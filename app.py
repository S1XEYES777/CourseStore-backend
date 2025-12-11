import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# ------------------------------------------------------------
# НАСТРОЙКИ
# ------------------------------------------------------------
DATA_FILE = "data.json"
UPLOAD_FOLDER = "uploads"
AVATAR_FOLDER = os.path.join(UPLOAD_FOLDER, "avatars")
COURSE_IMAGE_FOLDER = os.path.join(UPLOAD_FOLDER, "course_images")
VIDEO_FOLDER = os.path.join(UPLOAD_FOLDER, "videos")

# создаём папки
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AVATAR_FOLDER, exist_ok=True)
os.makedirs(COURSE_IMAGE_FOLDER, exist_ok=True)
os.makedirs(VIDEO_FOLDER, exist_ok=True)

app = Flask(__name__)
CORS(app)

# ------------------------------------------------------------
# ХРАНИЛИЩЕ (JSON)
# ------------------------------------------------------------
def load_data():
    if not os.path.exists(DATA_FILE):
        data = {
            "users": [],
            "courses": [],
            "carts": {}  # user_id -> [course_id]
        }
        save_data(data)
        return data
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def next_id(items):
    if not items:
        return 1
    return max(item["id"] for item in items) + 1


# ------------------------------------------------------------
# Упрощенный ответ пользователя
# ------------------------------------------------------------
def public_user(user):
    return {
        "id": user["id"],
        "phone": user["phone"],
        "name": user.get("name", ""),
        "balance": user.get("balance", 0),
        "avatar": user.get("avatar"),
        "my_courses": user.get("my_courses", []),
        "is_admin": user.get("is_admin", False)
    }


# ------------------------------------------------------------
# Статус сервера
# ------------------------------------------------------------
@app.route("/api/status")
def status():
    return jsonify({"status": "ok"})


# ------------------------------------------------------------
# РЕГИСТРАЦИЯ / ЛОГИН
# ------------------------------------------------------------
@app.route("/api/register", methods=["POST"])
def register():
    data = load_data()
    body = request.get_json(force=True)

    phone = body.get("phone", "").strip()
    password = body.get("password", "").strip()
    name = body.get("name", "").strip() or "Пользователь"

    if not phone or not password:
        return jsonify({"status": "error", "message": "Введите телефон и пароль"}), 400

    if any(u["phone"] == phone for u in data["users"]):
        return jsonify({"status": "error", "message": "Номер уже зарегистрирован"}), 400

    user_id = next_id(data["users"])

    is_admin = (phone == "77750476284" and password == "777")

    user = {
        "id": user_id,
        "phone": phone,
        "password": password,
        "name": name,
        "balance": 0,
        "avatar": None,
        "my_courses": [],
        "is_admin": is_admin
    }

    data["users"].append(user)
    save_data(data)

    return jsonify({"status": "ok", "user": public_user(user)})


@app.route("/api/login", methods=["POST"])
def login():
    data = load_data()
    body = request.get_json(force=True)

    phone = body.get("phone", "").strip()
    password = body.get("password", "").strip()

    for u in data["users"]:
        if u["phone"] == phone and u["password"] == password:

            # обновляем админа
            if phone == "77750476284" and password == "777":
                u["is_admin"] = True
                save_data(data)

            return jsonify({"status": "ok", "user": public_user(u)})

    return jsonify({"status": "error", "message": "Неверный номер или пароль"}), 400


# ------------------------------------------------------------
# КУРСЫ
# ------------------------------------------------------------
@app.route("/api/courses", methods=["GET"])
def get_courses():
    data = load_data()
    return jsonify({"status": "ok", "courses": data["courses"]})


@app.route("/api/course/<int:course_id>", methods=["GET"])
def get_course(course_id):
    data = load_data()
    for c in data["courses"]:
        if c["id"] == course_id:
            return jsonify({"status": "ok", "course": c})
    return jsonify({"status": "error", "message": "Курс не найден"}), 404


# ------------------------------------------------------------
# КОРЗИНА
# ------------------------------------------------------------
@app.route("/api/cart/<int:user_id>", methods=["GET"])
def get_cart(user_id):
    data = load_data()
    cart_ids = data["carts"].get(str(user_id), [])
    courses = [c for c in data["courses"] if c["id"] in cart_ids]
    return jsonify({"status": "ok", "cart": courses})


@app.route("/api/cart/add", methods=["POST"])
def add_to_cart():
    data = load_data()
    body = request.get_json(force=True)

    user_id = int(body.get("user_id"))
    course_id = int(body.get("course_id"))

    user = next((u for u in data["users"] if u["id"] == user_id), None)

    if not user:
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    if course_id in user.get("my_courses", []):
        return jsonify({"status": "error", "message": "Курс уже куплен"}), 400

    if not any(c["id"] == course_id for c in data["courses"]):
        return jsonify({"status": "error", "message": "Курс не найден"}), 404

    cart = data["carts"].setdefault(str(user_id), [])
    if course_id not in cart:
        cart.append(course_id)
        save_data(data)

    return jsonify({"status": "ok"})


@app.route("/api/cart/remove", methods=["POST"])
def remove_from_cart():
    data = load_data()
    body = request.get_json(force=True)

    user_id = str(body.get("user_id"))
    course_id = int(body.get("course_id"))

    cart = data["carts"].setdefault(user_id, [])
    if course_id in cart:
        cart.remove(course_id)
        save_data(data)

    return jsonify({"status": "ok"})


