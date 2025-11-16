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
# NORMALIZE YOUTUBE LINKS
# =========================================================
def normalize_youtube_url(url: str) -> str:
    url = url.strip()

    if not url:
        return ""

    # https://youtu.be/ID
    if "youtu.be/" in url:
        return "https://youtu.be/" + url.split("youtu.be/")[1].split("?")[0]

    # https://youtube.com/watch?v=ID
    if "watch?v=" in url:
        vid = url.split("watch?v=")[1].split("&")[0]
        return f"https://youtu.be/{vid}"

    # Только ID (8–20 символов)
    if len(url) >= 8 and len(url) <= 20 and " " not in url:
        return f"https://youtu.be/{url}"

    return url


# =========================================================
# POST /api/lessons/add — добавить урок
# =========================================================
@lessons_bp.post("/api/lessons/add")
def add_lesson():
    data = request.get_json(force=True)

    course_id = int(data.get("course_id", 0))
    title = data.get("title", "").strip()

    # 🟢 FIX: принимаем и youtube_url и link и url
    raw_link = (
        data.get("youtube_url")
        or data.get("link")
        or data.get("url")
        or ""
    ).strip()

    youtube_url = normalize_youtube_url(raw_link)

    if not course_id or not title or not youtube_url:
        return jsonify({"status": "error", "message": "Неверные данные"}), 400

    conn = get_connection()
    cur = conn.cursor()

    # новая позиция = последний номер + 1
    cur.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM lessons WHERE course_id = ?", (course_id,))
    pos = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO lessons (course_id, title, youtube_url, position)
        VALUES (?, ?, ?, ?)
    """, (course_id, title, youtube_url, pos))

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
