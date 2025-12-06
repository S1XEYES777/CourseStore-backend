from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import psycopg2
import os
import urllib.parse as up

app = Flask(__name__)
CORS(app)

# -------------------------------
# Создание папки uploads
# -------------------------------
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# -------------------------------
# Подключение к БД через DATABASE_URL
# -------------------------------
up.uses_netloc.append("postgres")

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise Exception("❌ ERROR: DATABASE_URL is missing!")

url = up.urlparse(DATABASE_URL)

conn = psycopg2.connect(
    database=url.path[1:],
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port,
    sslmode="require"
)


# -------------------------------
# АВТО-СОЗДАНИЕ ВСЕХ ТАБЛИЦ
# -------------------------------

def create_tables():
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT,
            phone TEXT UNIQUE,
            password TEXT,
            balance INTEGER DEFAULT 0,
            avatar TEXT
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id SERIAL PRIMARY KEY,
            title TEXT,
            price INTEGER,
            image TEXT,
            description TEXT,
            author TEXT
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cart (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            course_id INTEGER
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchased (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            course_id INTEGER
        );
    """)

    conn.commit()
    print("✅ Все таблицы созданы!")

create_tables()


# -------------------------------
# Помощник user
# -------------------------------

def dict_user(row):
    return {
        "id": row[0],
        "name": row[1],
        "phone": row[2],
        "password": row[3],
        "balance": row[4],
        "avatar": row[5]
    }


# -------------------------------
# Регистрация
# -------------------------------

@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    name = data["name"]
    phone = data["phone"]
    password = data["password"]

    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE phone=%s", (phone,))
    if cur.fetchone():
        return jsonify({"status": "error", "message": "Номер телефона занят"})

    cur.execute("""
        INSERT INTO users (name, phone, password, balance, avatar)
        VALUES (%s, %s, %s, 0, NULL)
        RETURNING *
    """, (name, phone, password))

    row = cur.fetchone()
    conn.commit()

    return jsonify({"status": "ok", "user": dict_user(row)})


# -------------------------------
# Логин
# -------------------------------

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    phone = data["phone"]
    password = data["password"]

    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE phone=%s AND password=%s", (phone, password))
    row = cur.fetchone()

    if not row:
        return jsonify({"status": "error", "message": "Неверный логин или пароль"})

    return jsonify({"status": "ok", "user": dict_user(row)})


# -------------------------------
# Загрузка аватара
# -------------------------------

@app.route("/api/upload_avatar", methods=["POST"])
def upload_avatar():
    try:
        user_id = request.form.get("user_id")
        file = request.files.get("avatar")

        if not user_id or not file:
            return jsonify({"status": "error", "message": "Нет файла"})

        filename = f"avatar_{user_id}.png"
        filepath = os.path.join(UPLOAD_FOLDER, filename)

        file.save(filepath)

        cur = conn.cursor()
        cur.execute("UPDATE users SET avatar=%s WHERE id=%s", (filename, user_id))
        conn.commit()

        return jsonify({"status": "ok", "filename": filename})

    except Exception as e:
        print("UPLOAD ERROR:", e)
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)})


# -------------------------------
# Выдача файлов uploads
# -------------------------------

@app.route("/uploads/<path:path>")
def send_upload(path):
    return send_from_directory(UPLOAD_FOLDER, path)


# -------------------------------
# Баланс
# -------------------------------

@app.route("/api/add_balance", methods=["POST"])
def add_balance():
    data = request.json
    uid = data["user_id"]
    amount = int(data["amount"])

    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = balance + %s WHERE id=%s RETURNING balance", (amount, uid))
    new_balance = cur.fetchone()[0]
    conn.commit()

    return jsonify({"status": "ok", "new_balance": new_balance})


# -------------------------------
# Курсы
# -------------------------------

@app.route("/api/courses")
def get_courses():
    cur = conn.cursor()
    cur.execute("SELECT * FROM courses")
    rows = cur.fetchall()

    result = [
        {
            "id": r[0],
            "title": r[1],
            "price": r[2],
            "image": r[3],
            "description": r[4],
            "author": r[5]
        } for r in rows
    ]

    return jsonify(result)


@app.route("/api/admin/add_course", methods=["POST"])
def add_course():
    try:
        title = request.form.get("title")
        price = request.form.get("price")
        description = request.form.get("description")
        author = request.form.get("author")
        image = request.files.get("image")

        if not title or not price or not description or not author or not image:
            return jsonify({"status": "error", "message": "Заполните все поля"})

        filename = f"course_{title.replace(' ', '_')}.png"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        image.save(filepath)

        cur = conn.cursor()
        cur.execute("""
            INSERT INTO courses (title, price, image, description, author)
            VALUES (%s, %s, %s, %s, %s)
        """, (title, price, filename, description, author))
        conn.commit()

        return jsonify({"status": "ok"})

    except Exception as e:
        print("ADD COURSE ERROR:", e)
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/admin/delete_course/<int:cid>", methods=["DELETE"])
def delete_course(cid):
    cur = conn.cursor()
    cur.execute("DELETE FROM courses WHERE id=%s", (cid,))
    conn.commit()
    return jsonify({"status": "ok"})


# -------------------------------
# Корзина
# -------------------------------

@app.route("/api/cart/add", methods=["POST"])
def add_to_cart():
    data = request.json
    uid = data["user_id"]
    cid = data["course_id"]

    cur = conn.cursor()
    cur.execute("INSERT INTO cart (user_id, course_id) VALUES (%s, %s)", (uid, cid))
    conn.commit()

    return jsonify({"status": "ok"})


@app.route("/api/cart/<int:uid>")
def cart(uid):
    cur = conn.cursor()
    cur.execute("""
        SELECT courses.id, courses.title, courses.price
        FROM cart
        JOIN courses ON courses.id = cart.course_id
        WHERE cart.user_id=%s
    """, (uid,))
    rows = cur.fetchall()

    return jsonify([
        {"id": r[0], "title": r[1], "price": r[2]} for r in rows
    ])


@app.route("/api/cart/remove", methods=["POST"])
def remove_cart():
    data = request.json
    uid = data["user_id"]
    cid = data["course_id"]

    cur = conn.cursor()
    cur.execute("DELETE FROM cart WHERE user_id=%s AND course_id=%s", (uid, cid))
    conn.commit()

    return jsonify({"status": "ok"})


# -------------------------------
# Покупка
# -------------------------------

@app.route("/api/cart/checkout/<int:uid>", methods=["POST"])
def checkout(uid):
    cur = conn.cursor()

    cur.execute("SELECT course_id FROM cart WHERE user_id=%s", (uid,))
    rows = cur.fetchall()

    for r in rows:
        cur.execute("INSERT INTO purchased (user_id, course_id) VALUES (%s, %s)", (uid, r[0]))

    cur.execute("DELETE FROM cart WHERE user_id=%s", (uid,))
    conn.commit()

    return jsonify({"status": "ok"})


# -------------------------------
# Мои курсы
# -------------------------------

@app.route("/api/purchases/<int:uid>")
def purchases(uid):
    cur = conn.cursor()
    cur.execute("""
        SELECT courses.id, courses.title, courses.price
        FROM purchased
        JOIN courses ON purchased.course_id = courses.id
        WHERE purchased.user_id=%s
    """, (uid,))
    rows = cur.fetchall()

    return jsonify([
        {"id": r[0], "title": r[1], "price": r[2]} for r in rows
    ])


# -------------------------------
# RUN SERVER
# -------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