# ------------------------------------------------------------
# БАЛАНС / ПОКУПКА
# ------------------------------------------------------------
@app.route("/api/balance/topup", methods=["POST"])
def balance_topup():
    data = load_data()
    body = request.get_json(force=True)

    user_id = int(body.get("user_id"))
    amount = int(body.get("amount", 0))

    if amount <= 0:
        return jsonify({"status": "error", "message": "Введите корректную сумму"}), 400

    user = next((u for u in data["users"] if u["id"] == user_id), None)
    if not user:
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    user["balance"] += amount
    save_data(data)

    return jsonify({"status": "ok", "user": public_user(user)})


@app.route("/api/purchase", methods=["POST"])
def purchase():
    data = load_data()
    body = request.get_json(force=True)

    user_id = int(body.get("user_id"))
    user = next((u for u in data["users"] if u["id"] == user_id), None)

    if not user:
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    cart = data["carts"].get(str(user_id), [])
    if not cart:
        return jsonify({"status": "error", "message": "Корзина пуста"}), 400

    courses_map = {c["id"]: c for c in data["courses"]}
    total = sum(courses_map[cid]["price"] for cid in cart)

    if user["balance"] < total:
        return jsonify({"status": "error", "message": "Недостаточно средств"}), 400

    # списываем средства
    user["balance"] -= total

    # добавляем купленные курсы
    my = user.setdefault("my_courses", [])
    for cid in cart:
        if cid not in my:
            my.append(cid)

    data["carts"][str(user_id)] = []
    save_data(data)

    return jsonify({"status": "ok", "user": public_user(user)})


@app.route("/api/my-courses/<int:user_id>", methods=["GET"])
def my_courses(user_id):
    data = load_data()

    user = next((u for u in data["users"] if u["id"] == user_id), None)
    if not user:
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    ids = user.get("my_courses", [])
    courses = [c for c in data["courses"] if c["id"] in ids]

    return jsonify({"status": "ok", "courses": courses})


# ------------------------------------------------------------
# ПРОВЕРКА АДМИНА
# ------------------------------------------------------------
def require_admin(user_id, data):
    user = next((u for u in data["users"] if u["id"] == user_id), None)
    if not user or not user.get("is_admin", False):
        return None
    return user


# ------------------------------------------------------------
# АДМИН: ДОБАВЛЕНИЕ КУРСА
# ------------------------------------------------------------
@app.route("/api/admin/add_course", methods=["POST"])
def admin_add_course():
    data = load_data()

    admin_id = int(request.form.get("admin_id"))
    if not require_admin(admin_id, data):
        return jsonify({"status": "error", "message": "Нет доступа"}), 403

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    price = int(request.form.get("price", 0))

    if not title:
        return jsonify({"status": "error", "message": "Название обязательно"}), 400

    # сохраняем фото курса
    image_file = request.files.get("image")
    image_name = None
    if image_file:
        image_name = f"course_{next_id(data['courses'])}_{image_file.filename}"
        image_file.save(os.path.join(COURSE_IMAGE_FOLDER, image_name))

    course = {
        "id": next_id(data["courses"]),
        "title": title,
        "description": description,
        "price": price,
        "image": image_name,
        "lessons": []
    }

    data["courses"].append(course)
    save_data(data)

    return jsonify({"status": "ok", "course": course})


# ------------------------------------------------------------
# АДМИН: ДОБАВЛЕНИЕ УРОКА (ФАЙЛ ВИДЕО)
# ------------------------------------------------------------
@app.route("/api/admin/add_lesson", methods=["POST"])
def admin_add_lesson():
    data = load_data()

    admin_id = int(request.form.get("admin_id"))
    if not require_admin(admin_id, data):
        return jsonify({"status": "error", "message": "Нет доступа"}), 403

    course_id = int(request.form.get("course_id"))
    title = request.form.get("title", "").strip()

    course = next((c for c in data["courses"] if c["id"] == course_id), None)
    if not course:
        return jsonify({"status": "error", "message": "Курс не найден"}), 404

    if not title:
        return jsonify({"status": "error", "message": "Введите название урока"}), 400

    video_file = request.files.get("video")
    video_name = None

    if video_file:
        ext = video_file.filename.split(".")[-1]
        video_name = f"lesson_{course_id}_{len(course['lessons']) + 1}.{ext}"
        video_path = os.path.join(VIDEO_FOLDER, video_name)
        video_file.save(video_path)

    lesson = {
        "id": len(course["lessons"]) + 1,
        "title": title,
        "video": video_name
    }

    course["lessons"].append(lesson)
    save_data(data)

    return jsonify({"status": "ok", "course": course})


# ------------------------------------------------------------
# АВАТАР
# ------------------------------------------------------------
@app.route("/api/upload_avatar/<int:user_id>", methods=["POST"])
def upload_avatar(user_id):
    data = load_data()

    user = next((u for u in data["users"] if u["id"] == user_id), None)
    if not user:
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    file = request.files.get("avatar")
    if not file:
        return jsonify({"status": "error", "message": "Файл не найден"}), 400

    filename = f"user_{user_id}_{file.filename}"
    file.save(os.path.join(AVATAR_FOLDER, filename))

    user["avatar"] = filename
    save_data(data)

    return jsonify({"status": "ok", "user": public_user(user)})


# ------------------------------------------------------------
# РАЗДАЧА ФАЙЛОВ
# ------------------------------------------------------------
@app.route("/uploads/<path:filename>")
def serve_uploads(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/videos/<path:filename>")
def serve_videos(filename):
    return send_from_directory(VIDEO_FOLDER, filename)


# ------------------------------------------------------------
# ЗАПУСК (для Render)
# ------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
