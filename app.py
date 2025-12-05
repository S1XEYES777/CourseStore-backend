from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import os

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_NAME = "users.db"


# ===========================
#  БАЗА ДАННЫХ
# ===========================
def get_conn():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # Пользователи
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

    # Курсы
    cur.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            price INTEGER,
            image TEXT
        )
    """)

    # Корзина
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            course_id INTEGER
        )
    """)

    # Покупки
    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            course_id INTEGER
        )
    """)

    conn.commit()
    conn.close()


init_db()


# ===========================
#  РЕГИСТРАЦИЯ
# ===========================
@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    name = data["name"]
    phone = data["phone"]
    password = data["password"]

    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute(
            "INSERT INTO users (name, phone, password) VALUES (?, ?, ?)",
            (name, phone, password)
        )
        conn.commit()
        user_id = cur.lastrowid
    except:
        return jsonify({"status": "error", "message": "Телефон уже зарегистрирован"})

    conn.close()

    return jsonify({
        "status": "ok",
        "user": {
            "id": user_id,
            "name": name,
            "phone": phone,
            "avatar": None,
            "balance": 0
        }
    })


# ===========================
#  ВХОД
# ===========================
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    phone = data["phone"]
    password = data["password"]

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, name, phone, avatar, balance FROM users WHERE phone=? AND password=?",
        (phone, password)
    )
    u = cur.fetchone()
    conn.close()

    if not u:
        return jsonify({"status": "error", "message": "Неверный логин или пароль"})

    return jsonify({
        "status": "ok",
        "user": {
            "id": u[0],
            "name": u[1],
            "phone": u[2],
            "avatar": u[3],
            "balance": u[4],
            "is_admin": (u[2] == "77750476284" and password == "777")
        }
    })


# ===========================
#  ПРОФИЛЬ
# ===========================
@app.route("/api/user/<int:user_id>")
def get_user(user_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, name, phone, avatar, balance FROM users WHERE id=?",
        (user_id,)
    )
    u = cur.fetchone()
    conn.close()

    if not u:
        return jsonify({"status": "error", "message": "Пользователь не найден"})

    return jsonify({
        "status": "ok",
        "user": {
            "id": u[0],
            "name": u[1],
            "phone": u[2],
            "avatar": u[3],
            "balance": u[4],
            "is_admin": (u[2] == "77750476284")
        }
    })


# ===========================
#  ЗАГРУЗКА АВАТАРА
# ===========================
@app.route("/api/upload_avatar/<int:user_id>", methods=["POST"])
def upload_avatar(user_id):
    file = request.files.get("avatar")
    if not file:
        return jsonify({"status": "error", "message": "Файл не найден"})

    filename = f"user_{user_id}.jpg"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET avatar=? WHERE id=?", (filename, user_id))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "avatar": filename})


# ===========================
#  ПОПОЛНЕНИЕ БАЛАНСА
# ===========================
@app.route("/api/topup/<int:user_id>", methods=["POST"])
def topup(user_id):
    data = request.json
    amount = int(data.get("amount", 0))

    if amount <= 0:
        return jsonify({"status": "error", "message": "Некорректная сумма"})

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET balance = balance + ? WHERE id=?",
        (amount, user_id)
    )
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "message": f"Баланс пополнен на {amount}₸"})


# ===========================
#  ВСЕ КУРСЫ
# ===========================
@app.route("/api/courses")
def get_courses():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id, title, price, image FROM courses")
    rows = cur.fetchall()
    conn.close()

    return jsonify([
        {"id": r[0], "title": r[1], "price": r[2], "image": r[3]}
        for r in rows
    ])


# ===========================
#  АДМИН: ДОБАВИТЬ КУРС
# ===========================
@app.route("/api/admin/add_course", methods=["POST"])
def admin_add_course():
    title = request.form.get("title")
    price = request.form.get("price")
    image = request.files.get("image")

    if not title or not price or not image:
        return jsonify({"status": "error", "message": "Все поля обязательны"})

    filename = f"course_{title.replace(' ', '_')}.jpg"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    image.save(filepath)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO courses (title, price, image) VALUES (?, ?, ?)",
        (title, price, filename)
    )
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "message": "Курс добавлен"})


# ===========================
#  АДМИН: УДАЛИТЬ КУРС
# ===========================
@app.route("/api/admin/delete_course/<int:course_id>", methods=["DELETE"])
def admin_delete_course(course_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("DELETE FROM courses WHERE id=?", (course_id,))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "message": "Курс удалён"})


# ===========================
#  КОРЗИНА
# ===========================
@app.route("/api/cart/add", methods=["POST"])
def add_to_cart():
    data = request.json
    user_id = data["user_id"]
    course_id = data["course_id"]

    conn = get_conn()
    cur = conn.cursor()

    # Уже куплен?
    cur.execute(
        "SELECT 1 FROM purchases WHERE user_id=? AND course_id=?",
        (user_id, course_id)
    )
    if cur.fetchone():
        return jsonify({"status": "error", "message": "Курс уже куплен"})

    # Уже в корзине?
    cur.execute(
        "SELECT 1 FROM cart WHERE user_id=? AND course_id=?",
        (user_id, course_id)
    )
    if cur.fetchone():
        return jsonify({"status": "error", "message": "Курс в корзине"})

    cur.execute(
        "INSERT INTO cart (user_id, course_id) VALUES (?, ?)",
        (user_id, course_id)
    )
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "message": "Добавлено в корзину"})


# ===========================
#  ПОКАЗАТЬ КОРЗИНУ
# ===========================
@app.route("/api/cart/<int:user_id>")
def get_cart(user_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT courses.id, courses.title, courses.price, courses.image
        FROM cart
        JOIN courses ON cart.course_id = courses.id
        WHERE cart.user_id=?
    """, (user_id,))
    rows = cur.fetchall()

    conn.close()

    return jsonify([
        {"id": r[0], "title": r[1], "price": r[2], "image": r[3]}
        for r in rows
    ])


