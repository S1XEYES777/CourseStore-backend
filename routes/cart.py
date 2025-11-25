from flask import Blueprint, request, jsonify
import os
import json

cart_bp = Blueprint("cart", __name__, url_prefix="/api/cart")

# ==========================
#  JSON ФАЙЛДАР
# ==========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")

USERS_FILE = os.path.join(DATA_DIR, "users.json")
COURSES_FILE = os.path.join(DATA_DIR, "courses.json")
CART_FILE = os.path.join(DATA_DIR, "cart.json")


# ==========================
#  ВСПОМОГАТЕЛЬНЫЕ
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


def get_course(course_id):
    courses = load_json(COURSES_FILE)
    for c in courses:
        if int(c.get("id")) == int(course_id):
            return c
    return None


def get_user(user_id):
    users = load_json(USERS_FILE)
    for u in users:
        if int(u.get("id")) == int(user_id):
            return u
    return None


# ============================================================
# 📌 Добавить курс в корзину (JSON)
# ============================================================
@cart_bp.post("/add")
def cart_add():
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    course_id = data.get("course_id")

    if not user_id or not course_id:
        return jsonify({"status": "error", "message": "Нет user_id или course_id"}), 400

    # Проверка существования курса
    course = get_course(course_id)
    if not course:
        return jsonify({"status": "error", "message": "Курс не найден"}), 404

    cart = load_json(CART_FILE)

    # Проверка на дубли
    for item in cart:
        if int(item["user_id"]) == int(user_id) and int(item["course_id"]) == int(course_id):
            return jsonify({"status": "error", "message": "Курс уже в корзине"}), 400

    cid = next_id(cart)
    cart.append({
        "id": cid,
        "user_id": int(user_id),
        "course_id": int(course_id)
    })

    save_json(CART_FILE, cart)
    return jsonify({"status": "ok", "cart_id": cid})


# ============================================================
# 📌 Получить корзину пользователя
# ============================================================
@cart_bp.get("")
def cart_get():
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"status": "error", "message": "Нет user_id"}), 400

    cart = load_json(CART_FILE)
    courses = load_json(COURSES_FILE)

    items = []
    total = 0

    for item in cart:
        if int(item["user_id"]) == int(user_id):
            course = get_course(item["course_id"])
            if course:
                total += int(course.get("price", 0))
                items.append({
                    "cart_id": item["id"],
                    "course_id": course["id"],
                    "title": course["title"],
                    "price": course["price"],
                    "author": course["author"],
                    "description": course["description"],
                    "image": course.get("image"),
                })

    return jsonify({"status": "ok", "items": items, "total": total})


# ============================================================
# 📌 Удалить 1 элемент из корзины
# ============================================================
@cart_bp.post("/remove")
def cart_remove():
    data = request.get_json(force=True)
    cart_id = data.get("cart_id")

    if not cart_id:
        return jsonify({"status": "error", "message": "Нет cart_id"}), 400

    cart = load_json(CART_FILE)
    cart = [i for i in cart if int(i["id"]) != int(cart_id)]

    save_json(CART_FILE, cart)
    return jsonify({"status": "ok"})


# ============================================================
# 📌 Купить всё (JSON версия)
# ============================================================
@cart_bp.post("/buy")
def cart_buy():
    data = request.get_json(force=True)
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"status": "error", "message": "Нет user_id"}), 400

    user = get_user(user_id)
    if not user:
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    cart = load_json(CART_FILE)
    courses = load_json(COURSES_FILE)

    # Получаем товары пользователя
    user_cart = [i for i in cart if int(i["user_id"]) == int(user_id)]

    if not user_cart:
        return jsonify({"status": "error", "message": "Корзина пуста"}), 400

    total = 0
    for item in user_cart:
        course = get_course(item["course_id"])
        if course:
            total += int(course.get("price", 0))

    # Проверка баланса
    balance = int(user.get("balance", 0))
    if balance < total:
        return jsonify({"status": "error", "message": "Недостаточно средств"}), 400

    # Списываем деньги
    user["balance"] = balance - total

    # Обновляем пользователей
    users = load_json(USERS_FILE)
    for u in users:
        if int(u["id"]) == int(user_id):
            u["balance"] = user["balance"]
    save_json(USERS_FILE, users)

    # Очищаем корзину
    new_cart = [i for i in cart if int(i["user_id"]) != int(user_id)]
    save_json(CART_FILE, new_cart)

    return jsonify({"status": "ok", "new_balance": user["balance"]})
