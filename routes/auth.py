from flask import Blueprint, request, jsonify
import os
import json

auth_bp = Blueprint("auth", __name__)

# ==========================
#  JSON ФАЙЛДАР
# ==========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")

USERS_FILE = os.path.join(DATA_DIR, "users.json")


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


# ============================================================
# 📌 РЕГИСТРАЦИЯ ПОЛЬЗОВАТЕЛЯ (JSON)
# ============================================================
@auth_bp.post("/api/register")
def register():
    data = request.get_json(force=True)

    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()

    if not name or not phone or not password:
        return jsonify({"status": "error", "message": "Заполните все поля"}), 400

    users = load_json(USERS_FILE)

    # Проверяем телефон
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

    return jsonify({
        "status": "ok",
        "user": {
            "id": user["id"],
            "name": user["name"],
            "phone": user["phone"],
            "balance": user["balance"]
        }
    })


# ============================================================
# 📌 ВХОД ПОЛЬЗОВАТЕЛЯ (JSON)
# ============================================================
@auth_bp.post("/api/login")
def login():
    data = request.get_json(force=True)

    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()

    if not phone or not password:
        return jsonify({"status": "error", "message": "Заполните телефон и пароль"}), 400

    users = load_json(USERS_FILE)

    for u in users:
        if u.get("phone") == phone and u.get("password") == password:
            return jsonify({
                "status": "ok",
                "user": {
                    "id": u["id"],
                    "name": u["name"],
                    "phone": u["phone"],
                    "balance": u.get("balance", 0)
                }
            })

    return jsonify({"status": "error", "message": "Неверный телефон или пароль"}), 400
