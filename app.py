import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import psycopg2

app = Flask(__name__)
CORS(app)

# ===========================
#  DATABASE
# ===========================

# Render даёт DATABASE_URL в переменных окружения
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL не задан в переменных окружения")

# иногда бывает postgres://, а psycopg2 хочет postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # ---------- users ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT,
            phone TEXT UNIQUE,
            password TEXT,
            avatar TEXT,
            balance INTEGER DEFAULT 0
        );
    """)

    # ---------- courses ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id SERIAL PRIMARY KEY,
            title TEXT,
            price INTEGER
        );
    """)

    # добавляем новые колонки, если их ещё нет
    cur.execute("""ALTER TABLE courses ADD COLUMN IF NOT EXISTS image TEXT;""")
    cur.execute("""ALTER TABLE courses ADD COLUMN IF NOT EXISTS description TEXT;""")
    cur.execute("""ALTER TABLE courses ADD COLUMN IF NOT EXISTS author TEXT;""")

    # ---------- cart ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cart (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            course_id INTEGER
        );
    """)

    # ---------- purchases ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            course_id INTEGER
        );
    """)

    conn.commit()
    cur.close()
    conn.close()


init_db()

# ===========================
#  FILE UPLOADS
# ===========================
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ===========================
#  AUTH: REGISTER / LOGIN
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
            "INSERT INTO users (name, phone, password) VALUES (%s, %s, %s)",
            (name, phone, password)
        )
        conn.commit()
        cur.execute(
            "SELECT id, avatar, balance FROM users WHERE phone=%s",
            (phone,)
        )
        row = cur.fetchone()
    except psycopg2.Error:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"status": "error", "message": "Номер телефона уже зарегистрирован"})

    cur.close()
    conn.close()

    return jsonify({
        "status": "ok",
        "user": {
            "id": row[0],
            "name": name,
            "phone": phone,
            "avatar": row[1],
            "balance": row[2],
            "is_admin": (phone == "77750476284" and password == "777")
        }
    })


@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    phone = data["phone"]
    password = data["password"]

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, name, phone, avatar, balance FROM users WHERE phone=%s AND password=%s",
        (phone, password)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({"status": "error", "message": "Неверный логин или пароль"})

    return jsonify({
        "status": "ok",
        "user": {
            "id": row[0],
            "name": row[1],
            "phone": row[2],
            "avatar": row[3],
            "balance": row[4],
            "is_admin": (row[2] == "77750476284" and password == "777")
        }
    })


# ===========================
#  USER PROFILE
# ===========================
@app.route("/api/user/<int:user_id>")
def get_user(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, phone, avatar, balance FROM users WHERE id=%s",
        (user_id,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({"status": "error", "message": "Пользователь не найден"})

    return jsonify({
        "status": "ok",
        "user": {
            "id": row[0],
            "name": row[1],
            "phone": row[2],
            "avatar": row[3],
            "balance": row[4],
            "is_admin": (row[2] == "77750476284")
        }
    })


# ===========================
#  AVATAR UPLOAD
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
    cur.execute("UPDATE users SET avatar=%s WHERE id=%s", (filename, user_id))
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"status": "ok", "avatar": filename})


# ===========================
#  BALANCE TOPUP
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
        "UPDATE users SET balance = balance + %s WHERE id=%s",
        (amount, user_id)
    )
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"status": "ok", "message": f"Баланс пополнен на {amount}₸"})


# ===========================
#  COURSES
# ===========================
@app.route("/api/courses")
def get_courses():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, title, price, image, description, author FROM courses")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify([
        {
            "id": r[0],
            "title": r[1],
            "price": r[2],
            "image": r[3],
            "description": r[4],
            "author": r[5]
        } for r in rows
    ])


