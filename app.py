# app.py
import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS

# ==========================
#  НАСТРОЙКИ
# ==========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

USERS_FILE = os.path.join(DATA_DIR, "users.json")
COURSES_FILE = os.path.join(DATA_DIR, "courses.json")
LESSONS_FILE = os.path.join(DATA_DIR, "lessons.json")
REVIEWS_FILE = os.path.join(DATA_DIR, "reviews.json")


# ==========================
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================

def load_json(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def next_id(items):
    if not items:
        return 1
    return max(int(x.get("id", 0)) for x in items) + 1


def course_public_dict(c):
    """Добавляем image_url в курс."""
    c = dict(c)
    img = c.get("image") or ""
    if img and not img.startswith("data:"):
        c["image_url"] = "data:image/jpeg;base64," + img
    elif img:
        c["image_url"] = img
    else:
        c["image_url"] = None
    return c


# ==========================
#  APP
# ==========================
app = Flask(__name__)
CORS(app, supports_credentials=True)


# ==========================
#  ГЛОБАЛЬНЫЙ ХЭНДЛЕР ОШИБОК
# ==========================
@app.errorhandler(Exception)
def handle_any_error(e):
    # В лог — подробности, клиенту — JSON
    print("SERVER ERROR:", repr(e))
    return jsonify({"status": "error", "message": str(e)}), 500


# ==========================
#  PING / STATUS
# ==========================
@app.get("/api/ping")
def ping():
    return {"status": "ok", "message": "backend running (json mode)"}


@app.get("/")
def index():
    return {"status": "running", "service": "CourseStore JSON Backend"}


# =========================================================
#  АВТОРИЗАЦИЯ
# =========================================================

@app.post("/api/register")
def register():
    data = request.get_json(force=True)

    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()

    if not name or not phone or not password:
        return jsonify({"status": "error", "message": "Заполни все поля"}), 400

    users = load_json(USERS_FILE)

    # проверка телефона
    for u in users:
        if u.get("phone") == phone:
            return jsonify({"status": "error", "message": "Телефон уже зарегистрирован"}), 400

    uid = next_id(users)
    user = {
        "id": uid,
        "name": name,
        "phone": phone,
        "password": password,
        "balance": 0
    }
    users.append(user)
    save_json(USERS_FILE, users)

    return jsonify({"status": "ok", "user": {k: user[k] for k in ("id", "name", "phone", "balance")}})


@app.post("/api/login")
def login():
    data = request.get_json(force=True)
    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()

    users = load_json(USERS_FILE)

    for u in users:
        if u.get("phone") == phone and u.get("password") == password:
            user_public = {k: u[k] for k in ("id", "name", "phone", "balance")}
            return jsonify({"status": "ok", "user": user_public})

    return jsonify({"status": "error", "message": "Неверный телефон или пароль"}), 400


# =========================================================
#  КУРСЫ
# =========================================================

@app.get("/api/courses")
def api_get_courses():
    courses = load_json(COURSES_FILE)
    return jsonify({
        "status": "ok",
        "courses": [course_public_dict(c) for c in courses]
    })


# совместимость: и /api/courses/one, и /api/course
def _get_course_with_lessons(course_id: int):
    courses = load_json(COURSES_FILE)
    lessons = load_json(LESSONS_FILE)

    course = next((c for c in courses if int(c.get("id")) == course_id), None)
    if not course:
        return None

    course_lessons = [
        l for l in lessons if int(l.get("course_id")) == course_id
    ]
    course_lessons.sort(key=lambda x: int(x.get("position", 0)))

    c_pub = course_public_dict(course)
    c_pub["lessons"] = course_lessons
    return c_pub


@app.get("/api/courses/one")
def api_get_course_one():
    course_id = request.args.get("course_id", type=int)
    if not course_id:
        return jsonify({"status": "error", "message": "Нет course_id"}), 400

    c_pub = _get_course_with_lessons(course_id)
    if not c_pub:
        return jsonify({"status": "error", "message": "Курс не найден"}), 404

    return jsonify({"status": "ok", "course": c_pub})


@app.get("/api/course")
def api_get_course_single_alias():
    # для course.html: /api/course?course_id=
    return api_get_course_one()


@app.post("/api/courses/add")
def api_add_course():
    data = request.get_json(force=True)

    title = (data.get("title") or "").strip()
    author = (data.get("author") or "").strip()
    description = (data.get("description") or "").strip()
    image_b64 = (data.get("image") or "").strip()

    try:
        price = int(data.get("price") or 0)
    except ValueError:
        price = 0

    if not title or not author or not description or not image_b64 or price <= 0:
        return jsonify({"status": "error", "message": "Неверные данные курса"}), 400

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


@app.post("/api/courses/update")
def api_update_course():
    data = request.get_json(force=True)

    cid = data.get("id")
    title = (data.get("title") or "").strip()
    author = (data.get("author") or "").strip()
    description = (data.get("description") or "").strip()
    image_b64 = (data.get("image") or "").strip()

    try:
        price = int(data.get("price") or 0)
    except ValueError:
        price = 0

    if not cid or not title or not author or not description or price <= 0:
        return jsonify({"status": "error", "message": "Неверные данные"}), 400

    courses = load_json(COURSES_FILE)
    updated = False

    for c in courses:
        if int(c.get("id")) == int(cid):
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


@app.post("/api/courses/delete")
def api_delete_course():
    data = request.get_json(force=True)
    cid = data.get("id")

    if not cid:
        return jsonify({"status": "error", "message": "Нет id"}), 400

    cid = int(cid)

    courses = load_json(COURSES_FILE)
    lessons = load_json(LESSONS_FILE)
    reviews = load_json(REVIEWS_FILE)

    courses = [c for c in courses if int(c.get("id")) != cid]
    lessons = [l for l in lessons if int(l.get("course_id")) != cid]
    reviews = [r for r in reviews if int(r.get("course_id")) != cid]

    save_json(COURSES_FILE, courses)
    save_json(LESSONS_FILE, lessons)
    save_json(REVIEWS_FILE, reviews)

    return jsonify({"status": "ok"})
    

# =========================================================
#  УРОКИ
# =========================================================

@app.get("/api/lessons")
def api_get_lessons():
    course_id = request.args.get("course_id", type=int)
    if not course_id:
        return jsonify({"status": "error", "message": "Нет course_id"}), 400

    lessons = load_json(LESSONS_FILE)
    result = [
        l for l in lessons if int(l.get("course_id")) == course_id
    ]
    result.sort(key=lambda x: int(x.get("position", 0)))

    return jsonify({"status": "ok", "lessons": result})


@app.post("/api/lessons/add")
def api_add_lesson():
    data = request.get_json(force=True)

    course_id = data.get("course_id")
    title = (data.get("title") or "").strip()
    youtube_url = (data.get("youtube_url") or "").strip()
    position = int(data.get("position") or 0)

    if not course_id or not title or not youtube_url:
        return jsonify({"status": "error", "message": "Неверные данные урока"}), 400

    lessons = load_json(LESSONS_FILE)
    lid = next_id(lessons)

    lesson = {
        "id": lid,
        "course_id": int(course_id),
        "title": title,
        "youtube_url": youtube_url,
        "position": position,
    }
    lessons.append(lesson)
    save_json(LESSONS_FILE, lessons)

    return jsonify({"status": "ok", "id": lid})


@app.post("/api/lessons/delete")
def api_delete_lesson():
    data = request.get_json(force=True)
    lid = data.get("id")
    if not lid:
        return jsonify({"status": "error", "message": "Нет id"}), 400

    lessons = load_json(LESSONS_FILE)
    lessons = [l for l in lessons if int(l.get("id")) != int(lid)]
    save_json(LESSONS_FILE, lessons)

    return jsonify({"status": "ok"})


# =========================================================
#  ОТЗЫВЫ (на будущее, чтобы не ломалось)
# фронт сейчас почти не использует, но пусть будут
# =========================================================

@app.get("/api/reviews")
def api_get_reviews():
    course_id = request.args.get("course_id", type=int)
    if not course_id:
        return jsonify({"status": "error", "message": "Нет course_id"}), 400

    reviews = load_json(REVIEWS_FILE)
    result = [r for r in reviews if int(r.get("course_id")) == course_id]

    return jsonify({"status": "ok", "reviews": result})


@app.post("/api/reviews/add")
def api_add_review():
    data = request.get_json(force=True)

    user_id = data.get("user_id")
    course_id = data.get("course_id")
    stars = data.get("stars")
    text = (data.get("text") or "").strip()

    if not user_id or not course_id or not text:
        return jsonify({"status": "error", "message": "Неверные данные"}), 400

    try:
        stars = int(stars)
        if stars < 1 or stars > 5:
            raise ValueError
    except Exception:
        return jsonify({"status": "error", "message": "Оценка 1–5"}), 400

    reviews = load_json(REVIEWS_FILE)
    rid = next_id(reviews)

    review = {
        "id": rid,
        "user_id": int(user_id),
        "course_id": int(course_id),
        "stars": stars,
        "text": text
    }
    reviews.append(review)
    save_json(REVIEWS_FILE, reviews)

    return jsonify({"status": "ok"})


# =========================================================
#  АДМИН: ПОЛЬЗОВАТЕЛИ
# =========================================================

@app.get("/api/admin/users")
def api_admin_users():
    users = load_json(USERS_FILE)
    # пароли не убираю, потому что админке нужны
    return jsonify({"status": "ok", "users": users})


@app.post("/api/admin/users/update")
def api_admin_user_update():
    data = request.get_json(force=True)

    uid = data.get("id")
    if not uid:
        return jsonify({"status": "error", "message": "Нет id"}), 400

    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()
    try:
        balance = int(data.get("balance") or 0)
    except ValueError:
        balance = 0

    users = load_json(USERS_FILE)
    updated = False

    for u in users:
        if int(u.get("id")) == int(uid):
            if name:
                u["name"] = name
            if phone:
                u["phone"] = phone
            if password:
                u["password"] = password
            u["balance"] = balance
            updated = True
            break

    if not updated:
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    save_json(USERS_FILE, users)
    return jsonify({"status": "ok"})


@app.post("/api/admin/users/delete")
def api_admin_user_delete():
    data = request.get_json(force=True)
    uid = data.get("id")
    if not uid:
        return jsonify({"status": "error", "message": "Нет id"}), 400

    users = load_json(USERS_FILE)
    users = [u for u in users if int(u.get("id")) != int(uid)]
    save_json(USERS_FILE, users)

    return jsonify({"status": "ok"})


# =========================================================
#  ЗАПУСК ЛОКАЛЬНО
# =========================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

