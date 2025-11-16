from flask import Blueprint, request, jsonify
from db import get_connection

reviews_bp = Blueprint("reviews", __name__)


# =========================================================
# GET /api/reviews — получить отзывы курса
# =========================================================
@reviews_bp.get("/api/reviews")
def get_reviews():
    course_id = request.args.get("course_id", type=int)
    if not course_id:
        return jsonify({"status": "error", "message": "Нет course_id"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT r.id, r.rating, r.text, r.created_at, u.name AS user_name
        FROM reviews r
        JOIN users u ON r.user_id = u.id
        WHERE r.course_id = %s
        ORDER BY r.created_at DESC
    """, (course_id,))

    rows = cur.fetchall()
    conn.close()

    reviews = [{
        "id": r["id"],
        "rating": r["rating"],
        "text": r["text"],
        "created_at": r["created_at"],
        "user_name": r["user_name"]
    } for r in rows]

    return jsonify({"status": "ok", "reviews": reviews})


# =========================================================
# POST /api/review/add — добавить отзыв
# =========================================================
@reviews_bp.post("/api/review/add")
def add_review():
    data = request.get_json(force=True)

    user_id = data.get("user_id")
    course_id = data.get("course_id")
    rating = int(data.get("rating", 0))
    text = data.get("text", "").strip()

    if not user_id or not course_id or not text or rating < 1 or rating > 5:
        return jsonify({"status": "error", "message": "Неверные данные"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO reviews (user_id, course_id, rating, text)
        VALUES (%s, %s, %s, %s)
    """, (user_id, course_id, rating, text))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})
