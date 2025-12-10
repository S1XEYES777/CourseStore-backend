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
#   REGISTRATION
# ================================
@app.route("/api/register", methods=["POST"])
def register():
    data = request.json or {}
    users = load(USERS)

    phone = data.get("phone")
    name = data.get("name")
    password = data.get("password")

    if not phone or not name or not password:
        return jsonify({"status": "error", "message": "Заполните все поля"})

    # проверка номера
    for u in users:
        if u.get("phone") == phone:
            return jsonify({"status": "error", "message": "Номер занят"})

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
#   LOGIN
# ================================
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    phone = data.get("phone")
    password = data.get("password")

    users = load(USERS)

    for u in users:
        if u.get("phone") == phone and u.get("password") == password:
            # если старый user без баланса — добавим
            if "balance" not in u:
                u["balance"] = 0
                save(USERS, users)
            return jsonify({"status": "ok", "user": u})

    return jsonify({"status": "error", "message": "Неверный логин или пароль"})

# ================================
#   АВАТАР
# ================================
@app.route("/api/upload_avatar/<int:user_id>", methods=["POST"])
def upload_avatar(user_id):
    users = load(USERS)
    file = request.files.get("avatar")

    if not file:
        return jsonify({"status": "error", "message": "Файл не передан"})

    # имя файла
    filename = f"avatar_{user_id}_{file.filename}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    # обновляем пользователя
    updated = False
    for u in users:
        if u.get("id") == user_id:
            u["avatar"] = filename
            updated = True
            break

    if not updated:
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    save(USERS, users)
    return jsonify({"status": "ok", "url": f"/uploads/{filename}"})

# ================================
#   ADD COURSE (ADMIN)
# ================================
@app.route("/api/add_course", methods=["POST"])
def add_course():
    courses = load(COURSES)

    title = request.form.get("title")
    price = request.form.get("price")
    author = request.form.get("author")
    description = request.form.get("description")
    file = request.files.get("image")

    if not all([title, price, author, description]):
        return jsonify({"status": "error", "message": "Заполните все поля курса"})

    if not file:
        return jsonify({"status": "error", "message": "Нет изображения"})

    filename = f"course_{len(courses) + 1}_{file.filename}"
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
#   GET COURSES
# ================================
@app.route("/api/courses")
def get_courses():
    return jsonify(load(COURSES))

# ================================
#   DELETE COURSE
# ================================
@app.route("/api/delete_course/<int:cid>", methods=["DELETE"])
def delete_course(cid):
    courses = load(COURSES)
    courses = [c for c in courses if c.get("id") != cid]
    save(COURSES, courses)
    return jsonify({"status": "ok"})

# ================================
#   CART: ADD
# ================================
@app.route("/api/cart/add", methods=["POST"])
def cart_add():
    data = request.json or {}
    user_id = data.get("user_id")
    course_id = data.get("course_id")

    if not user_id or not course_id:
        return jsonify({"status": "error", "message": "Нет user_id или course_id"})

    cart = load(CART)

    # не добавляем дубликаты
    for item in cart:
        if item.get("user_id") == user_id and item.get("course_id") == course_id:
            return jsonify({"status": "ok"})

    cart.append({"user_id": user_id, "course_id": course_id})
    save(CART, cart)

    return jsonify({"status": "ok"})

# ================================
#   CART: REMOVE
# ================================
@app.route("/api/cart/remove", methods=["POST"])
def cart_remove():
    data = request.json or {}
    user_id = data.get("user_id")
    course_id = data.get("course_id")

    if not user_id or not course_id:
        return jsonify({"status": "error", "message": "Нет user_id или course_id"})

    cart = load(CART)
    cart = [c for c in cart if not (c.get("user_id") == user_id and c.get("course_id") == course_id)]
    save(CART, cart)

    return jsonify({"status": "ok"})

# ================================
#   GET CART ITEMS (как карточки)
# ================================
@app.route("/api/cart/<int:user_id>")
def get_cart(user_id):
    cart = load(CART)
    courses = load(COURSES)

    items = []
    for c in cart:
        if c.get("user_id") == user_id:
            course = next((x for x in courses if x.get("id") == c.get("course_id")), None)
            if course:
                items.append(course)

    return jsonify(items)

# ================================
#   BALANCE: GET
# ================================
@app.route("/api/balance/<int:user_id>")
def get_balance(user_id):
    users = load(USERS)
    user = next((u for u in users if u.get("id") == user_id), None)
    if not user:
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    balance = user.get("balance", 0)
    return jsonify({"status": "ok", "balance": balance})

