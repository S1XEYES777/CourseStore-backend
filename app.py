from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import os

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ===========================
#   ИНИЦИАЛИЗАЦИЯ БАЗЫ
# ===========================
def init_db():
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT UNIQUE,
            password TEXT,
            avatar TEXT,
            balance INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()

init_db()


# ===========================
#   РЕГИСТРАЦИЯ
# ===========================
@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    name = data["name"]
    phone = data["phone"]
    password = data["password"]

    conn = sqlite3.connect("users.db")
    cur = conn.cursor()

    try:
        cur.execute("INSERT INTO users (name, phone, password, balance) VALUES (?, ?, ?, 0)",
                    (name, phone, password))
        conn.commit()
    except:
        return jsonify({"status": "error", "message": "Телефон уже есть"})

    return jsonify({"status": "ok"})


# ===========================
#   ВХОД
# ===========================
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    phone = data["phone"]
    password = data["password"]

    conn = sqlite3.connect("users.db")
    cur = conn.cursor()

    cur.execute("SELECT id, name, phone, avatar, balance FROM users WHERE phone=? AND password=?",
                (phone, password))
    user = cur.fetchone()

    if not user:
        return jsonify({"status": "error", "message": "Неверный логин"})

    return jsonify({
        "status": "ok",
        "user": {
            "id": user[0],
            "name": user[1],
            "phone": user[2],
            "avatar": user[3],
            "balance": user[4]
        }
    })


# ===========================
#   ПРОФИЛЬ
# ===========================
@app.route("/api/user/<int:user_id>")
def get_user(user_id):
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()

    cur.execute("SELECT id, name, phone, avatar, balance FROM users WHERE id=?", (user_id,))
    u = cur.fetchone()

    if not u:
        return jsonify({"status": "error"})

    return jsonify({
        "status": "ok",
        "user": {
            "id": u[0],
            "name": u[1],
            "phone": u[2],
            "avatar": u[3],
            "balance": u[4]
        }
    })


# ===========================
#   ЗАГРУЗКА АВАТАРА
# ===========================
@app.route("/api/upload_avatar/<int:user_id>", methods=["POST"])
def upload_avatar(user_id):
    file = request.files["avatar"]

    filename = f"user_{user_id}.jpg"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("UPDATE users SET avatar=? WHERE id=?", (filename, user_id))
    conn.commit()

    return jsonify({"status": "ok", "avatar": filename})


# ===========================
#   ПОПОЛНЕНИЕ БАЛАНСА
# ===========================
@app.route("/api/topup/<int:user_id>", methods=["POST"])
def topup(user_id):
    amount = 500  # фиксированное пополнение

    conn = sqlite3.connect("users.db")
    cur = conn.cursor()

    cur.execute("UPDATE users SET balance = balance + ? WHERE id=?", (amount, user_id))
    conn.commit()

    return jsonify({"status": "ok", "amount": amount})


# ===========================
#  ОТДАЧА АВАТАРОВ
# ===========================
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/")
def home():
    return jsonify({"status": "backend ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
