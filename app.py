import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# -----------------------
# НАСТРОЙКИ
# -----------------------
DATA_FILE = "data.json"
UPLOAD_FOLDER = "uploads"
AVATAR_FOLDER = os.path.join(UPLOAD_FOLDER, "avatars")
COURSE_IMAGE_FOLDER = os.path.join(UPLOAD_FOLDER, "course_images")

os.makedirs(AVATAR_FOLDER, exist_ok=True)
os.makedirs(COURSE_IMAGE_FOLDER, exist_ok=True)

app = Flask(__name__)
CORS(app)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# -----------------------
# ФУНКЦИИ РАБОТЫ С ФАЙЛОМ
# -----------------------
def load_data():
    if not os.path.exists(DATA_FILE):
        data = {
            "users": [],
            "courses": [],
            "carts": {}  # user_id -> [course_id, ...]
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


# -----------------------
# ВСПОМОГАТЕЛЬНОЕ
# -----------------------
def public_user(user):
    # что отправляем на фронт
    return {
        "id": user["id"],
        "phone": user["phone"],
        "name": user.get("name", ""),
        "balance": user.get("balance", 0),
        "avatar": user.get("avatar"),
        "my_courses": user.get("my_courses", []),
        "is_admin": user.get("is_admin", False),
    }


# -----------------------
# СЕРВИСНЫЕ МАРШРУТЫ
# -----------------------
@app.route("/api/status")
def status():
    return jsonify({"status": "ok"})


# -----------------------
# РЕГИСТРАЦИЯ / ЛОГИН
# -----------------------
@app.route("/api/register", methods=["POST"])
def register():
    data = load_data()
    body = request.get_json(force=True)

    phone = body.get("phone", "").strip()
    password = body.get("password", "").strip()
    name = body.get("name", "").strip() or "Пользователь"

    if not phone or not password:
        return jsonify({"status": "error", "message": "Телефон и пароль обязательны"}), 400

    if any(u["phone"] == phone for u in data["users"]):
        return jsonify({"status": "error", "message": "Такой телефон уже зарегистрирован"}), 400

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
        "is_admin": is_admin,
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
            # админ, если совпадают
            if phone == "77750476284" and password == "777":
                u["is_admin"] = True
                save_data(data)
            return jsonify({"status": "ok", "user": public_user(u)})

    return jsonify({"status": "error", "message": "Неверный телефон или пароль"}), 400


# -----------------------
# КУРСЫ
# -----------------------
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


# -----------------------
# КОРЗИНА
# -----------------------
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

    user_id = int(body.get("user_id", 0))
    course_id = int(body.get("course_id", 0))

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

    user_id = int(body.get("user_id", 0))
    course_id = int(body.get("course_id", 0))

    cart = data["carts"].setdefault(str(user_id), [])
    if course_id in cart:
        cart.remove(course_id)
        save_data(data)

    return jsonify({"status": "ok"})


# -----------------------
# БАЛАНС И ПОКУПКА
# -----------------------
@app.route("/api/balance/topup", methods=["POST"])
def balance_topup():
    data = load_data()
    body = request.get_json(force=True)

    user_id = int(body.get("user_id", 0))
    amount = int(body.get("amount", 0))

    user = next((u for u in data["users"] if u["id"] == user_id), None)
    if not user:
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    if amount <= 0:
        return jsonify({"status": "error", "message": "Некорректная сумма"}), 400

    user["balance"] = user.get("balance", 0) + amount
    save_data(data)

    return jsonify({"status": "ok", "user": public_user(user)})


@app.route("/api/purchase", methods=["POST"])
def purchase():
    data = load_data()
    body = request.get_json(force=True)

    user_id = int(body.get("user_id", 0))
    user = next((u for u in data["users"] if u["id"] == user_id), None)
    if not user:
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    cart_ids = data["carts"].get(str(user_id), [])
    if not cart_ids:
        return jsonify({"status": "error", "message": "Корзина пуста"}), 400

    courses_map = {c["id"]: c for c in data["courses"]}
    total = sum(courses_map[cid]["price"] for cid in cart_ids if cid in courses_map)

    if user.get("balance", 0) < total:
        return jsonify({"status": "error", "message": "Недостаточно средств"}), 400

    user["balance"] -= total
    my = user.setdefault("my_courses", [])
    for cid in cart_ids:
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

    my_ids = user.get("my_courses", [])
    courses = [c for c in data["courses"] if c["id"] in my_ids]

    return jsonify({"status": "ok", "courses": courses})


# -----------------------
# АДМИН: КУРСЫ
# -----------------------
def require_admin(user_id, data):
    user = next((u for u in data["users"] if u["id"] == user_id), None)
    if not user or not user.get("is_admin", False):
        return None
    return user


@app.route("/api/admin/add_course", methods=["POST"])
def admin_add_course():
    data = load_data()

    admin_id = int(request.form.get("admin_id", 0))
    if not require_admin(admin_id, data):
        return jsonify({"status": "error", "message": "Нет прав"}), 403

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    price = int(request.form.get("price", 0))

    if not title:
        return jsonify({"status": "error", "message": "Название обязательно"}), 400

    image_file = request.files.get("image")
    image_name = None
    if image_file:
        image_name = f"course_{next_id(data['courses'])}_{image_file.filename}"
        path = os.path.join(COURSE_IMAGE_FOLDER, image_name)
        image_file.save(path)

    course_id = next_id(data["courses"])
    course = {
        "id": course_id,
        "title": title,
        "description": description,
        "price": price,
        "image": image_name,  # хранится имя файла
        "lessons": []  # список уроков
    }
    data["courses"].append(course)
    save_data(data)

    return jsonify({"status": "ok", "course": course})


@app.route("/api/admin/add_lesson", methods=["POST"])
def admin_add_lesson():
    data = load_data()

    admin_id = int(request.form.get("admin_id", 0))
    if not require_admin(admin_id, data):
        return jsonify({"status": "error", "message": "Нет прав"}), 403

    course_id = int(request.form.get("course_id", 0))
    title = request.form.get("title", "").strip()
    video_url = request.form.get("video_url", "").strip()  # можно просто ссылку на YouTube

    course = next((c for c in data["courses"] if c["id"] == course_id), None)
    if not course:
        return jsonify({"status": "error", "message": "Курс не найден"}), 404

    if not title:
        return jsonify({"status": "error", "message": "Название урока обязательно"}), 400

    lesson_id = len(course["lessons"]) + 1
    course["lessons"].append({
        "id": lesson_id,
        "title": title,
        "video_url": video_url,
    })

    save_data(data)
    return jsonify({"status": "ok", "course": course})


# -----------------------
# АВАТАР
# -----------------------
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
    path = os.path.join(AVATAR_FOLDER, filename)
    file.save(path)

    user["avatar"] = filename
    save_data(data)

    return jsonify({"status": "ok", "user": public_user(user)})


# -----------------------
# РАЗДАЧА ФАЙЛОВ
# -----------------------
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
