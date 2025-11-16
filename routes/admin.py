from flask import Blueprint, request, jsonify
from db import get_connection

admin_bp = Blueprint("admin", __name__)


# ============================================================
# Получить ВСЕХ пользователей
# ============================================================
@admin_bp.get("/api/admin/users")
def admin_get_users():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, phone, balance FROM users ORDER BY id")
    rows = cur.fetchall()
    conn.close()

    users = [{
        "id": row["id"],
        "name": row["name"],
        "phone": row["phone"],
        "balance": row["balance"]
    } for row in rows]

    return jsonify({"status": "ok", "users": users})


# ============================================================
# Обновить пользователя
# ============================================================
@admin_bp.post("/api/admin/users/update")
def admin_update_user():
    data = request.get_json(force=True)
    uid = data.get("id")
    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()
    balance = data.get("balance", 0)

    if not uid:
        return jsonify({"status": "error", "message": "Нет user id"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET name = %s,
            phone = %s,
            password = %s,
            balance = %s
        WHERE id = %s
    """, (name, phone, password, balance, uid))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ============================================================
# Удалить пользователя
# ============================================================
@admin_bp.post("/api/admin/users/delete")
def admin_delete_user():
    data = request.get_json(force=True)
    uid = data.get("id")

    if not uid:
        return jsonify({"status": "error", "message": "Нет user id"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM users WHERE id = %s", (uid,))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ============================================================
# Удалить урок
# ============================================================
@admin_bp.post("/api/admin/lesson/delete")
def admin_delete_lesson():
    data = request.get_json(force=True)
    lid = data.get("id")

    if not lid:
        return jsonify({"status": "error", "message": "Нет lesson id"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM lessons WHERE id = %s", (lid,))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ============================================================
# Удалить курс (+ уроки + покупки)
# ============================================================
@admin_bp.post("/api/admin/course/delete")
def admin_delete_course():
    data = request.get_json(force=True)
    cid = data.get("id")

    if not cid:
        return jsonify({"status": "error", "message": "Нет course id"}), 400

    conn = get_connection()
    cur = conn.cursor()

    # Удаляем связанные записи
    cur.execute("DELETE FROM lessons WHERE course_id = %s", (cid,))
    cur.execute("DELETE FROM purchases WHERE course_id = %s", (cid,))
    cur.execute("DELETE FROM cart_items WHERE course_id = %s", (cid,))
    cur.execute("DELETE FROM reviews WHERE course_id = %s", (cid,))

    # Удаляем сам курс
    cur.execute("DELETE FROM courses WHERE id = %s", (cid,))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})
