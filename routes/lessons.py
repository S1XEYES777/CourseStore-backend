from flask import Blueprint, request, jsonify
from db import get_connection
import psycopg2.extras

lessons_bp = Blueprint("lessons", __name__, url_prefix="/api/lessons")


# =========================================================
# 📌 GET /api/lessons?course_id=ID — получить уроки курса
# =========================================================
@lessons_bp.get("")
def get_lessons():
    course_id = request.args.get("course_id", type=int)
    if not course_id:
        return jsonify({"status": "error", "message": "Нет course_id"}), 400

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT id, title, youtube_url, position
        FROM lessons
        WHERE course_id = %s
        ORDER BY position ASC
    """, (course_id,))

    lessons = cur.fetchall()
    conn.close()

    return jsonify({"status": "ok", "lessons": lessons})


# =========================================================
# 📌 Нормализация ссылок YouTube
# =========================================================
def normalize_youtube_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""

    if "youtu.be/" in url:
        return "https://youtu.be/" + url.split("youtu.be/")[1].split("?")[0]

    if "watch?v=" in url:
        vid = url.split("watch?v=")[1].split("&")[0]
        return f"https://youtu.be/{vid}"

    if 8 <= len(url) <= 20 and " " not in url:
        return f"https://youtu.be/{url}"

    return url


# =========================================================
# 📌 POST /api/lessons/add — добавить урок
# =========================================================
@lessons_bp.post("/add")
def add_lesson():
    data = request.get_json(force=True)

    course_id = data.get("course_id")
    title = (data.get("title") or "").strip()
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
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        "SELECT COALESCE(MAX(position), 0) + 1 AS pos FROM lessons WHERE course_id=%s",
        (course_id,)
    )
    pos = cur.fetchone()["pos"]

    cur.execute("""
        INSERT INTO lessons (course_id, title, youtube_url, position)
        VALUES (%s, %s, %s, %s)
        RETURNING id
    """, (course_id, title, youtube_url, pos))

    lesson_id = cur.fetchone()["id"]

    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "lesson_id": lesson_id})


# =========================================================
# 📌 POST /api/lessons/delete — удалить урок
# =========================================================
@lessons_bp.post("/delete")
def delete_lesson():
    data = request.get_json(force=True)
    lesson_id = data.get("id")

    if not lesson_id:
        return jsonify({"status": "error", "message": "Нет id"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM lessons WHERE id=%s", (lesson_id,))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})