# ================================
#   BALANCE: ADD (пополнение)
# ================================
@app.route("/api/add_balance/<int:user_id>", methods=["POST"])
def add_balance(user_id):
    data = request.json or {}
    amount = int(data.get("amount", 0))

    if amount <= 0:
        return jsonify({"status": "error", "message": "Сумма должна быть больше 0"})

    users = load(USERS)
    user = next((u for u in users if u.get("id") == user_id), None)

    if not user:
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    user["balance"] = int(user.get("balance", 0)) + amount
    save(USERS, users)

    return jsonify({"status": "ok", "balance": user["balance"]})

# ================================
#   CHECKOUT (покупка за баланс)
# ================================
@app.route("/api/cart/checkout/<int:user_id>", methods=["POST"])
def checkout(user_id):
    cart = load(CART)
    purchases = load(PURCHASES)
    courses = load(COURSES)
    users = load(USERS)

    user = next((u for u in users if u.get("id") == user_id), None)
    if not user:
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    balance = int(user.get("balance", 0))

    # все позиции пользователя
    user_cart = [c for c in cart if c.get("user_id") == user_id]
    if not user_cart:
        return jsonify({"status": "error", "message": "Корзина пуста"})

    # считаем сумму
    total = 0
    for item in user_cart:
        course = next((x for x in courses if x.get("id") == item.get("course_id")), None)
        if course:
            total += int(course.get("price", 0))

    if balance < total:
        return jsonify({"status": "error", "message": "Недостаточно средств"})

    # списываем деньги
    user["balance"] = balance - total

    # добавляем покупки (без дублей)
    for item in user_cart:
        if not any(p.get("user_id") == item.get("user_id") and p.get("course_id") == item.get("course_id") for p in purchases):
            purchases.append(item)

    # очищаем корзину пользователя
    cart = [c for c in cart if c.get("user_id") != user_id]

    save(PURCHASES, purchases)
    save(CART, cart)
    save(USERS, users)

    return jsonify({"status": "ok", "balance": user["balance"]})

# ================================
#   GET PURCHASES
# ================================
@app.route("/api/purchases/<int:user_id>")
def get_purchases(user_id):
    purchases = load(PURCHASES)
    courses = load(COURSES)

    owned = []
    for p in purchases:
        if p.get("user_id") == user_id:
            course = next((x for x in courses if x.get("id") == p.get("course_id")), None)
            if course:
                owned.append(course)

    return jsonify(owned)

# ================================
#   UPLOAD LESSON (VIDEO)
# ================================
@app.route("/api/upload_lesson", methods=["POST"])
def upload_lesson():
    lessons = load(LESSONS)

    course_id = request.form.get("course_id")
    title = request.form.get("title")
    file = request.files.get("file")

    if not course_id or not title or not file:
        return jsonify({"status": "error", "message": "Заполните все поля и выберите файл"})

    folder = os.path.join(VIDEO_FOLDER, str(course_id))
    os.makedirs(folder, exist_ok=True)

    filepath = os.path.join(folder, file.filename)
    file.save(filepath)

    lesson = {
        "id": len(lessons) + 1,
        "course_id": int(course_id),
        "title": title,
        "filename": file.filename
    }

    lessons.append(lesson)
    save(LESSONS, lessons)

    return jsonify({"status": "ok"})

# ================================
#   GET LESSONS (ONLY IF PURCHASED)
# ================================
@app.route("/api/get_lessons")
def get_lessons():
    cid = int(request.args.get("course_id"))
    uid = int(request.args.get("user_id"))

    purchases = load(PURCHASES)
    lessons = load(LESSONS)

    # проверка покупки
    if not any(p.get("user_id") == uid and p.get("course_id") == cid for p in purchases):
        return jsonify({"status": "error", "message": "not purchased"}), 403

    course_lessons = [
        {
            "title": l.get("title"),
            "url": f"/videos/{cid}/{l.get('filename')}"
        }
        for l in lessons if l.get("course_id") == cid
    ]

    return jsonify({"status": "ok", "lessons": course_lessons})

# ================================
#   VIDEO FILE SERVE
# ================================
@app.route("/videos/<cid>/<filename>")
def serve_video(cid, filename):
    folder = os.path.join(VIDEO_FOLDER, str(cid))
    return send_from_directory(folder, filename)

# ================================
#   STATIC UPLOAD FILES
# ================================
@app.route("/uploads/<filename>")
def serve_image(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ================================
#   RUN
# ================================
if __name__ == "__main__":
    app.run(debug=True)
