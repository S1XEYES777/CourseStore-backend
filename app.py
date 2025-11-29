import os
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import psycopg2.extras

# ==============================
#   POSTGRES ДЛЯ RENDER
# ==============================
DATABASE_URL = os.getenv("postgresql://coursestore_user:QpbQO0QAxRIwMRLVShTDgVSplVOMiZVQ@dpg-d4d05l0gjchc73dmfld0-a.oregon-postgres.render.com/coursestore?sslmode=require\")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL не установлен в Render!")

def get_db():
    return psycopg2.connect(
        DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor
    )

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            balance INTEGER DEFAULT 0,
            avatar TEXT
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            price INTEGER NOT NULL,
            author TEXT,
            description TEXT,
            image TEXT
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            id SERIAL PRIMARY KEY,
            course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
            title TEXT,
            video_url TEXT,
            position INTEGER DEFAULT 1
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cart_items (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            course_id INTEGER REFERENCES courses(id),
            stars INTEGER DEFAULT 5,
            text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    conn.close()

# Запускаем
app = Flask(__name__)
CORS(app)
init_db()


# ==============================
#   AUTH
# ==============================
@app.post("/api/register")
def register():
    data = request.json
    name = data["name"]
    phone = data["phone"]
    password = data["password"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE phone=%s", (phone,))
    if cur.fetchone():
        return {"status": "error", "message": "Телефон уже зарегистрирован"}

    cur.execute(
        "INSERT INTO users (name, phone, password) VALUES (%s,%s,%s) RETURNING *",
        (name, phone, password)
    )
    user = cur.fetchone()
    conn.commit()
    conn.close()

    return {"status": "ok", "user": dict(user)}


@app.post("/api/login")
def login():
    data = request.json
    phone = data["phone"]
    password = data["password"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE phone=%s", (phone,))
    user = cur.fetchone()
    conn.close()

    if not user or user["password"] != password:
        return {"status": "error", "message": "Неверный телефон или пароль"}

    return {"status": "ok", "user": dict(user)}


# ==============================
#   PROFILE
# ==============================
@app.get("/api/user")
def get_user():
    uid = request.args.get("user_id")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=%s", (uid,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return {"status": "error", "message": "Пользователь не найден"}

    return {"status": "ok", "user": dict(row)}


@app.post("/api/avatar")
def avatar():
    data = request.json
    uid = data["user_id"]
    avatar = data["avatar"]

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET avatar=%s WHERE id=%s", (avatar, uid))
    conn.commit()
    conn.close()

    return {"status": "ok"}


# ==============================
#   COURSES + LESSONS
# ==============================
@app.get("/api/courses")
def get_courses():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM courses ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return {"status": "ok", "courses": rows}


@app.get("/api/course")
def get_course():
    cid = request.args.get("course_id")
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM courses WHERE id=%s", (cid,))
    course = cur.fetchone()

    cur.execute(
        "SELECT * FROM lessons WHERE course_id=%s ORDER BY position ASC",
        (cid,)
    )
    lessons = cur.fetchall()

    cur.execute("""
        SELECT r.*, u.name AS user_name
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        WHERE course_id=%s ORDER BY created_at DESC
    """, (cid,))
    reviews = cur.fetchall()

    conn.close()

    return {"status": "ok", "course": course, "lessons": lessons, "reviews": reviews}


@app.post("/api/courses/add")
def add_course():
    data = request.json
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO courses (title, price, author, description, image)
        VALUES (%s,%s,%s,%s,%s) RETURNING id
    """, (data["title"], data["price"], data["author"], data["description"], data["image"]))

    cid = cur.fetchone()["id"]
    conn.commit()
    conn.close()

    return {"status": "ok", "course_id": cid}


@app.post("/api/lessons/add")
def add_lesson():
    data = request.json
    conn = get_db()
    cur = conn.cursor()

    # video_url = Drive /preview ссылка
    cur.execute("""
        INSERT INTO lessons (course_id,title,video_url,position)
        VALUES (%s,%s,%s,%s) RETURNING id
    """, (data["course_id"], data["title"], data["youtube_url"], data["position"]))

    conn.commit()
    conn.close()

    return {"status": "ok"}


@app.post("/api/lessons/delete")
def delete_lesson():
    lid = request.json["id"]
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM lessons WHERE id=%s", (lid,))
    conn.commit()
    conn.close()
    return {"status": "ok"}


# ==============================
#   CART + PURCHASES
# ==============================
@app.get("/api/cart")
def cart_get():
    uid = request.args.get("user_id")
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT ci.id AS cart_id, c.*
        FROM cart_items ci
        JOIN courses c ON c.id = ci.course_id
        WHERE ci.user_id=%s
    """, (uid,))

    rows = cur.fetchall()
    conn.close()
    return {"status": "ok", "items": rows}


@app.post("/api/cart/add")
def cart_add():
    uid = request.json["user_id"]
    cid = request.json["course_id"]

    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO cart_items (user_id,course_id) VALUES (%s,%s)",
                (uid, cid))

    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.post("/api/cart/remove")
def cart_remove():
    cart_id = request.json["cart_id"]

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM cart_items WHERE id=%s", (cart_id,))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.post("/api/cart/buy")
def buy():
    uid = request.json["user_id"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT c.id, c.price
        FROM cart_items ci
        JOIN courses c ON c.id = ci.course_id
        WHERE ci.user_id=%s
    """, (uid,))
    items = cur.fetchall()

    if not items:
        return {"status": "error", "message": "Корзина пуста"}

    total = sum(i["price"] for i in items)

    cur.execute("SELECT balance FROM users WHERE id=%s", (uid,))
    bal = cur.fetchone()["balance"]

    if bal < total:
        return {"status": "error", "message": "Недостаточно средств"}

    # Списываем
    cur.execute("UPDATE users SET balance=balance-%s WHERE id=%s",
                (total, uid))

    # Покупки
    for c in items:
        cur.execute("INSERT INTO purchases (user_id,course_id) VALUES (%s,%s)",
                    (uid, c["id"]))

    # Очищаем корзину
    cur.execute("DELETE FROM cart_items WHERE user_id=%s", (uid,))

    conn.commit()
    conn.close()

    return {"status": "ok"}


@app.get("/api/my-courses")
def my_courses():
    uid = request.args.get("user_id")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.*
        FROM purchases p
        JOIN courses c ON c.id = p.course_id
        WHERE p.user_id=%s
    """, (uid,))
    rows = cur.fetchall()
    conn.close()

    return {"status": "ok", "courses": rows}


# ==============================
#   REVIEWS
# ==============================
@app.post("/api/reviews/add")
def add_review():
    data = request.json
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO reviews (user_id,course_id,stars,text)
        VALUES (%s,%s,%s,%s)
    """, (data["user_id"], data["course_id"], data["stars"], data["text"]))

    conn.commit()
    conn.close()

    return {"status": "ok"}


# ==============================
#   START
# ==============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

