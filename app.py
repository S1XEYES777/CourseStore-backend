import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import psycopg2.extras

# =======================================
#  FLASK + CORS
# =======================================

app = Flask(__name__)
CORS(app)

# =======================================
#  DATABASE_URL
# =======================================

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL не найден! "
        "В панели Render → Environment Variables добавь DATABASE_URL."
    )

def get_db():
    return psycopg2.connect(
        DATABASE_URL,
        sslmode="require",
        cursor_factory=psycopg2.extras.RealDictCursor
    )


# =======================================
#  INIT DB
# =======================================

def init_db():
    conn = get_db()
    cur = conn.cursor()

    # USERS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            balance INTEGER NOT NULL DEFAULT 0,
            avatar TEXT
        );
    """)

    # COURSES
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

    # LESSONS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            id SERIAL PRIMARY KEY,
            course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
            title TEXT,
            video_url TEXT,
            position INTEGER DEFAULT 1
        );
    """)

    # CART
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cart_items (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE
        );
    """)

    # PURCHASES
    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # REVIEWS
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


init_db()  # запуск при старте сервера


# =======================================
#  PING
# =======================================

@app.get("/api/ping")
def ping():
    return {"status": "ok"}


# =======================================
#  AUTH
# =======================================

@app.post("/api/register")
def register():
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    phone = data.get("phone", "").strip()
    password = data.get("password", "").strip()

    if not name or not phone or not password:
        return {"status": "error", "message": "Заполните все поля"}

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE phone=%s", (phone,))
    if cur.fetchone():
        conn.close()
        return {"status": "error", "message": "Телефон уже зарегистрирован"}

    cur.execute("""
        INSERT INTO users (name, phone, password)
        VALUES (%s, %s, %s)
        RETURNING *
    """, (name, phone, password))

    user = cur.fetchone()
    conn.commit()
    conn.close()

    return {"status": "ok", "user": user}


@app.post("/api/login")
def login():
    data = request.get_json(force=True)
    phone = data.get("phone", "").strip()
    password = data.get("password", "").strip()

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE phone = %s", (phone,))
    user = cur.fetchone()
    conn.close()

    if not user or user["password"] != password:
        return {"status": "error", "message": "Неверный телефон или пароль"}

    return {"status": "ok", "user": user}


# =======================================
#  USER PROFILE
# =======================================

@app.get("/api/user")
def get_user():
    uid = request.args.get("user_id")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=%s", (uid,))
    user = cur.fetchone()
    conn.close()

    if not user:
        return {"status": "error", "message": "Пользователь не найден"}

    return {"status": "ok", "user": user}


@app.post("/api/avatar")
def update_avatar():
    data = request.get_json(force=True)
    uid = data.get("user_id")
    avatar = data.get("avatar")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET avatar=%s WHERE id=%s", (avatar, uid))
    conn.commit()
    conn.close()

    return {"status": "ok"}


# =======================================
#  COURSES
# =======================================

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

    # Course
    cur.execute("SELECT * FROM courses WHERE id=%s", (cid,))
    course = cur.fetchone()

    if not course:
        conn.close()
        return {"status": "error", "message": "Курс не найден"}

    # Lessons
    cur.execute("""
        SELECT * FROM lessons
        WHERE course_id=%s
        ORDER BY position ASC
    """, (cid,))
    lessons = cur.fetchall()

    # Reviews
    cur.execute("""
        SELECT r.*, u.name AS user_name
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        WHERE course_id=%s
        ORDER BY created_at DESC
    """, (cid,))
    reviews = cur.fetchall()

    conn.close()

    return {
        "status": "ok",
        "course": course,
        "lessons": lessons,
        "reviews": reviews
    }


# ADD COURSE
@app.post("/api/courses/add")
def add_course():
    data = request.get_json(force=True)

    title = data.get("title")
    price = data.get("price")
    author = data.get("author")
    description = data.get("description")
    image = data.get("image")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO courses (title, price, author, description, image)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """, (title, price, author, description, image))

    cid = cur.fetchone()["id"]

    conn.commit()
    conn.close()

    return {"status": "ok", "course_id": cid}


