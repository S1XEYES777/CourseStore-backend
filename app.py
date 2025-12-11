import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# ============================================================
#  ПАПКИ
# ============================================================
DATA_FILE = "data.json"
UPLOAD_FOLDER = "uploads"
AVATAR_FOLDER = os.path.join(UPLOAD_FOLDER, "avatars")
COURSE_IMAGE_FOLDER = os.path.join(UPLOAD_FOLDER, "course_images")
VIDEO_FOLDER = os.path.join(UPLOAD_FOLDER, "videos")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AVATAR_FOLDER, exist_ok=True)
os.makedirs(COURSE_IMAGE_FOLDER, exist_ok=True)
os.makedirs(VIDEO_FOLDER, exist_ok=True)

app = Flask(__name__)
CORS(app)

# ============================================================
#  JSON БАЗА
# ============================================================
def load_data():
    if not os.path.exists(DATA_FILE):
        data = {"users": [], "courses": [], "carts": {}}
        save_data(data)
        return data
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def next_id(items):
    return max((item["id"] for item in items), default=0) + 1

# ============================================================
#  USER PUBLIC VIEW
# ============================================================
def public_user(u):
    return {
        "id": u["id"],
        "phone": u["phone"],
        "name": u.get("name", ""),
        "balance": u.get("balance", 0),
        "avatar": u.get("avatar"),
        "my_courses": u.get("my_courses", []),
        "is_admin": u.get("is_admin", False)
    }

# ============================================================
#  API STATUS
# ============================================================
@app.route("/api/status")
def status():
    return jsonify({"status": "ok"})

# ============================================================
#  РЕГИСТРАЦИЯ
# ============================================================
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
        "is_admin": is_admin,
        "balance_history": 0
    }

    data["users"].append(user)
    save_data(data)

    return jsonify({"status": "ok", "user": public_user(user)})

# ============================================================
#  ЛОГИН
# ============================================================
@app.route("/api/login", methods=["POST"])
def login():
    data = load_data()
    body = request.get_json(force=True)

    phone = body.get("phone", "").strip()
    password = body.get("password", "").strip()

    for u in data["users"]:
        if u["phone"] == phone and u["password"] == password:
            if phone == "77750476284" and password == "777":
                u["is_admin"] = True
                save_data(data)

            return jsonify({"status": "ok", "user": public_user(u)})

    return jsonify({"status": "error", "message": "Неверный номер или пароль"}), 400

# ============================================================
#  КУРСЫ
# ============================================================
@app.route("/api/courses")
def get_courses():
    return jsonify({"status": "ok", "courses": load_data()["courses"]})

@app.route("/api/course/<int:course_id>")
def get_course(course_id):
    data = load_data()
    course = next((c for c in data["courses"] if c["id"] == course_id), None)
    if not course:
        return jsonify({"status": "error", "message": "Курс не найден"}), 404
    return jsonify({"status": "ok", "course": course})

# ============================================================
#  КОРЗИНА
# ============================================================
@app.route("/api/cart/<int:user_id>")
def get_cart(user_id):
    data = load_data()
    cart = data["carts"].get(str(user_id), [])
    courses = [c for c in data["courses"] if c["id"] in cart]
    return jsonify({"status": "ok", "cart": courses})

@app.route("/api/cart/add", methods=["POST"])
def cart_add():
    data = load_data()
    body = request.get_json(force=True)

    user_id = int(body["user_id"])
    course_id = int(body["course_id"])

    user = next((u for u in data["users"] if u["id"] == user_id), None)
    if not user:
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    if course_id in user.get("my_courses", []):
        return jsonify({"status": "error", "message": "Курс уже куплен"}), 400

    cart = data["carts"].setdefault(str(user_id), [])
    if course_id not in cart:
        cart.append(course_id)

    save_data(data)
    return jsonify({"status": "ok"})

@app.route("/api/cart/remove", methods=["POST"])
def cart_remove():
    data = load_data()
    body = request.get_json(force=True)

    user_id = str(body["user_id"])
    course_id = int(body["course_id"])

    cart = data["carts"].setdefault(user_id, [])
    if course_id in cart:
        cart.remove(course_id)

    save_data(data)
    return jsonify({"status": "ok"})

# ============================================================
#  ПОПОЛНЕНИЕ БАЛАНСА
# ============================================================
@app.route("/api/balance/topup", methods=["POST"])
def balance_topup():
    data = load_data()
    body = request.get_json(force=True)

    user_id = int(body["user_id"])
    amount = int(body["amount"])

    if amount <= 0:
        return jsonify({"status": "error", "message": "Некорректная сумма"}), 400

    user = next((u for u in data["users"] if u["id"] == user_id), None)
    if not user:
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    user["balance"] += amount
    user["balance_history"] = user.get("balance_history", 0) + amount

    save_data(data)
    return jsonify({"status": "ok", "user": public_user(user)})

