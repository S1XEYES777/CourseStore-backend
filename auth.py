from flask import Blueprint, request, jsonify
from db import get_connection

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/api/register")
def register():
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    phone = data.get("phone", "").strip()
    password = data.get("password", "").strip()

    if not name or not phone or not password:
        return jsonify({"status": "error", "message": "Заполните все поля"}), 400

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE phone = ?", (phone,))
    if cur.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "Телефон уже зарегистрирован"}), 400

    cur.execute(
        "INSERT INTO users (name, phone, password, balance) VALUES (?, ?, ?, 0)",
        (name, phone, password)
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()

    return jsonify({"status": "ok", "user_id": user_id, "name": name, "phone": phone, "balance": 0})


@auth_bp.post("/api/login")
def login():
    data = request.get_json(force=True)
    phone = data.get("phone", "").strip()
    password = data.get("password", "").strip()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, phone, balance FROM users WHERE phone = ? AND password = ?",
        (phone, password)
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"status": "error", "message": "Неверный телефон или пароль"}), 400

    return jsonify({
        "status": "ok",
        "user_id": row["id"],
        "name": row["name"],
        "phone": row["phone"],
        "balance": row["balance"]
    })
