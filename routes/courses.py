from flask import Blueprint, request, jsonify, current_app, url_for
import base64, os
from db import get_connection

courses_bp = Blueprint("courses", __name__)


# =========================================================
# GET /api/courses — список курсов
# =========================================================
@courses_bp.get("/api/courses")
def get_courses():
    conn = get_connection()
    cur = conn.cursor()

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
                file_path = os.path.join(current_app.root_path, "static", "images", r["image_path"])
                if os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        image_b64 = base64.b64encode(f.read()).decode("utf-8")

                image_url = url_for("static", filename=f"images/{r['image_path']}", _external=True)
            except:
                pass

        courses.append({
            "id": r["id"],
            "title": r["title"],
            "price": r["price"],
            "author": r["author"],
            "description": r["description"],
            "image": image_b64,          # 🔥 ВОЗВРАЩАЕМ BASE64
            "image_url": image_url        # 🔥 И URL — если надо
        })

    return jsonify({"status": "ok", "courses": courses})


# =========================================================
# GET /api/course — 1 курс + уроки
# =========================================================
@courses_bp.get("/api/course")
def get_course():
    course_id = request.args.get("course_id", type=int)
    if not course_id:
        return jsonify({"status": "error", "message": "Нет course_id"}), 400

    conn = get_connection()
    cur = conn.cursor()

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
    lessons = [{
        "id": r["id"],
        "title": r["title"],
        "youtube_url": r["youtube_url"],
        "position": r["position"]
    } for r in cur.fetchall()]

    conn.close()

    # загружаем картинку
    image_b64 = None
    image_url = None
    if c["image_path"]:
        try:
            file_path = os.path.join(current_app.root_path, "static", "images", c["image_path"])
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    image_b64 = base64.b64encode(f.read()).decode("utf-8")

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
# POST /api/courses/add — Admin.py
# =========================================================
@courses_bp.post("/api/courses/add")
def admin_add_course():
    data = request.get_json(force=True)

    title = data.get("title", "").strip()
    price = int(data.get("price", 0))
    author = data.get("author", "").strip()
    description = data.get("description", "").strip()
    image_b64 = data.get("image")

    if not title or not author or not description or price <= 0:
        return jsonify({"status": "error", "message": "Неверные данные"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO courses (title, price, author, description)
        VALUES (%s, %s, %s, %s)
        RETURNING id
    """, (title, price, author, description))

    course_id = cur.fetchone()["id"]

    if image_b64:
        try:
            img_bytes = base64.b64decode(image_b64)
            image_path = f"course_{course_id}.jpg"

            folder = os.path.join(current_app.root_path, "static", "images")
            os.makedirs(folder, exist_ok=True)

            with open(os.path.join(folder, image_path), "wb") as f:
                f.write(img_bytes)

            cur.execute("UPDATE courses SET image_path=%s WHERE id=%s", (image_path, course_id))
        except Exception as e:
            print("Ошибка при сохранении изображения:", e)

    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "course_id": course_id})


# =========================================================
# POST /api/courses/update
# =========================================================
@courses_bp.post("/api/courses/update")
def update_course():
    data = request.get_json(force=True)

    cid = data.get("id")
    title = data.get("title", "").strip()
    price = int(data.get("price", 0))
    author = data.get("author", "").strip()
    description = data.get("description", "").strip()
    image_b64 = data.get("image")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE courses
        SET title=%s, price=%s, author=%s, description=%s
        WHERE id=%s
    """, (title, price, author, description, cid))

    # если новая картинка — перезаписываем
    if image_b64:
        try:
            img_bytes = base64.b64decode(image_b64)
            image_path = f"course_{cid}.jpg"
            folder = os.path.join(current_app.root_path, "static", "images")
            os.makedirs(folder, exist_ok=True)

            with open(os.path.join(folder, image_path), "wb") as f:
                f.write(img_bytes)

            cur.execute("UPDATE courses SET image_path=%s WHERE id=%s", (image_path, cid))
        except:
            pass

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# =========================================================
# POST /api/courses/delete
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

