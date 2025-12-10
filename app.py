import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import psycopg2
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

# ==========================================
# ПАПКИ ДЛЯ МЕДИА
# ==========================================
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
UPLOAD_VIDEO_FOLDER = os.path.join(UPLOAD_FOLDER, "videos")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_VIDEO_FOLDER, exist_ok=True)

# ==========================================
# ПОДКЛЮЧЕНИЕ К БАЗЕ
# ==========================================
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    result = urlparse(DATABASE_URL)
    return psycopg2.connect(
        database=result.path[1:],
        user=result.username,
        password=result.password,
        host=result.hostname,
        port=result.port,
        sslmode="require"
    )

# ==========================================
# СОЗДАНИЕ ТАБЛИЦ
# ==========================================
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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS cart (
        id SERIAL PRIMARY KEY,
        user_id INTEGER,
        course_id INTEGER
    );
    """)

    # ★ ★ ★ НОВАЯ ТАБЛИЦА ДЛЯ УРОКОВ ★ ★ ★
    cur.execute("""
    CREATE TABLE IF NOT EXISTS lessons (
        id SERIAL PRIMARY KEY,
        course_id INTEGER,
        title TEXT,
        filename TEXT
    );
    """)

    conn.commit()
    cur.close()
    conn.close()

create_tables()

# =====================================================
#  РЕГИСТРАЦИЯ 
# =====================================================
@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    name = data["name"]
    phone = data["phone"]
    password = data["password"]

    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO users (name, phone, password)
            VALUES (%s, %s, %s)
            RETURNING id, name, phone, avatar;
        """, (name, phone, password))

        user = cur.fetchone()
        conn.commit()

    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return jsonify({"status": "error", "message": "Номер уже занят"})

    cur.close()
    conn.close()

    return jsonify({"status": "ok", "user": {
        "id": user[0],
        "name": user[1],
        "phone": user[2],
        "avatar": user[3]
    }})


# =====================================================
#  ВХОД
# =====================================================
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    phone = data["phone"]
    password = data["password"]

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, phone, avatar 
        FROM users 
        WHERE phone=%s AND password=%s
    """, (phone, password))

    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user:
        return jsonify({"status": "error", "message": "Неверный логин или пароль"})

    return jsonify({"status": "ok", "user": {
        "id": user[0],
        "name": user[1],
        "phone": user[2],
        "avatar": user[3]
    }})



# =====================================================
#  ДОБАВЛЕНИЕ КУРСА (АДМИН)
# =====================================================
@app.route("/api/add_course", methods=["POST"])
def add_course():
    title = request.form.get("title")
    price = request.form.get("price")
    author = request.form.get("author")
    description = request.form.get("description")
    file = request.files.get("image")

    if not file:
        return jsonify({"status": "error", "message": "Нет изображения"})

    filename = file.filename
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

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


# =====================================================
#  СПИСОК КУРСОВ
# =====================================================
@app.route("/api/courses")
def courses():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, price, author, description, image
        FROM courses
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()

    result = []
    for c in rows:
        result.append({
            "id": c[0],
            "title": c[1],
            "price": c[2],
            "author": c[3],
            "description": c[4],
            "image": c[5]
        })

    return jsonify(result)



# =====================================================
#  УДАЛЕНИЕ КУРСА
# =====================================================
@app.route("/api/delete_course/<int:course_id>", methods=["DELETE"])
def delete_course(course_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("DELETE FROM courses WHERE id=%s", (course_id,))
    conn.commit()

    cur.close()
    conn.close()

    return jsonify({"status": "ok"})


# =====================================================
#  ДОБАВИТЬ В КОРЗИНУ
# =====================================================
@app.route("/api/cart/add", methods=["POST"])
def add_to_cart():
    data = request.json
    user_id = data["user_id"]
    course_id = data["course_id"]

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO cart (user_id, course_id) VALUES (%s, %s)", (user_id, course_id))
    conn.commit()

    cur.close()
    conn.close()

    return jsonify({"status": "ok"})


# =====================================================
#  КОРЗИНА ПОЛЬЗОВАТЕЛЯ
# =====================================================
@app.route("/api/cart/<int:user_id>")
def get_cart(user_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT courses.id, courses.title, courses.price
        FROM cart 
        JOIN courses ON cart.course_id = courses.id
        WHERE cart.user_id = %s
    """, (user_id,))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    items = []
    for r in rows:
        items.append({
            "id": r[0],
            "title": r[1],
            "price": r[2]
        })

    return jsonify(items)


