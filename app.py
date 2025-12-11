import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ================================
# ПАПКИ ДЛЯ ФАЙЛОВ
# ================================
BASE_DIR = os.getcwd()
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
VIDEO_FOLDER = os.path.join(UPLOAD_FOLDER, "videos")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(VIDEO_FOLDER, exist_ok=True)


# ================================
# JSON ФУНКЦИИ
# ================================
def load(filename):
    """Читаем JSON, если нет — создаём пустой список."""
    if not os.path.exists(filename):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=4)
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)


def save(filename, data):
    """Сохраняем список в JSON."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# ================================
# "БАЗА ДАННЫХ" (ФАЙЛЫ)
# ================================
USERS = "users.json"
COURSES = "courses.json"
CART = "cart.json"
PURCHASES = "purchases.json"
LESSONS = "lessons.json"


# ================================
# REGISTRATION
# ================================
@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    users = load(USERS)

    # Проверка телефона
    for u in users:
        if u["phone"] == data["phone"]:
            return jsonify({"status": "error", "message": "Номер занят"})

    new_user = {
        "id": len(users) + 1,
        "name": data["name"],
        "phone": data["phone"],
        "password": data["password"],
        "avatar": None,   # имя файла аватарки
        "balance": 0      # баланс в тенге
    }

    users.append(new_user)
    save(USERS, users)

    return jsonify({"status": "ok", "user": new_user})


# ================================
# LOGIN
# ================================
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    users = load(USERS)

    for u in users:
        if u["phone"] == data["phone"] and u["password"] == data["password"]:
            return jsonify({"status": "ok", "user": u})

    return jsonify({"status": "error", "message": "Неверный логин или пароль"})


# ================================
# UPLOAD AVATAR
# ================================
@app.route("/api/upload_avatar/<int:user_id>", methods=["POST"])
def upload_avatar(user_id):
    file = request.files.get("avatar")
    if not file:
        return jsonify({"status": "error", "message": "Файл не найден"})

    # уникальное имя файла
    filename = f"user_{user_id}_{file.filename}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    users = load(USERS)
    found = False
    for u in users:
        if u["id"] == user_id:
            u["avatar"] = filename
            found = True
            break

    if not found:
        return jsonify({"status": "error", "message": "User not found"})

    save(USERS, users)
    # фронт ожидает поле url вида "/uploads/filename"
    return jsonify({"status": "ok", "url": f"/uploads/{filename}"})


# ================================
# ADD COURSE (ADMIN)
# ================================
@app.route("/api/add_course", methods=["POST"])
def add_course():
    courses = load(COURSES)

    title = request.form.get("title")
    price = request.form.get("price")
    author = request.form.get("author")
    description = request.form.get("description")
    file = request.files.get("image")

    if not file:
        return jsonify({"status": "error", "message": "Нет изображения"})

    try:
        price_int = int(price)
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Неверная цена"})

    filename = f"course_{len(courses) + 1}_{file.filename}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    course = {
        "id": len(courses) + 1,
        "title": title,
        "price": price_int,
        "author": author,
        "description": description,
        "image": filename
    }

    courses.append(course)
    save(COURSES, courses)

    return jsonify({"status": "ok"})


# ================================
# GET COURSES
# ================================
@app.route("/api/courses")
def get_courses():
    return jsonify(load(COURSES))


# ================================
# DELETE COURSE (ADMIN)
# ================================
@app.route("/api/delete_course/<int:cid>", methods=["DELETE"])
def delete_course(cid):
    courses = load(COURSES)
    courses = [c for c in courses if c["id"] != cid]
    save(COURSES, courses)
    return jsonify({"status": "ok"})


# ================================
# CART: ADD ITEM
# ================================
@app.route("/api/cart/add", methods=["POST"])
def cart_add():
    data = request.json
    user_id = data.get("user_id")
    course_id = data.get("course_id")

    cart = load(CART)

    # не добавлять дубликаты
    for item in cart:
        if item["user_id"] == user_id and item["course_id"] == course_id:
            return jsonify({"status": "ok"})

    cart.append({"user_id": user_id, "course_id": course_id})
    save(CART, cart)

    return jsonify({"status": "ok"})


# ================================
# CART: REMOVE ITEM
# ================================
@app.route("/api/cart/remove", methods=["POST"])
def cart_remove():
    data = request.json
    user_id = data["user_id"]
    course_id = data["course_id"]

    cart = load(CART)
    cart = [c for c in cart if not (c["user_id"] == user_id and c["course_id"] == course_id)]
    save(CART, cart)

    return jsonify({"status": "ok"})


# ================================
# CART: GET ITEMS
# ================================
@app.route("/api/cart/<int:user_id>")
def get_cart(user_id):
    cart = load(CART)
    courses = load(COURSES)

    items = []
    for c in cart:
        if c["user_id"] == user_id:
            course = next((x for x in courses if x["id"] == c["course_id"]), None)
            if course:
                items.append(course)

    return jsonify(items)


# ================================
# BALANCE: ADD MONEY
# ================================
@app.route("/api/balance/<int:user_id>", methods=["POST"])
def add_balance(user_id):
    data = request.json or {}
    amount = data.get("amount", 0)

    try:
        amount = int(amount)
    except (TypeError, ValueError):
        amount = 0

    if amount <= 0:
        return jsonify({"status": "error", "message": "Неверная сумма"})

    users = load(USERS)
    for u in users:
        if u["id"] == user_id:
            if "balance" not in u:
                u["balance"] = 0
            u["balance"] += amount
            save(USERS, users)
            return jsonify({"status": "ok", "balance": u["balance"]})

    return jsonify({"status": "error", "message": "User not found"})


# ================================
# CHECKOUT (СПИСАНИЕ С БАЛАНСА)
# ================================
@app.route("/api/cart/checkout/<int:user_id>", methods=["POST"])
def checkout(user_id):
    cart = load(CART)
    purchases = load(PURCHASES)
    users = load(USERS)
    courses = load(COURSES)

    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return jsonify({"status": "error", "message": "User not found"})

    if "balance" not in user:
        user["balance"] = 0

    # считаем сумму всех курсов в корзине этого пользователя
    total = 0
    for item in cart:
        if item["user_id"] == user_id:
            course = next((c for c in courses if c["id"] == item["course_id"]), None)
            if course:
                total += course["price"]

    if total == 0:
        return jsonify({"status": "error", "message": "В корзине ничего нет"})

    if user["balance"] < total:
        return jsonify({"status": "error", "message": "Недостаточно денег"})

    # списываем деньги
    user["balance"] -= total
    save(USERS, users)

    # добавляем покупки (user_id, course_id)
    for item in cart:
        if item["user_id"] == user_id:
            purchases.append(item)

    # очищаем корзину этого пользователя
    cart = [c for c in cart if c["user_id"] != user_id]

    save(PURCHASES, purchases)
    save(CART, cart)

    return jsonify({"status": "ok", "balance": user["balance"]})


# ================================
# PURCHASES: GET USER COURSES
# ================================
@app.route("/api/purchases/<int:user_id>")
def get_purchases(user_id):
    purchases = load(PURCHASES)
    courses = load(COURSES)

    owned = []
    for p in purchases:
        if p["user_id"] == user_id:
            course = next((x for x in courses if x["id"] == p["course_id"]), None)
            if course and course not in owned:
                owned.append(course)

    return jsonify(owned)


# ================================
# UPLOAD LESSON (VIDEO)
# ================================
@app.route("/api/upload_lesson", methods=["POST"])
def upload_lesson():
    lessons = load(LESSONS)

    course_id = request.form.get("course_id")
    title = request.form.get("title")
    file = request.files.get("file")

    if not file or not course_id:
        return jsonify({"status": "error", "message": "Нет файла или course_id"})

    folder = os.path.join(VIDEO_FOLDER, str(course_id))
    os.makedirs(folder, exist_ok=True)

    filename = f"lesson_{len(lessons) + 1}_{file.filename}"
    filepath = os.path.join(folder, filename)
    file.save(filepath)

    lesson = {
        "id": len(lessons) + 1,
        "course_id": int(course_id),
        "title": title,
        "filename": filename
    }

    lessons.append(lesson)
    save(LESSONS, lessons)

    return jsonify({"status": "ok"})


# ================================
# GET LESSONS (ONLY IF PURCHASED)
# ================================
@app.route("/api/get_lessons")
def get_lessons():
    cid = int(request.args.get("course_id"))
    uid = int(request.args.get("user_id"))

    purchases = load(PURCHASES)
    lessons = load(LESSONS)

    # есть ли покупка
    if not any(p["user_id"] == uid and p["course_id"] == cid for p in purchases):
        return jsonify({"status": "error", "message": "not purchased"}), 403

    course_lessons = [
        {"title": l["title"], "url": f"/videos/{cid}/{l['filename']}"}
        for l in lessons if l["course_id"] == cid
    ]

    return jsonify({"status": "ok", "lessons": course_lessons})


# ================================
# ВИДЕО И КАРТИНКИ
# ================================
@app.route("/videos/<cid>/<filename>")
def serve_video(cid, filename):
    folder = os.path.join(VIDEO_FOLDER, cid)
    return send_from_directory(folder, filename)


@app.route("/uploads/<filename>")
def serve_image(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ================================
# ROOT (необязательно)
# ================================
@app.route("/")
def root():
    return "CourseStore backend is running"


# ================================
# RUN (локально)
# ================================
if __name__ == "__main__":
    app.run(debug=True)
