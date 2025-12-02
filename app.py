import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import psycopg2.extras

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("❌ DATABASE_URL не найден!")

def db():
    return psycopg2.connect(
        DATABASE_URL,
        sslmode="require",
        cursor_factory=psycopg2.extras.RealDictCursor
    )

# ============================================================
# INIT DB
# ============================================================

def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT,
            phone TEXT UNIQUE,
            password TEXT,
            balance INTEGER DEFAULT 0,
            avatar TEXT DEFAULT 'https://i.imgur.com/ZKLRtYk.png'
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id SERIAL PRIMARY KEY,
            title TEXT,
            author TEXT,
            price INTEGER,
            image TEXT,
            description TEXT,
            rating FLOAT DEFAULT 0
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            id SERIAL PRIMARY KEY,
            course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
            title TEXT,
            video_url TEXT
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            course_id INTEGER REFERENCES courses(id)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cart_items (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            course_id INTEGER REFERENCES courses(id)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            course_id INTEGER REFERENCES courses(id),
            stars INTEGER,
            text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    conn.close()


init_db()


# ============================================================
# AUTH
# ============================================================

@app.post("/api/register")
def register():
    data = request.get_json()
    name, phone, password = data["name"], data["phone"], data["password"]

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE phone=%s", (phone,))
    if cur.fetchone():
        return {"status": "error", "message": "Телефон уже существует"}

    cur.execute("""
        INSERT INTO users (name, phone, password)
        VALUES (%s,%s,%s)
        RETURNING *
    """, (name, phone, password))

    u = cur.fetchone()
    conn.commit()
    conn.close()

    return {"status": "ok", "user": u}


@app.post("/api/login")
def login():
    data = request.get_json()
    phone, password = data["phone"], data["password"]

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE phone=%s", (phone,))
    u = cur.fetchone()
    conn.close()

    if not u or u["password"] != password:
        return {"status": "error", "message": "Неверные данные"}

    return {"status": "ok", "user": u}

# ============================================================
# CATALOG
# ============================================================

@app.get("/api/catalog")
def catalog():
    uid = request.args.get("user_id")

    conn = db()
    cur = conn.cursor()

    # купленные курсы
    cur.execute("SELECT course_id FROM purchases WHERE user_id=%s", (uid,))
    purchased = {row["course_id"] for row in cur.fetchall()}

    cur.execute("SELECT * FROM courses ORDER BY id DESC")
    rows = cur.fetchall()

    for r in rows:
        r["is_purchased"] = r["id"] in purchased

    conn.close()
    return {"status": "ok", "courses": rows}

# ============================================================
# SINGLE COURSE PAGE
# ============================================================

@app.get("/api/course")
def course():
    cid = request.args.get("id")
    uid = request.args.get("user_id")

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM courses WHERE id=%s", (cid,))
    course = cur.fetchone()
    if not course:
        return {"status": "error", "message": "Курс не найден"}

    # проверка покупки
    cur.execute(
        "SELECT id FROM purchases WHERE user_id=%s AND course_id=%s",
        (uid, cid)
    )
    purchased = bool(cur.fetchone())

    # уроки только если куплено
    lessons = []
    if purchased:
        cur.execute("SELECT * FROM lessons WHERE course_id=%s", (cid,))
        lessons = cur.fetchall()

    # отзывы
    cur.execute("""
        SELECT r.*, u.name AS user_name
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        WHERE r.course_id=%s
        ORDER BY created_at DESC
    """, (cid,))
    rev = cur.fetchall()

    # скрытие плохих отзывов
    for r in rev:
        if r["stars"] < 3 and r["user_id"] != int(uid):
            r["text"] = "Скрытый отзыв"
            r["stars"] = 0

    conn.close()

    return {
        "status": "ok",
        "course": course,
        "lessons": lessons,
        "reviews": rev,
        "purchased": purchased
    }


# ============================================================
# CART
# ============================================================

@app.post("/api/cart/add")
def cart_add():
    data = request.get_json()
    uid, cid = data["user_id"], data["course_id"]

    conn = db()
    cur = conn.cursor()

    # нельзя добавить купленный
    cur.execute(
        "SELECT id FROM purchases WHERE user_id=%s AND course_id=%s", (uid, cid)
    )
    if cur.fetchone():
        return {"status": "error", "message": "Уже куплено"}

    # нельзя добавить повторно
    cur.execute(
        "SELECT id FROM cart_items WHERE user_id=%s AND course_id=%s", (uid, cid)
    )
    if cur.fetchone():
        return {"status": "ok"}

    cur.execute(
        "INSERT INTO cart_items (user_id, course_id) VALUES (%s,%s)",
        (uid, cid)
    )
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.get("/api/cart")
def cart_get():
    uid = request.args.get("user_id")

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT cart_items.id AS cart_id,
               courses.*
        FROM cart_items
        JOIN courses ON courses.id = cart_items.course_id
        WHERE cart_items.user_id=%s
    """, (uid,))

    rows = cur.fetchall()
    conn.close()
    return {"status": "ok", "items": rows}


@app.post("/api/cart/remove")
def cart_remove():
    cid = request.get_json()["cart_id"]

    conn = db()
    cur = conn.cursor()
    cur.execute("DELETE FROM cart_items WHERE id=%s", (cid,))
    conn.commit()
    conn.close()

    return {"status": "ok"}


@app.post("/api/cart/buy")
def cart_buy():
    uid = request.get_json()["user_id"]

    conn = db()
    cur = conn.cursor()

    # все товары корзины
    cur.execute("""
        SELECT cart_items.course_id, courses.price
        FROM cart_items
        JOIN courses ON courses.id = cart_items.course_id
        WHERE cart_items.user_id=%s
    """, (uid,))
    items = cur.fetchall()

    if not items:
        return {"status": "error", "message": "Корзина пуста"}

    total = sum(i["price"] for i in items)

    cur.execute("SELECT balance FROM users WHERE id=%s", (uid,))
    bal = cur.fetchone()["balance"]

    if bal < total:
        return {"status": "error", "message": "Недостаточно средств"}

    # снимаем деньги
    cur.execute("UPDATE users SET balance=balance-%s WHERE id=%s", (total, uid))

    # добавляем покупки
    for i in items:
        cur.execute(
            "INSERT INTO purchases (user_id, course_id) VALUES (%s,%s)",
            (uid, i["course_id"])
        )

    # очистка корзины
    cur.execute("DELETE FROM cart_items WHERE user_id=%s", (uid,))
    conn.commit()
    conn.close()

    return {"status": "ok"}

# ============================================================
# REVIEWS
# ============================================================

@app.post("/api/reviews/add")
def review_add():
    data = request.get_json()
    uid, cid, stars, text = data["user_id"], data["course_id"], data["stars"], data["text"]

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO reviews (user_id, course_id, stars, text)
        VALUES (%s,%s,%s,%s)
    """, (uid, cid, stars, text))

    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.post("/api/admin/reviews/delete")