# =====================================================
#  ОПЛАТА
# =====================================================
@app.route("/api/cart/checkout/<int:user_id>", methods=["POST"])
def checkout(user_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT course_id FROM cart WHERE user_id=%s", (user_id,))
    course_ids = [row[0] for row in cur.fetchall()]

    for cid in course_ids:
        cur.execute("INSERT INTO purchases (user_id, course_id) VALUES (%s, %s)", (user_id, cid))

    cur.execute("DELETE FROM cart WHERE user_id=%s", (user_id,))
    conn.commit()

    cur.close()
    conn.close()

    return jsonify({"status": "ok"})


# =====================================================
#  МОИ КУРСЫ
# =====================================================
@app.route("/api/purchases/<int:user_id>")
def purchases(user_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT courses.id, courses.title, courses.price
        FROM purchases
        JOIN courses ON purchases.course_id = courses.id
        WHERE purchases.user_id = %s
    """, (user_id,))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    result = []
    for r in rows:
        result.append({"id": r[0], "title": r[1], "price": r[2]})

    return jsonify(result)


# =====================================================
#  ЗАГРУЗКА АВАТАРА
# =====================================================
@app.route("/api/upload_avatar", methods=["POST"])
def upload_avatar():
    file = request.files.get("avatar")
    user_id = request.form.get("user_id")

    if not file:
        return jsonify({"status": "error", "message": "Файл отсутствует"})

    filename = f"user_{user_id}.jpg"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET avatar=%s WHERE id=%s", (filename, user_id))
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"status": "ok", "filename": filename})


# =====================================================
# ★ ★ ★ ЗАГРУЗКА ВИДЕО УРОКА ★ ★ ★
# =====================================================
@app.route("/api/upload_lesson", methods=["POST"])
def upload_lesson():
    course_id = request.form.get("course_id")
    title = request.form.get("title")
    file = request.files.get("file")

    if not course_id or not title or not file:
        return jsonify({"status": "error", "message": "Missing fields"}), 400

    folder = os.path.join(UPLOAD_VIDEO_FOLDER, course_id)
    os.makedirs(folder, exist_ok=True)

    filepath = os.path.join(folder, file.filename)
    file.save(filepath)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO lessons (course_id, title, filename)
        VALUES (%s, %s, %s)
    """, (course_id, title, file.filename))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"status": "ok"})


# =====================================================
# ★ ★ ★ ПОЛУЧЕНИЕ УРОКОВ КУРСА ★ ★ ★
# =====================================================
@app.route("/api/get_lessons")
def get_lessons():
    course_id = request.args.get("course_id")
    user_id = request.args.get("user_id")

    # Проверяем покупку
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT 1 FROM purchases 
        WHERE user_id=%s AND course_id=%s
    """, (user_id, course_id))
    
    purchased = cur.fetchone()
    cur.close()
    conn.close()

    if not purchased:
        return jsonify({"status": "error", "message": "not purchased"}), 403

    # Если купил → выдаём уроки
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, filename 
        FROM lessons 
        WHERE course_id=%s
    """, (course_id,))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    lessons = []
    for l in rows:
        lessons.append({
            "id": l[0],
            "title": l[1],
            "url": f"/videos/{course_id}/{l[2]}"
        })

    return jsonify({"status": "ok", "lessons": lessons})


# =====================================================
# ★ ★ ★ ОТДАЧА ВИДЕО ★ ★ ★
# =====================================================
@app.route("/videos/<course_id>/<filename>")
def serve_video(course_id, filename):
    folder = os.path.join(UPLOAD_VIDEO_FOLDER, course_id)
    return send_from_directory(folder, filename)


# =====================================================
# ОТДАЧА АВАТАРОВ
# =====================================================
@app.route("/uploads/<filename>")
def uploaded_files(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# =====================================================
# СТАРТ
# =====================================================
if __name__ == "__main__":
    app.run()
