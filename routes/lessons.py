from flask import Blueprint, request, jsonify
from db import get_connection

lessons_bp = Blueprint("lessons", __name__)


# =========================================================
# GET /api/lessons — получить уроки курса
# =========================================================
@lessons_bp.get("/api/lessons/<int:course_id>")
def get_lessons(course_id):
    if not course_id:
        return jsonify({"status": "error", "message": "Нет course_id"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, youtube_url, position
        FROM lessons
        WHERE course_id = ?
        ORDER BY position ASC
    """, (course_id,))

    rows = cur.fetchall()
    conn.close()

    lessons = [{
        "id": r["id"],
        "title": r["title"],
        "youtube_url": r["youtube_url"],
        "position": r["position"]
    } for r in rows]

    return jsonify({"status": "ok", "lessons": lessons})



# =========================================================
# POST /api/lessons/add — добавить урок
# =========================================================
@lessons_bp.post("/api/lessons/add")
def add_lesson():
    data = request.get_json(force=True)

    course_id = int(data.get("course_id", 0))
    title = data.get("title", "").strip()
    link = data.get("link", "").strip()

    if not course_id or not title or not link:
        return jsonify({"status": "error", "message": "Неверные данные"}), 400

    conn = get_connection()
    cur = conn.cursor()

    # новая позиция = последний номер + 1
    cur.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM lessons WHERE course_id = ?", (course_id,))
    pos = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO lessons (course_id, title, youtube_url, position)
        VALUES (?, ?, ?, ?)
    """, (course_id, title, link, pos))

    conn.commit()
    lesson_id = cur.lastrowid
    conn.close()

    return jsonify({"status": "ok", "lesson_id": lesson_id})


# =========================================================
# POST /api/lessons/delete — удалить урок
# =========================================================
@lessons_bp.post("/api/lessons/delete")
def delete_lesson():
    data = request.get_json(force=True)
    lesson_id = data.get("id")

    if not lesson_id:
        return jsonify({"status": "error", "message": "Нет id"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})

