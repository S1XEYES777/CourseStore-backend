from flask import Blueprint, request, jsonify
import psycopg2.extras
from db import get_connection

courses_bp = Blueprint("courses", __name__)

# =========================================================
# GET /api/courses — список всех курсов
# =========================================================
@courses_bp.get("/api/courses")
def get_courses():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT id, title, price, author, description, image
        FROM courses
        ORDER BY id DESC
    """)

    rows = cur.fetchall()
    conn.close()

    courses = []
    for r in rows:
        courses.append({
            "id": r["id"],
            "title": r["title"],
            "price": r["price"],
            "author": r["author"],
            "description": r["description"],
            "image": r["image"]  # base64
        })

    return jsonify({"status": "ok", "courses": courses})


# =========================================================
# GET /api/course — один курс
# =========================================================
@courses_bp.get("/api/course")
def get_course():
    course_id = request.args.get("course_id", type=int)
    if not course_id:
        return jsonify({"status": "error", "message": "Нет course_id"}), 400

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT id, title, price, author, description, image
        FROM courses
        WHERE id = %s
    """, (course_id,))
    course = cur.fetchone()

    if not course:
        conn.close()
        return jsonify({"status": "error", "message": "Курс не найден"}), 404

    cur.execute("""
        SELECT id, title, youtube_url, position
        FROM lessons
        WHERE course_id = %s
        ORDER BY position ASC
    """, (course_id,))
    lessons = cur.fetchall()

    conn.close()

    return jsonify({
        "status": "ok",
        "course": {
            **course,
            "lessons": lessons
        }
    })


# =========================================================
# POST /api/courses/add — Добавить курс
# =========================================================
@courses_bp.post("/api/courses/add")
def add_course():
    data = request.get_json(force=True)

    title = data.get("title", "").strip()
    author = data.get("author", "").strip()
    description = data.get("description", "").strip()
    price = int(data.get("price", 0))

    # ВАЖНО: Tkinter отправляет base64 в поле "image"
    image_b64 = data.get("image", "").strip()

    if not title or not author or not description or not image_b64 or price <= 0:
        return jsonify({"status": "error", "message": "Неверные данные"}), 400

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        INSERT INTO courses (title, price, author, description, image)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """, (title, price, author, description, image_b64))

    cid = cur.fetchone()["id"]
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "course_id": cid})


# =========================================================
# POST /api/courses/update — Изменить курс
# =========================================================
@courses_bp.post("/api/courses/update")
def update_course():
    data = request.get_json(force=True)

    cid = data.get("id")
    title = data.get("title", "").strip()
    author = data.get("author", "").strip()
    description = data.get("description", "").strip()
    price = int(data.get("price", 0))

    # Здесь image может быть либо base64, либо пустой
    image_b64 = data.get("image", "").strip()

    if not cid or not title or not author or not description or price <= 0:
        return jsonify({"status": "error", "message": "Неверные данные"}), 400

    conn = get_connection()
    cur = conn.cursor()

    # Если пользователь выбрал новое изображение
    if image_b64:
        cur.execute("""
            UPDATE courses
            SET title=%s, price=%s, author=%s, description=%s, image=%s
            WHERE id=%s
        """, (title, price, author, description, image_b64, cid))
    else:
        cur.execute("""
            UPDATE courses
            SET title=%s, price=%s, author=%s, description=%s
            WHERE id=%s
        """, (title, price, author, description, cid))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# =========================================================
# POST /api/courses/delete — Удалить курс
# =========================================================
@courses_bp.post("/api/courses/delete")
def delete_course():
    data = request.get_json(force=True)
    cid = data.get("id")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM lessons WHERE course_id=%s", (cid,))
    cur.execute("DELETE FROM purchases WHERE course_id=%s", (cid,))
    cur.execute("DELETE FROM cart_items WHERE course_id=%s", (cid,))
    cur.execute("DELETE FROM reviews WHERE course_id=%s", (cid,))
    cur.execute("DELETE FROM courses WHERE id=%s", (cid,))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})
