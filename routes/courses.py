from flask import Blueprint, request, jsonify
import os
import json

courses_bp = Blueprint("courses", __name__, url_prefix="/api/courses")

# ==========================
# JSON PATHS
# ==========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")

COURSES_FILE = os.path.join(DATA_DIR, "courses.json")
LESSONS_FILE = os.path.join(DATA_DIR, "lessons.json")
REVIEWS_FILE = os.path.join(DATA_DIR, "reviews.json")
CART_FILE = os.path.join(DATA_DIR, "cart.json")


# ==========================
# HELPERS
# ==========================
def load_json(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def next_id(items):
    if not items:
        return 1
    return max(int(x.get("id", 0)) for x in items) + 1


def course_public(c):
    """Добавляем image_url (как в app.py)"""
    c = dict(c)
    img = c.get("image") or ""
    if img and not img.startswith("data:"):
        c["image_url"] = "data:image/jpeg;base64," + img
    elif img:
        c["image_url"] = img
    else:
        c["image_url"] = None
    return c


# ================================
# GET /api/courses  — список курсов
# ================================
@courses_bp.get("")
def get_courses():
    courses = load_json(COURSES_FILE)
    courses = [course_public(c) for c in courses]
    return jsonify({"status": "ok", "courses": courses})


# =============================================
# GET /api/courses/one — один курс + уроки JSON
# =============================================
@courses_bp.get("/one")
def get_course():
    course_id = request.args.get("course_id", type=int)
    if not course_id:
        return jsonify({"status": "error", "message": "Нет course_id"}), 400

    courses = load_json(COURSES_FILE)
    lessons = load_json(LESSONS_FILE)

    course = next((c for c in courses if int(c["id"]) == course_id), None)
    if not course:
        return jsonify({"status": "error", "message": "Курс не найден"}), 404

    course_lessons = [
        l for l in lessons if int(l.get("course_id", 0)) == int(course_id)
    ]
    course_lessons.sort(key=lambda x: int(x.get("position", 0)))

    course = course_public(course)
    course["lessons"] = course_lessons

    return jsonify({"status": "ok", "course": course})


# ================================
# POST /api/courses/add — создать курс
# ================================
@courses_bp.post("/add")
def add_course():
    data = request.get_json(force=True)

    title = data.get("title", "").strip()
    author = data.get("author", "").strip()
    description = data.get("description", "").strip()
    price = int(data.get("price", 0))
    image_b64 = data.get("image", "").strip()

    if not title or not author or not description or not image_b64 or price <= 0:
        return jsonify({"status": "error", "message": "Неверные данные"}), 400

    courses = load_json(COURSES_FILE)
    cid = next_id(courses)

    course = {
        "id": cid,
        "title": title,
        "author": author,
        "description": description,
        "price": price,
        "image": image_b64
    }

    courses.append(course)
    save_json(COURSES_FILE, courses)

    return jsonify({"status": "ok", "course_id": cid})


# =======================================
# POST /api/courses/update — обновить курс
# =======================================
@courses_bp.post("/update")
def update_course():
    data = request.get_json(force=True)

    cid = data.get("id")
    title = data.get("title", "").strip()
    author = data.get("author", "").strip()
    description = data.get("description", "").strip()
    price = int(data.get("price", 0))
    image_b64 = data.get("image", "").strip()

    if not cid or not title or not author or not description or price <= 0:
        return jsonify({"status": "error", "message": "Неверные данные"}), 400

    courses = load_json(COURSES_FILE)

    updated = False
    for c in courses:
        if int(c["id"]) == int(cid):
            c["title"] = title
            c["author"] = author
            c["description"] = description
            c["price"] = price
            if image_b64:
                c["image"] = image_b64
            updated = True
            break

    if not updated:
        return jsonify({"status": "error", "message": "Курс не найден"}), 404

    save_json(COURSES_FILE, courses)
    return jsonify({"status": "ok"})


# ==========================================
# POST /api/courses/delete — удалить курс JSON
# ==========================================
@courses_bp.post("/delete")
def delete_course():
    data = request.get_json(force=True)
    cid = data.get("id")

    if not cid:
        return jsonify({"status": "error", "message": "Нет id"}), 400

    cid = int(cid)

    courses = load_json(COURSES_FILE)
    lessons = load_json(LESSONS_FILE)
    reviews = load_json(REVIEWS_FILE)
    cart = load_json(CART_FILE)

    courses = [c for c in courses if int(c["id"]) != cid]
    lessons = [l for l in lessons if int(l.get("course_id", 0)) != cid]
    reviews = [r for r in reviews if int(r.get("course_id", 0)) != cid]
    cart = [item for item in cart if int(item.get("course_id", 0)) != cid]

    save_json(COURSES_FILE, courses)
    save_json(LESSONS_FILE, lessons)
    save_json(REVIEWS_FILE, reviews)
    save_json(CART_FILE, cart)

    return jsonify({"status": "ok"})
