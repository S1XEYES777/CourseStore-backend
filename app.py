import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ================================
#   ПАПКИ
# ================================
BASE_DIR = os.getcwd()
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
VIDEO_FOLDER = os.path.join(UPLOAD_FOLDER, "videos")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(VIDEO_FOLDER, exist_ok=True)

# ================================
#   JSON-функции
# ================================
def load(filename):
    if not os.path.exists(filename):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=4)
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

def save(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ================================
#   ФАЙЛЫ
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
    data = request.json or {}
    name = data.get("name")
    phone = data.get("phone")
    password = data.get("password")

    if not name or not phone or not password:
        return jsonify({"status": "error", "message": "Заполните все поля"})

    users = load(USERS)

    # Номер занят
    for u in users:
        if u["phone"] == phone:
            return jsonify({"status": "error", "message": "Номер уже зарегистрирован"})

    new_user = {
        "id": len(users) + 1,
        "name": name,
        "phone": phone,
        "password": password,
        "avatar": None,
        "balance": 0
    }

    users.append(new_user)
    save(USERS, users)

    return jsonify({"status": "ok", "user": new_user})

# ================================
# LOGIN
# ================================
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    phone = data.get("phone")
    password = data.get("password")

    users = load(USERS)

    for u in users:
        if u["phone"] == phone and u["password"] == password:
            return jsonify({"status": "ok", "user": u})

    return jsonify({"status": "error", "message": "Неверный логин или пароль"})

# ================================
# АВАТАР
# ================================
@app.route("/api/upload_avatar/<int:user_id>", methods=["POST"])
def upload_avatar(user_id):
    users = load(USERS)
    file = request.files.get("avatar")

    if not file:
        return jsonify({"status": "error", "message": "Нет файла"})

    filename = f"avatar_{user_id}_{file.filename}"
    file.save(os.path.join(UPLOAD_FOLDER, filename))

    for u in users:
        if u["id"] == user_id:
            u["avatar"] = filename
            break

    save(USERS, users)

    return jsonify({"status": "ok", "url": f"/uploads/{filename}"})

# ================================
# ДОБАВИТЬ КУРС
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

    filename = f"course_{len(courses)+1}_{file.filename}"
    file.save(os.path.join(UPLOAD_FOLDER, filename))

    course = {
        "id": len(courses) + 1,
        "title": title,
        "price": int(price),
        "author": author,
        "description": description,
        "image": filename
    }

    courses.append(course)
    save(COURSES, courses)

    return jsonify({"status": "ok"})

# ================================
# СПИСОК КУРСОВ
# ================================
@app.route("/api/courses")
def get_courses():
    return jsonify(load(COURSES))

# ================================
# УДАЛИТЬ КУРС
# ================================
@app.route("/api/delete_course/<int:cid>", methods=["DELETE"])
def delete_course(cid):
    courses = load(COURSES)
    courses = [c for c in courses if c["id"] != cid]
    save(COURSES, courses)
    return jsonify({"status": "ok"})

# ================================
# ДОБАВИТЬ В КОРЗИНУ
# ================================
@app.route("/api/cart/add", methods=["POST"])
def cart_add():
    data = request.json
    cart = load(CART)

    # не добавляем дубликаты
    for item in cart:
        if item["user_id"] == data["user_id"] and item["course_id"] == data["course_id"]:
            return jsonify({"status": "ok"})

    cart.append(data)
    save(CART, cart)

    return jsonify({"status": "ok"})

# ================================
# УДАЛИТЬ ИЗ КОРЗИНЫ
# ================================
@app.route("/api/cart/remove", methods=["POST"])
def cart_remove():
    data = request.json
    cart = load(CART)

    cart = [
        c for c in cart
        if not (c["user_id"] == data["user_id"] and c["course_id"] == data["course_id"])
    ]

    save(CART, cart)
    return jsonify({"status": "ok"})

# ================================
# КОРЗИНА ПОЛЬЗОВАТЕЛЯ
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
# ПОПОЛНЕНИЕ БАЛАНСА
# ================================
@app.route("/api/add_balance/<int:user_id>", methods=["POST"])
def add_balance(user_id):
    data = request.json
    amount = int(data.get("amount", 0))

    if amount <= 0:
        return jsonify({"status": "error", "message": "Сумма должна быть > 0"})

    users = load(USERS)

    for u in users:
        if u["id"] == user_id:
            u["balance"] += amount
            save(USERS, users)
            return jsonify({"status": "ok", "balance": u["balance"]})

    return jsonify({"status": "error", "message": "Пользователь не найден"})

# ================================
# ПОКУПКА (ТОЛЬКО ЕСЛИ ДЕНЕГ ХВАТАЕТ)
# ================================
@app.route("/api/cart/checkout/<int:user_id>", methods=["POST"])
def checkout(user_id):
    cart = load(CART)
    purchases = load(PURCHASES)
    courses = load(COURSES)
    users = load(USERS)

    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return jsonify({"status": "error", "message": "Пользователь не найден"})

    balance = user["balance"]

    # позиции из корзины
    user_cart = [c for c in cart if c["user_id"] == user_id]

    if not user_cart:
        return jsonify({"status": "error", "message": "Корзина пуста"})

    # считаем сумму новых покупок
    total = 0
    for item in user_cart:
        course = next((x for x in courses if x["id"] == item["course_id"]), None)
        already = any(
            p["user_id"] == user_id and p["course_id"] == course["id"]
            for p in purchases
        )
        if not already:
            total += int(course["price"])

    if balance < total:
        return jsonify({"status": "error", "message": "Недостаточно средств"})

    # списываем деньги
    user["balance"] -= total

    # сохраняем покупки
    for item in user_cart:
        if not any(
            p["user_id"] == user_id and p["course_id"] == item["course_id"]
            for p in purchases
        ):
            purchases.append({"user_id": user_id, "course_id": item["course_id"]})

    # очищаем корзину
    cart = [c for c in cart if c["user_id"] != user_id]

    save(USERS, users)
    save(PURCHASES, purchases)
    save(CART, cart)

    return jsonify({"status": "ok", "balance": user["balance"]})

# ================================
# СПИСОК КУПЛЕННЫХ КУРСОВ
# ================================
@app.route("/api/purchases/<int:user_id>")
def get_purchases(user_id):
    purchases = load(PURCHASES)
    courses = load(COURSES)

    owned = []
    for p in purchases:
        if p["user_id"] == user_id:
            course = next((x for x in courses if x["id"] == p["course_id"]), None)
            if course:
                owned.append(course)

    return jsonify(owned)

# ================================
# ЗАГРУЗКА ВИДЕО УРОКА
# ================================
@app.route("/api/upload_lesson", methods=["POST"])
def upload_lesson():
    lessons = load(LESSONS)

    course_id = request.form.get("course_id")
    title = request.form.get("title")
    file = request.files.get("file")

    if not file:
        return jsonify({"status": "error", "message": "Нет видео"})

    folder = os.path.join(VIDEO_FOLDER, str(course_id))
    os.makedirs(folder, exist_ok=True)

    filepath = os.path.join(folder, file.filename)
    file.save(filepath)

    lessons.append({
        "id": len(lessons) + 1,
        "course_id": int(course_id),
        "title": title,
        "filename": file.filename
    })

    save(LESSONS, lessons)
    return jsonify({"status": "ok"})

# ================================
# ПОЛУЧИТЬ УРОКИ (ТОЛЬКО ПОСЛЕ ПОКУПКИ)
# ================================
@app.route("/api/get_lessons")
def get_lessons():
    cid = int(request.args.get("course_id"))
    uid = int(request.args.get("user_id"))

    purchases = load(PURCHASES)
    lessons = load(LESSONS)

    owned = any(p["user_id"] == uid and p["course_id"] == cid for p in purchases)

    if not owned:
        return jsonify({"status": "error", "message": "not purchased"}), 403

    result = [
        {
            "title": l["title"],
            "url": f"/videos/{cid}/{l['filename']}"
        }
        for l in lessons if l["course_id"] == cid
    ]

    return jsonify({"status": "ok", "lessons": result})

# ================================
# ОТДАЧА ВИДЕО
# ================================
@app.route("/videos/<cid>/<filename>")
def serve_video(cid, filename):
    folder = os.path.join(VIDEO_FOLDER, str(cid))
    return send_from_directory(folder, filename)

# ================================
# ОТДАЧА ФОТО
# ================================
@app.route("/uploads/<filename>")
def serve_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ================================
# RUN
# ================================
if __name__ == "__main__":
    app.run(debug=True)
