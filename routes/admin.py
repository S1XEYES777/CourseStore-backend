from flask import Blueprint, request, jsonify
from db import get_connection
import psycopg2.extras

admin_bp = Blueprint("admin", __name__)


# ============================================================
# 📌 Получить всех пользователей
# ============================================================
@admin_bp.get("/api/admin/users")
def admin_get_users():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT id, name, phone, balance, password
        FROM users
        ORDER BY id DESC
    """)

    users = cur.fetchall()
    conn.close()

    return jsonify({"status": "ok", "users": users})


# ============================================================
# 📌 Обновить пользователя
# ============================================================
@admin_bp.post("/api/admin/users/update")
def admin_update_user():
    data = request.get_json(force=True)

    uid = data.get("id")
    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()
    balance = data.get("balance")

    if not uid or not name or not phone or not password:
        return jsonify({"status": "error", "message": "Неверные данные"}), 400

    try:
        balance = int(balance)
    except:
        return jsonify({"status": "error", "message": "Баланс должен быть числом"}), 400

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


# ============================================================
# 📌 Удалить пользователя
# ============================================================
@admin_bp.post("/api/admin/users/delete")
def admin_delete_user():
    data = request.get_json(force=True)
    uid = data.get("id")

    if not uid:
        return jsonify({"status": "error", "message": "Нет user id"}), 400

    conn = get_connection()
    cur = conn.cursor()

    # Удаление зависимых данных
    cur.execute("DELETE FROM purchases WHERE user_id=%s", (uid,))
    cur.execute("DELETE FROM cart_items WHERE user_id=%s", (uid,))
    cur.execute("DELETE FROM reviews WHERE user_id=%s", (uid,))

    # Удаляем пользователя
    cur.execute("DELETE FROM users WHERE id=%s", (uid,))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ============================================================
# 📌 Удалить урок
# ============================================================
@admin_bp.post("/api/admin/lesson/delete")
def admin_delete_lesson():
    data = request.get_json(force=True)
    lid = data.get("id")

    if not lid:
        return jsonify({"status": "error", "message": "Нет lesson id"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM lessons WHERE id=%s", (lid,))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ============================================================
# 📌 Удалить курс полностью
# ============================================================
@admin_bp.post("/api/admin/course/delete")
def admin_delete_course():
    data = request.get_json(force=True)
    cid = data.get("id")

    if not cid:
        return jsonify({"status": "error", "message": "Нет course id"}), 400

    conn = get_connection()
    cur = conn.cursor()

    # Удаление зависимостей
    cur.execute("DELETE FROM lessons WHERE course_id=%s", (cid,))
    cur.execute("DELETE FROM purchases WHERE course_id=%s", (cid,))
    cur.execute("DELETE FROM cart_items WHERE course_id=%s", (cid,))
    cur.execute("DELETE FROM reviews WHERE course_id=%s", (cid,))

    # Удаляем курс
    cur.execute("DELETE FROM courses WHERE id=%s", (cid,))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})
