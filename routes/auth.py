from flask import Blueprint, request, jsonify
from db import get_connection

auth_bp = Blueprint("auth", __name__)


# ============================
#      РЕГИСТРАЦИЯ
# ============================
@auth_bp.post("/api/register")
def register():
    data = request.get_json()
    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()

    if not name or not phone or not password:
        return jsonify({"status": "error", "message": "Заполните все поля"}), 400

    conn = get_connection()
    cur = conn.cursor()

    # Проверка телефона
    cur.execute("SELECT id FROM users WHERE phone = %s", (phone,))
    if cur.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "Телефон уже зарегистрирован"}), 400

    # Создаём пользователя и сразу читаем его обратно
    cur.execute("""
        INSERT INTO users (name, phone, password, balance)
        VALUES (%s, %s, %s, 0)
        RETURNING id, name, phone, balance
    """, (name, phone, password))

    user = cur.fetchone()
    conn.commit()
    conn.close()

    user_obj = {
        "user_id": user["id"],
        "name": user["name"],
        "phone": user["phone"],
        "balance": user["balance"],
    }

    return jsonify({"status": "ok", "user": user_obj})


# ============================
#          ВХОД
# ============================
@auth_bp.post("/api/login")
def login():
    data = request.get_json()
    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()

    if not phone or not password:
        return jsonify({"status": "error", "message": "Заполните телефон и пароль"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, phone, balance
        FROM users
        WHERE phone = %s AND password = %s
    """, (phone, password))

    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"status": "error", "message": "Неверный телефон или пароль"}), 400

    user_obj = {
        "user_id": row["id"],
        "name": row["name"],
        "phone": row["phone"],
        "balance": row["balance"],
    }

    return jsonify({"status": "ok", "user": user_obj})
