import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import psycopg2
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

# ----------------------------
# ПАПКА ДЛЯ ХРАНЕНИЯ ФАЙЛОВ
# ----------------------------
UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ----------------------------
# ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ
# ----------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    url = urlparse(DATABASE_URL)
    return psycopg2.connect(
        database=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port,
        sslmode="require"
    )


# ----------------------------
# СОЗДАНИЕ ТАБЛИЦ
# ----------------------------
def create_tables():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        name TEXT,
        phone TEXT UNIQUE,
        password TEXT,
        avatar TEXT DEFAULT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        id SERIAL PRIMARY KEY,
        title TEXT,
        price INTEGER,
        author TEXT,
        description TEXT,
        image TEXT
    );
    """)

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

create_tables()


# ----------------------------
# РЕГИСТРАЦИЯ
# ----------------------------
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
            "INSERT INTO users (name, phone, password) VALUES (%s, %s, %s) RETURNING id, name, phone, avatar;",
            (name, phone, password)
        )
        new_user = cur.fetchone()
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return jsonify({"status": "error", "message": "Номер занят"})

    cur.close()
    conn.close()

    return jsonify({
        "status": "ok",
        "user": {
            "id": new_user[0],
            "name": new_user[1],
            "phone": new_user[2],
            "avatar": new_user[3]
        }
    })


# ----------------------------
# ЛОГИН
# ----------------------------
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    phone = data["phone"]
    password = data["password"]

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, name, phone, avatar FROM users WHERE phone=%s AND password=%s",
        (phone, password)
    )

    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user:
        return jsonify({"status": "error", "message": "Неверный логин или пароль"})

    return jsonify({
        "status": "ok",
        "user": {
            "id": user[0],
            "name": user[1],
            "phone": user[2],
            "avatar": user[3]
        }
    })


# ----------------------------
# ДОБАВЛЕНИЕ КУРСА (АДМИН)
# ----------------------------
@app.route("/api/add_course", methods=["POST"])
def add_course():
    title = request.form.get("title")
    price = request.form.get("price")
    author = request.form.get("author")
    description = request.form.get("description")

    image = request.files.get("image")
    if not image:
        return jsonify({"status": "error", "message": "Нет изображения"})

    filename = image.filename
    path = os.path.join(UPLOAD_FOLDER, filename)
    image.save(path)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO courses (title, price, author, description, image)
        VALUES (%s, %s, %s, %s, %s)
    """, (title, price, author, description, filename))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"status": "ok"})


# ----------------------------
# ПОЛУЧЕНИЕ ВСЕХ КУРСОВ
# ----------------------------
@app.route("/api/courses")
def get_courses():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id, title, price, author, description, image FROM courses;")
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return jsonify([
        {
            "id": r[0],
            "title": r[1],
            "price": r[2],
            "author": r[3],
            "description": r[4],
            "image": r[5]
        }
        for r in rows
    ])


# ----------------------------
# УДАЛЕНИЕ КУРСА
# ----------------------------
@app.route("/api/delete_course/<int:course_id>", methods=["DELETE"])
def delete_course(course_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("DELETE FROM courses WHERE id=%s", (course_id,))
    conn.commit()

    cur.close()
    conn.close()

    return jsonify({"status": "ok"})


# ----------------------------
# ЗАГРУЗКА АВАТАРКИ
# ----------------------------
@app.route("/api/upload_avatar/<int:user_id>", methods=["POST"])
def upload_avatar(user_id):
    file = request.files.get("avatar")

    if not file:
        return jsonify({"status": "error", "message": "Файл не найден"})

    filename = f"user_{user_id}.jpg"
    file.save(os.path.join(UPLOAD_FOLDER, filename))

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET avatar=%s WHERE id=%s", (filename, user_id))
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"status": "ok", "avatar": filename})


# ----------------------------
# СТАТИЧЕСКИЕ ФАЙЛЫ (для картинок)
# ----------------------------
@app.route("/static/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ----------------------------
# ЗАПУСК
# ----------------------------
if __name__ == "__main__":
    app.run()