# ---------- ADMIN: ADD COURSE ----------
@app.route("/api/admin/add_course", methods=["POST"])
def admin_add_course():
    title = request.form.get("title")
    price = request.form.get("price")
    desc = request.form.get("description")
    author = request.form.get("author")
    image = request.files.get("image")

    if not title or not price or not image:
        return jsonify({"status": "error", "message": "Название, цена и картинка обязательны"})

    filename = f"course_{title.replace(' ', '_')}.jpg"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    image.save(filepath)

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO courses (title, price, image, description, author)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (title, int(price), filename, desc, author)
        )
        conn.commit()
    except psycopg2.Error as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"status": "error", "message": str(e)})

    cur.close()
    conn.close()
    return jsonify({"status": "ok", "message": "Курс добавлен"})


# ---------- ADMIN: DELETE COURSE ----------
@app.route("/api/admin/delete_course/<int:course_id>", methods=["DELETE"])
def admin_delete_course(course_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM courses WHERE id=%s", (course_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"status": "ok", "message": "Курс удалён"})


# ===========================
#  CART
# ===========================
@app.route("/api/cart/add", methods=["POST"])
def add_to_cart():
    data = request.json
    user_id = data["user_id"]
    course_id = data["course_id"]

    conn = get_conn()
    cur = conn.cursor()

    # уже куплен?
    cur.execute(
        "SELECT 1 FROM purchases WHERE user_id=%s AND course_id=%s",
        (user_id, course_id)
    )
    if cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({"status": "error", "message": "Курс уже куплен"})

    # уже в корзине?
    cur.execute(
        "SELECT 1 FROM cart WHERE user_id=%s AND course_id=%s",
        (user_id, course_id)
    )
    if cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({"status": "error", "message": "Курс уже в корзине"})

    cur.execute(
        "INSERT INTO cart (user_id, course_id) VALUES (%s, %s)",
        (user_id, course_id)
    )
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"status": "ok", "message": "Добавлено в корзину"})


@app.route("/api/cart/<int:user_id>")
def get_cart(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT courses.id, courses.title, courses.price, courses.image
        FROM cart
        JOIN courses ON cart.course_id = courses.id
        WHERE cart.user_id=%s
    """, (user_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify([
        {"id": r[0], "title": r[1], "price": r[2], "image": r[3]}
        for r in rows
    ])


@app.route("/api/cart/remove", methods=["POST"])
def remove_from_cart():
    data = request.json
    user_id = data["user_id"]
    course_id = data["course_id"]

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM cart WHERE user_id=%s AND course_id=%s",
        (user_id, course_id)
    )
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"status": "ok"})


@app.route("/api/cart/checkout/<int:user_id>", methods=["POST"])
def checkout(user_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT COALESCE(SUM(courses.price), 0)
        FROM cart
        JOIN courses ON cart.course_id = courses.id
        WHERE cart.user_id=%s
    """, (user_id,))
    total = cur.fetchone()[0]

    if total == 0:
        cur.close()
        conn.close()
        return jsonify({"status": "error", "message": "Корзина пуста"})

    cur.execute("SELECT balance FROM users WHERE id=%s", (user_id,))
    balance = cur.fetchone()[0]

    if balance < total:
        cur.close()
        conn.close()
        return jsonify({"status": "error", "message": "Недостаточно средств"})

    # списываем деньги
    cur.execute(
        "UPDATE users SET balance = balance - %s WHERE id=%s",
        (total, user_id)
    )

    # переносим курсы в покупки
    cur.execute("""
        INSERT INTO purchases (user_id, course_id)
        SELECT user_id, course_id FROM cart WHERE user_id=%s
    """, (user_id,))

    # чистим корзину
    cur.execute("DELETE FROM cart WHERE user_id=%s", (user_id,))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"status": "ok", "message": "Покупка успешна"})


# ===========================
#  PURCHASES
# ===========================
@app.route("/api/purchases/<int:user_id>")
def purchases(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT courses.id, courses.title, courses.price, courses.image
        FROM purchases
        JOIN courses ON purchases.course_id = courses.id
        WHERE purchases.user_id=%s
    """, (user_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify([
        {"id": r[0], "title": r[1], "price": r[2], "image": r[3]}
        for r in rows
    ])


# ===========================
#  STATIC UPLOADS
# ===========================
@app.route("/uploads/<path:filename>")
def serve_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ===========================
#  HEALTH CHECK
# ===========================
@app.route("/")
def home():
    return jsonify({"status": "backend ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
