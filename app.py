import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import psycopg2.extras

# ==========================
#  FLASK + CORS
# ==========================

app = Flask(__name__)
CORS(app)

# ==========================
# DATABASE
# ==========================

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("❌ DATABASE_URL не найден. Добавь в Render → Environment.")


def get_db():
    return psycopg2.connect(
        DATABASE_URL,
        sslmode="require",
        cursor_factory=psycopg2.extras.RealDictCursor
    )


# ==========================
# INIT TABLES
# ==========================

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
            user_id INTEGER REFERENCES users(id),
            course_id INTEGER REFERENCES courses(id),
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


init_db()

# ==========================
#  PING
# ==========================

@app.get("/api/ping")
def ping():
    return {"status": "ok"}


# ==========================
#  REGISTER + LOGIN
# ==========================

@app.post("/api/register")
def register():
    data = request.get_json()

    name = data.get("name")
    phone = data.get("phone")
    password = data.get("password")

    if not name or not phone or not password:
        return {"status": "error", "message": "Заполните все поля"}

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE phone = %s", (phone,))
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

    return {
        "status": "ok",
        "user": {
            "user_id": user["id"],
            "name": user["name"],
            "phone": user["phone"],
            "balance": user["balance"],
            "avatar": user["avatar"]
        }
    }


@app.post("/api/login")
def login():
    data = request.get_json()

    phone = data.get("phone")
    password = data.get("password")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE phone = %s", (phone,))
    u = cur.fetchone()
    conn.close()

    if not u or u["password"] != password:
        return {"status": "error", "message": "Неверный телефон или пароль"}

    return {
        "status": "ok",
        "user": {
            "user_id": u["id"],
            "name": u["name"],
            "phone": u["phone"],
            "balance": u["balance"],
            "avatar": u["avatar"]
        }
    }


# ==========================
# PROFILE
# ==========================

@app.get("/api/user")
def get_user():
    uid = request.args.get("user_id")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s", (uid,))
    u = cur.fetchone()
    conn.close()

    if not u:
        return {"status": "error", "message": "Пользователь не найден"}

    return {"status": "ok", "user": u}


@app.post("/api/avatar")
def update_avatar():
    data = request.get_json()
    uid = data.get("user_id")
    avatar = data.get("avatar")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET avatar = %s WHERE id = %s", (avatar, uid))
    conn.commit()
    conn.close()

    return {"status": "ok"}


# ==========================
# ADD BALANCE
# ==========================

@app.post("/api/add-balance")
def add_balance():
    data = request.get_json()
    uid = data.get("user_id")
    amount = data.get("amount")

    if amount <= 0:
        return {"status": "error", "message": "Сумма неверная"}

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET balance = balance + %s
        WHERE id = %s
        RETURNING balance
    """, (amount, uid))

    new_balance = cur.fetchone()["balance"]
    conn.commit()
    conn.close()

    return {"status": "ok", "balance": new_balance}


# ==========================
# COURSES
# ==========================

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

    cur.execute("SELECT * FROM courses WHERE id = %s", (cid,))
    course = cur.fetchone()

    if not course:
        conn.close()
        return {"status": "error", "message": "Курс не найден"}

    cur.execute("""
        SELECT * FROM lessons
        WHERE course_id = %s
        ORDER BY position ASC
    """, (cid,))
    lessons = cur.fetchall()

    cur.execute("""
        SELECT r.*, u.name AS user_name
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        WHERE r.course_id = %s
        ORDER BY r.created_at DESC
    """, (cid,))
    reviews = cur.fetchall()

    conn.close()

    return {
        "status": "ok",
        "course": course,
        "lessons": lessons,
        "reviews": reviews
    }


# ==========================
# ADMIN — COURSES
# ==========================

@app.get("/api/admin/courses")
def admin_courses():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM courses ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return {"status": "ok", "courses": rows}


@app.post("/api/admin/courses/add")
def admin_add_course():
    data = request.get_json()

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO courses (title, price, author, description, image)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """, (data["title"], data["price"], data["author"], data["description"], data["image"]))

    cid = cur.fetchone()["id"]
    conn.commit()
    conn.close()

    return {"status": "ok", "course_id": cid}


@app.post("/api/admin/courses/delete")
def admin_delete_course():
    data = request.get_json()
    cid = data.get("id")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM courses WHERE id = %s", (cid,))
    conn.commit()
    conn.close()

    return {"status": "ok"}


# ==========================
# LESSONS
# ==========================

