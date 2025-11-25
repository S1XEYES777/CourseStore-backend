from flask import Blueprint, request, jsonify
import os
import json

users_bp = Blueprint("users", __name__)

# ============================================================
# JSON FILES
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")

USERS_FILE = os.path.join(DATA_DIR, "users.json")
CART_FILE = os.path.join(DATA_DIR, "cart.json")
REVIEWS_FILE = os.path.join(DATA_DIR, "reviews.json")
PURCHASES_FILE = os.path.join(DATA_DIR, "purchases.json")


# ============================================================
# HELPERS
# ============================================================
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
    return max(int(i.get("id", 0)) for i in items) + 1


# ============================================================
# 📌 INTERNAL: получить всех пользователей
# ============================================================
def get_all_users():
    users = load_json(USERS_FILE)
    return users


# ============================================================
# 📌 API: список пользователей
# ============================================================
@users_bp.get("/api/users")
def api_get_users():
    return jsonify({"status": "ok", "users": get_all_users()})


# ============================================================
# 📌 API: обновление пользователя
# ============================================================
@users_bp.post("/api/users/update")
def api_update_user():
    data = request.get_json(force=True)

    uid = data.get("id")
    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()
    balance = data.get("balance")

    if not uid or not name or not phone or not password:
        return jsonify({"status": "error", "message": "Неверные данные"}), 400

    try:
        balance = int(balance)
    except:
        return jsonify({"status": "error", "message": "Баланс должен быть числом"}), 400

    users = load_json(USERS_FILE)
    updated = False

    for u in users:
        if int(u.get("id", 0)) == int(uid):
            u["name"] = name
            u["phone"] = phone
            u["password"] = password
            u["balance"] = balance
            updated = True
            break

    if not updated:
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    save_json(USERS_FILE, users)
    return jsonify({"status": "ok"})


# ============================================================
# 📌 API: удалить пользователя
# ============================================================
@users_bp.post("/api/users/delete")
def api_delete_user():
    data = request.get_json(force=True)
    uid = data.get("id")

    if not uid:
        return jsonify({"status": "error", "message": "Нет id"}), 400

    uid = int(uid)

    users = load_json(USERS_FILE)
    cart = load_json(CART_FILE)
    reviews = load_json(REVIEWS_FILE)
    purchases = load_json(PURCHASES_FILE)

    # Удаляем пользователя
    users = [u for u in users if int(u.get("id", 0)) != uid]

    # Удаляем корзину
    cart = [c for c in cart if int(c.get("user_id", 0)) != uid]

    # Удаляем отзывы
    reviews = [r for r in reviews if int(r.get("user_id", 0)) != uid]

    # Удаляем покупки (если есть)
    purchases = [p for p in purchases if int(p.get("user_id", 0)) != uid]

    save_json(USERS_FILE, users)
    save_json(CART_FILE, cart)
    save_json(REVIEWS_FILE, reviews)
    save_json(PURCHASES_FILE, purchases)

    return jsonify({"status": "ok"})


# ============================================================
# 📌 Старые admin-маршруты (для Tkinter Admin Panel)
# ============================================================
@users_bp.get("/api/admin/users")
def admin_get_users():
    return api_get_users()


@users_bp.post("/api/admin/users/update")
def admin_update_user():
    return api_update_user()


@users_bp.post("/api/admin/users/delete")
def admin_delete_user():
    return api_delete_user()