# ============================================================
#  ПОКУПКА КУРСОВ
# ============================================================
@app.route("/api/purchase", methods=["POST"])
def purchase():
    data = load_data()
    body = request.get_json(force=True)

    user_id = int(body["user_id"])
    user = next((u for u in data["users"] if u["id"] == user_id), None)
    if not user:
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    cart = data["carts"].get(str(user_id), [])
    if not cart:
        return jsonify({"status": "error", "message": "Корзина пуста"}), 400

    courses = {c["id"]: c for c in data["courses"]}
    total = sum(courses[cid]["price"] for cid in cart)

    if user["balance"] < total:
        return jsonify({"status": "error", "message": "Недостаточно средств"}), 400

    user["balance"] -= total

    my = user.setdefault("my_courses", [])
    for cid in cart:
        if cid not in my:
            my.append(cid)

    data["carts"][str(user_id)] = []

    save_data(data)
    return jsonify({"status": "ok", "user": public_user(user)})

# ============================================================
#  МОИ КУРСЫ
# ============================================================
@app.route("/api/my-courses/<int:user_id>")
def my_courses(user_id):
    data = load_data()
    user = next((u for u in data["users"] if u["id"] == user_id), None)

    if not user:
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    ids = user.get("my_courses", [])
    courses = [c for c in data["courses"] if c["id"] in ids]

    return jsonify({"status": "ok", "courses": courses})

# ============================================================
#  ADMIN CHECK
# ============================================================
def require_admin(user_id, data):
    u = next((x for x in data["users"] if x["id"] == user_id), None)
    return u if u and u.get("is_admin") else None

# ============================================================
#  ДОБАВЛЕНИЕ КУРСА
# ============================================================
@app.route("/api/admin/add_course", methods=["POST"])
def admin_add_course():
    data = load_data()

    admin_id = int(request.form.get("admin_id"))
    if not require_admin(admin_id, data):
        return jsonify({"status": "error", "message": "Нет доступа"}), 403

    title = request.form.get("title", "")
    desc = request.form.get("description", "")
    price = int(request.form.get("price", 0))

    course_id = next_id(data["courses"])

    image_file = request.files.get("image")
    image_name = None
    if image_file:
        image_name = f"course_{course_id}_{image_file.filename}"
        image_file.save(os.path.join(COURSE_IMAGE_FOLDER, image_name))

    course = {
        "id": course_id,
        "title": title,
        "description": desc,
        "price": price,
        "image": image_name,
        "lessons": []
    }

    data["courses"].append(course)
    save_data(data)

    return jsonify({"status": "ok", "course": course})

# ============================================================
#  ДОБАВЛЕНИЕ УРОКА
# ============================================================
@app.route("/api/admin/add_lesson", methods=["POST"])
def admin_add_lesson():
    data = load_data()

    admin_id = int(request.form.get("admin_id"))
    course_id = int(request.form.get("course_id"))
    title = request.form.get("title", "")

    if not require_admin(admin_id, data):
        return jsonify({"status": "error", "message": "Нет доступа"}), 403

    course = next((c for c in data["courses"] if c["id"] == course_id), None)
    if not course:
        return jsonify({"status": "error", "message": "Курс не найден"}), 404

    video_file = request.files.get("video")
    video_name = None

    if video_file:
        ext = video_file.filename.split(".")[-1]
        video_name = f"lesson_{course_id}_{len(course['lessons'])+1}.{ext}"
        video_file.save(os.path.join(VIDEO_FOLDER, video_name))

    lesson = {
        "id": len(course["lessons"]) + 1,
        "title": title,
        "video": video_name
    }

    course["lessons"].append(lesson)
    save_data(data)

    return jsonify({"status": "ok"})

# ============================================================
#  УДАЛЕНИЕ КУРСА
# ============================================================
@app.route("/api/admin/delete_course", methods=["POST"])
def delete_course():
    data = load_data()

    admin_id = int(request.form.get("admin_id"))
    course_id = int(request.form.get("course_id"))

    if not require_admin(admin_id, data):
        return jsonify({"status": "error", "message": "Нет доступа"}), 403

    course = next((c for c in data["courses"] if c["id"] == course_id), None)
    if not course:
        return jsonify({"status": "error", "message": "Курс не найден"}), 404

    if course.get("image"):
        try:
            os.remove(os.path.join(COURSE_IMAGE_FOLDER, course["image"]))
        except:
            pass

    for l in course["lessons"]:
        if l.get("video"):
            try:
                os.remove(os.path.join(VIDEO_FOLDER, l["video"]))
            except:
                pass

    for u in data["users"]:
        u["my_courses"] = [cid for cid in u.get("my_courses", []) if cid != course_id]

    for uid in data["carts"]:
        data["carts"][uid] = [cid for cid in data["carts"][uid] if cid != course_id]

    data["courses"] = [c for c in data["courses"] if c["id"] != course_id]

    save_data(data)
    return jsonify({"status": "ok"})