# ===========================
#  УДАЛИТЬ ИЗ КОРЗИНЫ
# ===========================
@app.route("/api/cart/remove", methods=["POST"])
def remove_from_cart():
    data = request.json
    user_id = data["user_id"]
    course_id = data["course_id"]

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM cart WHERE user_id=? AND course_id=?",
        (user_id, course_id)
    )
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ===========================
#  ПОКУПКА
# ===========================
@app.route("/api/cart/checkout/<int:user_id>", methods=["POST"])
def checkout(user_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT SUM(courses.price)
        FROM cart
        JOIN courses ON cart.course_id = courses.id
        WHERE cart.user_id=?
    """, (user_id,))
    total = cur.fetchone()[0]

    if not total:
        return jsonify({"status": "error", "message": "Корзина пуста"})

    cur.execute("SELECT balance FROM users WHERE id=?", (user_id,))
    balance = cur.fetchone()[0]

    if balance < total:
        return jsonify({"status": "error", "message": "Недостаточно средств"})

    # списать деньги
    cur.execute(
        "UPDATE users SET balance = balance - ? WHERE id=?",
        (total, user_id)
    )

    # перенести в покупки
    cur.execute("""
        INSERT INTO purchases (user_id, course_id)
        SELECT user_id, course_id FROM cart WHERE user_id=?
    """, (user_id,))

    # очистить корзину
    cur.execute("DELETE FROM cart WHERE user_id=?", (user_id,))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "message": "Покупка успешна"})


# ===========================
#  МОИ КУРСЫ
# ===========================
@app.route("/api/purchases/<int:user_id>")
def purchases(user_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT courses.id, courses.title, courses.price, courses.image
        FROM purchases
        JOIN courses ON purchases.course_id = courses.id
        WHERE purchases.user_id=?
    """, (user_id,))
    rows = cur.fetchall()

    conn.close()

    return jsonify([
        {"id": r[0], "title": r[1], "price": r[2], "image": r[3]}
        for r in rows
    ])


# ===========================
#  ОТДАЧА ФАЙЛОВ
# ===========================
@app.route("/uploads/<path:filename>")
def serve_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ===========================
#  ПИНГ
# ===========================
@app.route("/")
def home():
    return jsonify({"status": "backend ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
