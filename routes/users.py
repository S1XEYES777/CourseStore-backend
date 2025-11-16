from flask import Blueprint, request, jsonify
from db import get_connection

users_bp = Blueprint("users", __name__)


# ====================================================================
# GET /api/admin/users — Получить всех пользователей
# ====================================================================
@users_bp.get("/api/admin/users")
def admin_get_users():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, phone, password, balance
        FROM users
        ORDER BY id DESC
    """)

    rows = cur.fetchall()
    conn.close()

    users = [{
        "id": r["id"],
        "name": r["name"],
        "phone": r["phone"],
        "password": r["password"],  # Admin может видеть пароль
        "balance": r["balance"],
    } for r in rows]

    return jsonify({"status": "ok", "users": users})


# ====================================================================
# POST /api/admin/users/update — изменить пользователя
# ====================================================================
@users_bp.post("/api/admin/users/update")
def admin_update_user():
    data = request.get_json(force=True)

    user_id = data.get("id")
    name = data.get("name", "").strip()
    phone = data.get("phone", "").strip()
    password = data.get("password", "").strip()
    balance = data.get("balance")

    if not user_id or not name or not phone or not password:
        return jsonify({"status": "error", "message": "Неверные данные"}), 400

    try:
        balance = float(balance)
    except:
        return jsonify({"status": "error", "message": "Баланс должен быть числом"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET name = %s, phone = %s, password = %s, balance = %s
        WHERE id = %s
    """, (name, phone, password, balance, user_id))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ====================================================================
# POST /api/admin/users/delete — удалить пользователя
# ====================================================================
@users_bp.post("/api/admin/users/delete")
def admin_delete_user():
    data = request.get_json(force=True)
    user_id = data.get("id")

    if not user_id:
        return jsonify({"status": "error", "message": "Нет id"}), 400

    conn = get_connection()
    cur = conn.cursor()

    # Удаляем данные из зависимых таблиц
    cur.execute("DELETE FROM purchases WHERE user_id = %s", (user_id,))
    cur.execute("DELETE FROM cart_items  WHERE user_id = %s", (user_id,))
    cur.execute("DELETE FROM reviews     WHERE user_id = %s", (user_id,))

    # Удаляем самого пользователя
    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})
