from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3

app = Flask(__name__)
CORS(app)

# ===========================
#  ИНИЦИАЛИЗАЦИЯ БАЗЫ
# ===========================
def init_db():
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT UNIQUE,
            password TEXT
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
    name = data.get("name")
    phone = data.get("phone")
    password = data.get("password")

    conn = sqlite3.connect("users.db")
    cur = conn.cursor()

    try:
        cur.execute("INSERT INTO users (name, phone, password) VALUES (?, ?, ?)",
                    (name, phone, password))
        conn.commit()
    except:
        return jsonify({"status": "error", "message": "Телефон уже существует"})

    conn.close()
    return jsonify({"status": "ok", "message": "Регистрация успешна"})


# ===========================
#   ВХОД
# ===========================
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    phone = data.get("phone")
    password = data.get("password")

    conn = sqlite3.connect("users.db")
    cur = conn.cursor()

    cur.execute("SELECT id, name, phone FROM users WHERE phone=? AND password=?", (phone, password))
    user = cur.fetchone()

    conn.close()

    if user:
        return jsonify({
            "status": "ok",
            "user": {
                "id": user[0],
                "name": user[1],
                "phone": user[2]
            }
        })

    return jsonify({"status": "error", "message": "Неверный номер или пароль"})


# ===========================
#  ПРОФИЛЬ
# ===========================
@app.route("/api/user/<int:user_id>")
def get_user(user_id):
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()

    cur.execute("SELECT id, name, phone FROM users WHERE id=?", (user_id,))
    user = cur.fetchone()

    conn.close()

    if not user:
        return jsonify({"status": "error", "message": "Пользователь не найден"})

    return jsonify({
        "status": "ok",
        "user": {
                "id": user[0],
                "name": user[1],
                "phone": user[2]
        }
    })


@app.route("/")
def home():
    return jsonify({"status": "backend ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

