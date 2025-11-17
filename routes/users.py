from flask import Blueprint, request, jsonify
from db import get_connection

users_bp = Blueprint("users", __name__)

# ============================================================
# 📌 ВНУТРЕННЯЯ ФУНКЦИЯ (чтобы не повторять код)
# ============================================================

def get_all_users():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, phone, password, balance
        FROM users
        ORDER BY id DESC
    """)

    rows = cur.fetchall()
    conn.close()

    return [{
        "id": r["id"],
        "name": r["name"],
        "phone": r["phone"],
        "password": r["password"],
        "balance": r["balance"]
    } for r in rows]


# ============================================================
# 📌 API для Tkinter Admin Panel
# ============================================================

# --- Получить всех пользователей ---
@users_bp.get("/api/users")
def get_users_public():
    return jsonify({"status": "ok", "users": get_all_users()})


# --- Обновить пользователя ---
@users_bp.post("/api/users/update")
def update_user_public():
    data = request.get_json(force=True)

    uid = data.get("id")
    name = data.get("name", "").strip()
    phone = data.get("phone", "").strip()
    password = data.get("password", "").strip()
    balance = data.get("balance")

    if not uid or not name or not phone or not password:
        return jsonify({"status": "error", "message": "Неверные данные"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET name=%s, phone=%s, password=%s, balance=%s
        WHERE id=%s
    """, (name, phone, password, balance, uid))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# --- Удалить пользователя ---
@users_bp.post("/api/users/delete")
def delete_user_public():
    data = request.get_json(force=True)
    uid = data.get("id")

    if not uid:
        return jsonify({"status": "error", "message": "Нет id"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM purchases WHERE user_id=%s", (uid,))
    cur.execute("DELETE FROM cart_items WHERE user_id=%s", (uid,))
    cur.execute("DELETE FROM reviews WHERE user_id=%s", (uid,))
    cur.execute("DELETE FROM users WHERE id=%s", (uid,))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ============================================================
# 📌 Старые маршруты (чтобы ничего не ломалось)
# ============================================================

@users_bp.get("/api/admin/users")
def admin_get_users():
    return jsonify({"status": "ok", "users": get_all_users()})


@users_bp.post("/api/admin/users/update")
def admin_update_user():
    return update_user_public()


@users_bp.post("/api/admin/users/delete")
def admin_delete_user():
    return delete_user_public()
