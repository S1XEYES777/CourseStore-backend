from flask import Blueprint, request, jsonify, current_app, url_for
import base64, os
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
        SELECT id, title, price, author, description, image_path
        FROM courses
        ORDER BY id DESC
    """)

    rows = cur.fetchall()
    conn.close()

    courses = []

    for r in rows:
        image_url = None
        image_b64 = None

        if r["image_path"]:
            try:
                img_file = os.path.join(current_app.root_path, "static", "images", r["image_path"])
                if os.path.exists(img_file):
                    with open(img_file, "rb") as f:
                        image_b64 = base64.b64encode(f.read()).decode()

                image_url = url_for("static", filename=f"images/{r['image_path']}", _external=True)
            except:
                pass

        courses.append({
            "id": r["id"],
            "title": r["title"],
            "price": r["price"],
            "author": r["author"],
            "description": r["description"],
            "image": image_b64,
            "image_url": image_url,
        })

    return jsonify({"status": "ok", "courses": courses})


# =========================================================
# GET /api/course — 1 курс
# =========================================================
@courses_bp.get("/api/course")
def get_course():
    course_id = request.args.get("course_id", type=int)

    if not course_id:
        return jsonify({"status": "error", "message": "Нет course_id"}), 400

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT id, title, price, author, description, image_path
        FROM courses
        WHERE id = %s
    """, (course_id,))
    c = cur.fetchone()

    if not c:
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

    # загрузка изображения
    image_b64 = None
    image_url = None

    if c["image_path"]:
        try:
            img_file = os.path.join(current_app.root_path, "static", "images", c["image_path"])
            if os.path.exists(img_file):
                with open(img_file, "rb") as f:
                    image_b64 = base64.b64encode(f.read()).decode()
            image_url = url_for("static", filename=f"images/{c['image_path']}", _external=True)
        except:
            pass

    return jsonify({
        "status": "ok",
        "course": {
            "id": c["id"],
            "title": c["title"],
            "price": c["price"],
            "author": c["author"],
            "description": c["description"],
            "image": image_b64,
            "image_url": image_url,
            "lessons": lessons
        }
    })


# =========================================================
# POST /api/courses/add — Добавить курс (Admin.py)
# =========================================================
@courses_bp.post("/api/courses/add")
def add_course():
    data = request.get_json(force=True)

    title = data.get("title", "").strip()
    author = data.get("author", "").strip()
    description = data.get("description", "").strip()
    price = int(data.get("price", 0))
    image_b64 = data.get("image")

    if not title or not author or not description or price <= 0:
        return jsonify({"status": "error", "message": "Неверные данные"}), 400

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        INSERT INTO courses (title, price, author, description)
        VALUES (%s, %s, %s, %s)
        RETURNING id
    """, (title, price, author, description))
    cid = cur.fetchone()["id"]

    # сохраняем картинку
    if image_b64:
        try:
            img_bytes = base64.b64decode(image_b64)
            file_name = f"course_{cid}.jpg"
            img_dir = os.path.join(current_app.root_path, "static", "images")
            os.makedirs(img_dir, exist_ok=True)

            with open(os.path.join(img_dir, file_name), "wb") as f:
                f.write(img_bytes)

            cur.execute("UPDATE courses SET image_path=%s WHERE id=%s", (file_name, cid))
        except:
            pass

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
    image_b64 = data.get("image")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE courses
        SET title=%s, price=%s, author=%s, description=%s
        WHERE id=%s
    """, (title, price, author, description, cid))

    if image_b64:
        try:
            img_bytes = base64.b64decode(image_b64)
            file_name = f"course_{cid}.jpg"
            img_dir = os.path.join(current_app.root_path, "static", "images")
            os.makedirs(img_dir, exist_ok=True)

            with open(os.path.join(img_dir, file_name), "wb") as f:
                f.write(img_bytes)

            cur.execute("UPDATE courses SET image_path=%s WHERE id=%s", (file_name, cid))
        except:
            pass

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

    cur.execute("DELETE FROM lessons   WHERE course_id=%s", (cid,))
    cur.execute("DELETE FROM purchases WHERE course_id=%s", (cid,))
    cur.execute("DELETE FROM cart_items WHERE course_id=%s", (cid,))
    cur.execute("DELETE FROM reviews   WHERE course_id=%s", (cid,))
    cur.execute("DELETE FROM courses   WHERE id=%s", (cid,))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})