@app.post("/api/admin/lessons/add")
def admin_add_lesson():
    data = request.get_json()

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO lessons (course_id, title, video_url, position)
        VALUES (%s, %s, %s, %s)
    """, (data["course_id"], data["title"], data["video_url"], data["position"]))

    conn.commit()
    conn.close()

    return {"status": "ok"}


@app.post("/api/admin/lessons/delete")
def admin_delete_lesson():
    data = request.get_json()
    lid = data.get("id")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM lessons WHERE id = %s", (lid,))
    conn.commit()
    conn.close()

    return {"status": "ok"}


@app.get("/api/admin/lessons")
def admin_get_lessons():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT l.*, c.title AS course_title
        FROM lessons l
        JOIN courses c ON c.id = l.course_id
        ORDER BY l.id DESC
    """)
    rows = cur.fetchall()

    conn.close()
    return {"status": "ok", "lessons": rows}


# ==========================
# CART
# ==========================

@app.get("/api/cart")
def get_cart():
    uid = request.args.get("user_id")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT ci.id AS cart_id, c.*
        FROM cart_items ci
        JOIN courses c ON c.id = ci.course_id
        WHERE ci.user_id = %s
    """, (uid,))
    rows = cur.fetchall()

    conn.close()
    return {"status": "ok", "items": rows}


@app.post("/api/cart/add")
def add_to_cart():
    data = request.get_json()
    uid = data["user_id"]
    cid = data["course_id"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id FROM cart_items
        WHERE user_id = %s AND course_id = %s
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
def remove_from_cart():
    data = request.get_json()
    cart_id = data.get("cart_id")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM cart_items WHERE id = %s", (cart_id,))
    conn.commit()
    conn.close()

    return {"status": "ok"}


@app.post("/api/cart/buy")
def buy_cart():
    data = request.get_json()
    uid = data["user_id"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT c.id, c.price 
        FROM cart_items ci 
        JOIN courses c ON c.id = ci.course_id 
        WHERE ci.user_id = %s
    """, (uid,))
    items = cur.fetchall()

    if not items:
        conn.close()
        return {"status": "error", "message": "Корзина пуста"}

    total = sum(i["price"] for i in items)

    cur.execute("SELECT balance FROM users WHERE id = %s", (uid,))
    balance = cur.fetchone()["balance"]

    if balance < total:
        conn.close()
        return {"status": "error", "message": "Недостаточно средств"}

    cur.execute("UPDATE users SET balance = balance - %s WHERE id = %s", (total, uid))

    for i in items:
        cur.execute("""
            INSERT INTO purchases (user_id, course_id)
            VALUES (%s, %s)
        """, (uid, i["id"]))

    cur.execute("DELETE FROM cart_items WHERE user_id = %s", (uid,))
    conn.commit()
    conn.close()

    return {"status": "ok"}


# ==========================
# ADMIN PURCHASES
# ==========================

@app.get("/api/admin/purchases")
def admin_purchases():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT p.*, u.name AS user_name, c.title AS course_title, c.price
        FROM purchases p
        JOIN users u ON u.id = p.user_id
        JOIN courses c ON c.id = p.course_id
        ORDER BY p.id DESC
    """)
    rows = cur.fetchall()

    conn.close()
    return {"status": "ok", "purchases": rows}


# ==========================
# ADMIN USERS
# ==========================

@app.get("/api/admin/users")
def admin_users():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id, name, phone, balance FROM users ORDER BY id DESC")
    rows = cur.fetchall()

    conn.close()
    return {"status": "ok", "users": rows}


@app.post("/api/admin/users/delete")
def admin_delete_user():
    data = request.get_json()
    uid = data.get("id")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = %s", (uid,))
    conn.commit()
    conn.close()

    return {"status": "ok"}


# ==========================
# ADMIN STATS
# ==========================

@app.get("/api/admin/stats")
def admin_stats():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    users = cur.fetchone()["count"]

    cur.execute("SELECT COUNT(*) FROM courses")
    courses = cur.fetchone()["count"]

    cur.execute("SELECT COUNT(*) FROM purchases")
    purchases = cur.fetchone()["count"]

    cur.execute("""
        SELECT COALESCE(SUM(c.price), 0) AS revenue
        FROM purchases p
        JOIN courses c ON c.id = p.course_id
    """)
    revenue = cur.fetchone()["revenue"]

    conn.close()

    return {
        "status": "ok",
        "users": users,
        "courses": courses,
        "purchases": purchases,
        "revenue": revenue
    }


# ==========================
# REVIEWS
# ==========================

@app.post("/api/reviews/add")
def add_review():
    data = request.get_json()

    uid = data.get("user_id")
    cid = data.get("course_id")
    stars = data.get("stars")
    text = data.get("text")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO reviews (user_id, course_id, stars, text)
        VALUES (%s, %s, %s, %s)
    """, (uid, cid, stars, text))

    conn.commit()
    conn.close()

    return {"status": "ok"}


# ==========================
# RUN
# ==========================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
