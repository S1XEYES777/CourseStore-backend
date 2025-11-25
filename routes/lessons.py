from flask import Blueprint, request, jsonify
import os
import json

lessons_bp = Blueprint("lessons", __name__, url_prefix="/api/lessons")


# ==========================
# JSON PATHS
# ==========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")

LESSONS_FILE = os.path.join(DATA_DIR, "lessons.json")


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
# 📌 GET /api/lessons?course_id=ID — получить уроки курса
# =========================================================
@lessons_bp.get("")
def get_lessons():
    course_id = request.args.get("course_id", type=int)
    if not course_id:
        return jsonify({"status": "error", "message": "Нет course_id"}), 400

    lessons = load_json(LESSONS_FILE)

    course_lessons = [
        l for l in lessons if int(l.get("course_id", 0)) == course_id
    ]
    course_lessons.sort(key=lambda x: int(x.get("position", 0)))

    return jsonify({"status": "ok", "lessons": course_lessons})


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

    lessons = load_json(LESSONS_FILE)

    # position — это max(position) + 1
    if lessons:
        pos = max([int(l.get("position", 0)) for l in lessons 
                   if int(l.get("course_id", 0)) == int(course_id)] + [0]) + 1
    else:
        pos = 1

    lesson_id = next_id(lessons)

    new_lesson = {
        "id": lesson_id,
        "course_id": int(course_id),
        "title": title,
        "youtube_url": youtube_url,
        "position": pos
    }

    lessons.append(new_lesson)
    save_json(LESSONS_FILE, lessons)

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

    lessons = load_json(LESSONS_FILE)
    lessons = [l for l in lessons if int(l.get("id", 0)) != int(lesson_id)]
    save_json(LESSONS_FILE, lessons)

    return jsonify({"status": "ok"})
