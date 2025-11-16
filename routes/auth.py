from flask import Blueprint, request, jsonify
from db import get_connection

auth_bp = Blueprint("auth", __name__)

# ============================
#      РЕГИСТРАЦИЯ
# ============================
@auth_bp.post("/api/register")
def register():
    data = request.get_json()
    name = data.get("name")
    phone = data.get("phone")
    password = data.get("password")

    if not name or not phone or not password:
        return jsonify({"status": "error", "message": "Заполните все поля"}), 400

    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO users (name, phone, password)
            VALUES (%s, %s, %s)
            RETURNING id, name, phone, balance
        """, (name, phone, password))

        user = cur.fetchone()
        conn.commit()

        return jsonify({
            "status": "ok",
            "user": {
                "user_id": user[0],
                "name": user[1],
                "phone": user[2],
                "balance": user[3]
            }
        })
    except:
        return jsonify({"status": "error", "message": "Телефон уже зарегистрирован"}), 400
    finally:
        conn.close()


# ============================
#      ВХОД
# ============================
@auth_bp.post("/api/login")
def login():
    data = request.get_json()
    phone = data.get("phone")
    password = data.get("password")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, phone, balance 
        FROM users 
        WHERE phone=%s AND password=%s
    """, (phone, password))

    user = cur.fetchone()
    conn.close()

    if not user:
        return jsonify({"status": "error", "message": "Неверный телефон или пароль"}), 400

    return jsonify({
        "status": "ok",
        "user": {
            "user_id": user[0],
            "name": user[1],
            "phone": user[2],
            "balance": user[3]
        }
    })