# ============================================================
#  УДАЛЕНИЕ УРОКА
# ============================================================
@app.route("/api/admin/delete_lesson", methods=["POST"])
def delete_lesson():
    data = load_data()

    admin_id = int(request.form.get("admin_id"))
    course_id = int(request.form.get("course_id"))
    lesson_id = int(request.form.get("lesson_id"))

    if not require_admin(admin_id, data):
        return jsonify({"status": "error", "message": "Нет доступа"}), 403

    course = next((c for c in data["courses"] if c["id"] == course_id), None)
    if not course:
        return jsonify({"status": "error", "message": "Курс не найден"}), 404

    lesson = next((l for l in course["lessons"] if l["id"] == lesson_id), None)
    if not lesson:
        return jsonify({"status": "error", "message": "Урок не найден"}), 404

    if lesson.get("video"):
        try:
            os.remove(os.path.join(VIDEO_FOLDER, lesson["video"]))
        except:
            pass

    course["lessons"] = [l for l in course["lessons"] if l["id"] != lesson_id]

    save_data(data)
    return jsonify({"status": "ok"})

# ============================================================
#  АДМИН — АНАЛИТИКА
# ============================================================
@app.route("/api/admin/stats")
def stats():
    data = load_data()

    admin_id = int(request.args.get("admin_id", 0))
    if not require_admin(admin_id, data):
        return jsonify({"status": "error", "message": "Нет доступа"}), 403

    users = len(data["users"])
    revenue = sum(u.get("balance_history", 0) for u in data["users"])

    return jsonify({
        "status": "ok",
        "users": users,
        "revenue": revenue
    })

# ============================================================
#  АДМИН — СПИСОК ПОЛЬЗОВАТЕЛЕЙ
# ============================================================
@app.route("/api/admin/users")
def admin_users():
    data = load_data()

    admin_id = int(request.args.get("admin_id", 0))
    if not require_admin(admin_id, data):
        return jsonify({"status": "error", "message": "Нет доступа"}), 403

    users = []
    for u in data["users"]:
        users.append({
            "id": u["id"],
            "phone": u["phone"],
            "name": u.get("name", ""),
            "balance": u.get("balance", 0),
            "courses": len(u.get("my_courses", [])),
        })

    return jsonify({"status": "ok", "users": users})

# ============================================================
#  АДМИН — УДАЛЕНИЕ ПОЛЬЗОВАТЕЛЯ
# ============================================================
@app.route("/api/admin/delete_user", methods=["POST"])
def delete_user():
    data = load_data()

    admin_id = int(request.form.get("admin_id"))
    user_id = int(request.form.get("user_id"))

    if not require_admin(admin_id, data):
        return jsonify({"status": "error", "message": "Нет доступа"}), 403

    user = next((u for u in data["users"] if u["id"] == user_id), None)
    if not user:
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    if user.get("avatar"):
        try:
            os.remove(os.path.join(AVATAR_FOLDER, user["avatar"]))
        except:
            pass

    if str(user_id) in data["carts"]:
        del data["carts"][str(user_id)]

    data["users"] = [u for u in data["users"] if u["id"] != user_id]

    save_data(data)
    return jsonify({"status": "ok"})

# ============================================================
#  ЗАГРУЗКА АВАТАРА
# ============================================================
@app.route("/api/upload_avatar/<int:user_id>", methods=["POST"])
def upload_avatar(user_id):
    data = load_data()

    u = next((x for x in data["users"] if x["id"] == user_id), None)
    if not u:
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    file = request.files.get("avatar")
    if not file:
        return jsonify({"status": "error", "message": "Файл не найден"}), 400

    filename = f"user_{user_id}_{file.filename}"
    file.save(os.path.join(AVATAR_FOLDER, filename))

    u["avatar"] = filename
    save_data(data)

    return jsonify({"status": "ok", "user": public_user(u)})

# ============================================================
#  РАЗДАЧА ФАЙЛОВ
# ============================================================
@app.route("/uploads/<path:path>")
def serve_uploads(path):
    return send_from_directory(UPLOAD_FOLDER, path)

@app.route("/videos/<path:path>")
def serve_videos(path):
    return send_from_directory(VIDEO_FOLDER, path)

# ============================================================
#  RUN
# ============================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
