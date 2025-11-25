from flask import Blueprint, request, jsonify
import os
import json

reviews_bp = Blueprint("reviews", __name__, url_prefix="/api/reviews")

# ==========================
# JSON PATHS
# ==========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")

REVIEWS_FILE = os.path.join(DATA_DIR, "reviews.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")


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


def get_user_name(user_id):
    users = load_json(USERS_FILE)
    for u in users:
        if int(u.get("id", 0)) == int(user_id):
            return u.get("name", "Unknown")
    return "Unknown"


# =========================================================
# 📌 GET /api/reviews?course_id=ID — получить отзывы курса
# =========================================================
@reviews_bp.get("")
def get_reviews():
    course_id = request.args.get("course_id", type=int)
    if not course_id:
        return jsonify({"status": "error", "message": "Нет course_id"}), 400

    reviews = load_json(REVIEWS_FILE)
    lesson_reviews = [
        r for r in reviews if int(r.get("course_id", 0)) == course_id
    ]

    for r in lesson_reviews:
        r["user_name"] = get_user_name(r.get("user_id"))

    return jsonify({"status": "ok", "reviews": lesson_reviews})


# =========================================================
# 📌 POST /api/reviews/add — добавить отзыв
# =========================================================
@reviews_bp.post("/add")
def add_review():
    data = request.get_json(force=True)

    user_id = data.get("user_id")
    course_id = data.get("course_id")
    stars = data.get("stars")
    text = (data.get("text") or "").strip()

    if not user_id or not course_id or not text:
        return jsonify({"status": "error", "message": "Неверные данные"}), 400

    try:
        stars = int(stars)
        if not (1 <= stars <= 5):
            raise ValueError
    except:
        return jsonify({"status": "error", "message": "Оценка должна быть от 1 до 5"}), 400

    reviews = load_json(REVIEWS_FILE)
    rid = next_id(reviews)

    new_review = {
        "id": rid,
        "user_id": int(user_id),
        "course_id": int(course_id),
        "stars": stars,
        "text": text,
    }

    reviews.append(new_review)
    save_json(REVIEWS_FILE, reviews)

    return jsonify({"status": "ok"})