# ADD LESSON
@app.post("/api/lessons/add")
def add_lesson():
    data = request.get_json(force=True)

    course_id = data.get("course_id")
    title = data.get("title")
    url = data.get("youtube_url")
    position = data.get("position", 1)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO lessons (course_id, title, video_url, position)
        VALUES (%s, %s, %s, %s)
    """, (course_id, title, url, position))

    conn.commit()
    conn.close()

    return {"status": "ok"}


@app.post("/api/lessons/delete")
def delete_lesson():
    lid = request.get_json().get("id")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM lessons WHERE id=%s", (lid,))
    conn.commit()
    conn.close()

    return {"status": "ok"}


# =======================================
#  CART + BUY
# =======================================

@app.get("/api/cart")
def get_cart():
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
def add_cart_item():
    data = request.get_json(force=True)
    uid = data.get("user_id")
    cid = data.get("course_id")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id FROM cart_items WHERE user_id=%s AND course_id=%s
    """, (uid, cid))

    if cur.fetchone():
        conn.close()
        return {"status": "ok"}

    cur.execute("""
        INSERT INTO cart_items (user_id, course_id)
        VALUES (%s, %s)
    """, (uid, cid))

    conn.commit()
    conn.close()

    return {"status": "ok"}


@app.post("/api/cart/remove")
def remove_cart_item():
    cid = request.get_json().get("cart_id")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM cart_items WHERE id=%s", (cid,))
    conn.commit()
    conn.close()

    return {"status": "ok"}


@app.post("/api/cart/buy")
def buy_cart():
    uid = request.get_json().get("user_id")

    conn = get_db()
    cur = conn.cursor()

    # Courses from cart
    cur.execute("""
        SELECT c.id, c.price
        FROM cart_items ci
        JOIN courses c ON c.id = ci.course_id
        WHERE ci.user_id=%s
    """, (uid,))
    items = cur.fetchall()

    if not items:
        conn.close()
        return {"status": "error", "message": "Корзина пуста"}

    total = sum(x["price"] for x in items)

    # Balance check
    cur.execute("SELECT balance FROM users WHERE id=%s", (uid,))
    bal = cur.fetchone()["balance"]

    if bal < total:
        conn.close()
        return {"status": "error", "message": "Недостаточно средств"}

    # Balance update
    cur.execute("UPDATE users SET balance=balance-%s WHERE id=%s", (total, uid))

    # Save purchases
    for it in items:
        cur.execute("""
            INSERT INTO purchases (user_id, course_id)
            VALUES (%s, %s)
        """, (uid, it["id"]))

    # Clear cart
    cur.execute("DELETE FROM cart_items WHERE user_id=%s", (uid,))

    conn.commit()
    conn.close()

    return {"status": "ok"}


# MY COURSES
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


# =======================================
#  REVIEWS
# =======================================

@app.post("/api/reviews/add")
def add_review():
    data = request.get_json(force=True)

    uid = data.get("user_id")
    cid = data.get("course_id")
    stars = data.get("stars", 5)
    text = data.get("text", "")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO reviews (user_id, course_id, stars, text)
        VALUES (%s, %s, %s, %s)
    """, (uid, cid, stars, text))

    conn.commit()
    conn.close()

    return {"status": "ok"}


# =======================================
#           ADMIN PANEL
# =======================================

# --- USERS LIST ---
@app.get("/api/admin/users")
def admin_users():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, phone, balance FROM users ORDER BY id DESC")
    data = cur.fetchall()
    conn.close()
    return {"status": "ok", "users": data}


# --- PURCHASES LIST ---
@app.get("/api/admin/purchases")
def admin_purchases():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT p.id,
               u.name AS user_name,
               c.title AS course_title,
               c.price,
               p.created_at
        FROM purchases p
        JOIN users u ON u.id = p.user_id
        JOIN courses c ON c.id = p.course_id
        ORDER BY p.id DESC
    """)

    items = cur.fetchall()
    conn.close()

    return {"status": "ok", "items": items}


# =======================================
#  RUN LOCAL
# =======================================

if __name__ == "__main__":
    app.run(port=5000, host="0.0.0.0", debug=True)