def admin_delete_review():
    rid = request.get_json()["id"]

    conn = db()
    cur = conn.cursor()
    cur.execute("DELETE FROM reviews WHERE id=%s", (rid,))
    conn.commit()
    conn.close()

    return {"status": "ok"}


# ============================================================
# USER COURSES
# ============================================================

@app.get("/api/user/courses")
def user_courses():
    uid = request.args.get("user_id")

    conn = db()
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


# ============================================================
# ADMIN PANEL
# ============================================================

@app.get("/api/admin/users")
def admin_users():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return {"status": "ok", "users": rows}


@app.get("/api/admin/courses")
def admin_courses():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM courses ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return {"status": "ok", "courses": rows}


@app.get("/api/admin/lessons")
def admin_lessons():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT lessons.*, courses.title AS course_title
        FROM lessons
        JOIN courses ON courses.id = lessons.course_id
        ORDER BY lessons.id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return {"status": "ok", "lessons": rows}


@app.post("/api/admin/courses/add")
def admin_add_course():
    data = request.get_json()

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO courses (title, author, price, image, description)
        VALUES (%s,%s,%s,%s,%s)
    """, (data["title"], data["author"], data["price"], data["image"], data["description"]))

    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.post("/api/admin/lessons/add")
def admin_add_lesson():
    data = request.get_json()

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO lessons (course_id, title, video_url)
        VALUES (%s,%s,%s)
    """, (data["course_id"], data["title"], data["video_url"]))

    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.post("/api/admin/courses/delete")
def admin_delete_course():
    cid = request.get_json()["id"]

    conn = db()
    cur = conn.cursor()
    cur.execute("DELETE FROM courses WHERE id=%s", (cid,))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.get("/")
def home():
    return "CourseStore 2.0 Backend работает!"



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
