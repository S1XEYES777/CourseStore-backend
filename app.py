from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from psycopg import connect
from psycopg.rows import dict_row

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    return connect(DATABASE_URL, row_factory=dict_row, autocommit=False)


# ============================================================
#  AUTO-CREATE DATABASE TABLES IF THEY DON'T EXIST
# ============================================================

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # USERS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            balance INTEGER DEFAULT 10000,
            avatar TEXT,
            is_admin BOOLEAN DEFAULT FALSE
        );
    """)

    # COURSES
    cur.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            price INTEGER NOT NULL,
            thumbnail TEXT,
            avg_rating NUMERIC(3,2) DEFAULT 0,
            ratings_count INTEGER DEFAULT 0
        );
    """)

    # LESSONS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            id SERIAL PRIMARY KEY,
            course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            video_url TEXT NOT NULL,
            order_index INTEGER NOT NULL
        );
    """)

    # PURCHASES
    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
            bought_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(user_id, course_id)
        );
    """)

    # CART ITEMS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cart_items (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
            added_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(user_id, course_id)
        );
    """)

    # REVIEWS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
            rating INTEGER NOT NULL,
            text TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    conn.commit()
    conn.close()


# ============================================================
#  CALL INIT DB
# ============================================================
init_db()



# ============================================================
#  HELPER: RECALC RATING
# ============================================================

def recalc_course_rating(course_id, conn=None):
    close = False
    if conn is None:
        conn = get_connection()
        close = True

    cur = conn.cursor()
    cur.execute("""
        SELECT 
            COALESCE(AVG(rating)::NUMERIC(3,2), 0) AS avg,
            COUNT(*) AS cnt
        FROM reviews
        WHERE course_id = %s
    """, (course_id,))

    row = cur.fetchone()

    cur.execute("""
        UPDATE courses
        SET avg_rating = %s,
            ratings_count = %s
        WHERE id = %s
    """, (row["avg"], row["cnt"], course_id))

    conn.commit()
    if close:
        conn.close()



# ============================================================
# LOGIN
# ============================================================

@app.post("/api/login")
def login():
    data = request.get_json(force=True)
    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, phone, balance, avatar, is_admin
        FROM users
        WHERE phone = %s AND password = %s
    """, (phone, password))

    user = cur.fetchone()
    conn.close()

    if not user:
        return jsonify({"status": "error", "message": "Неверный телефон или пароль"}), 400

    return jsonify({"status": "ok", "user": user})


# ============================================================
# REGISTER
# ============================================================

@app.post("/api/register")
def register():
    data = request.get_json(force=True)

    name = data.get("name")
    phone = data.get("phone")
    password = data.get("password")

    if not name or not phone or not password:
        return jsonify({"status": "error", "message": "Заполните все поля"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM users WHERE phone = %s", (phone,))
    if cur.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "Телефон занят"}), 400

    cur.execute("""
        INSERT INTO users (name, phone, password, balance)
        VALUES (%s, %s, %s, 10000)
        RETURNING id, name, phone, balance, avatar, is_admin
    """, (name, phone, password))

    user = cur.fetchone()
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "user": user})


# ============================================================
# COURSES
# ============================================================

@app.get("/api/courses")
def get_courses():
    user_id = request.args.get("user_id", type=int)

    conn = get_connection()
    cur = conn.cursor()

    if user_id:
        cur.execute("""
            SELECT
                c.id, c.title, c.description, c.price,
                c.thumbnail, c.avg_rating, c.ratings_count,
                CASE WHEN p.id IS NULL THEN FALSE ELSE TRUE END AS is_purchased
            FROM courses c
            LEFT JOIN purchases p
                ON p.course_id = c.id AND p.user_id = %s
            ORDER BY c.id DESC
        """, (user_id,))
    else:
        cur.execute("""
            SELECT id, title, description, price,
                   thumbnail, avg_rating, ratings_count,
                   FALSE AS is_purchased
            FROM courses
            ORDER BY id DESC
        """)

    rows = cur.fetchall()
    conn.close()

    return jsonify({"status": "ok", "courses": rows})


@app.get("/api/courses/<int:course_id>")
def course_details(course_id):
    user_id = request.args.get("user_id", type=int)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, description, price,
               thumbnail, avg_rating, ratings_count
        FROM courses
        WHERE id = %s
    """, (course_id,))
    course = cur.fetchone()

    if not course:
        conn.close()
        return jsonify({"status": "error", "message": "Курс не найден"}), 404

    # покупка
    is_purchased = False
    if user_id:
        cur.execute("""
            SELECT 1 FROM purchases
            WHERE user_id = %s AND course_id = %s
        """, (user_id, course_id))
        is_purchased = cur.fetchone() is not None

    course["is_purchased"] = is_purchased

    lessons = []
    if is_purchased:
        cur.execute("""
            SELECT id, title, video_url, order_index
            FROM lessons
            WHERE course_id = %s
            ORDER BY order_index
        """, (course_id,))
        lessons = cur.fetchall()

    conn.close()
    return jsonify({"status": "ok", "course": course, "lessons": lessons})


# ============================================================
# CART
# ============================================================

@app.get("/api/cart")
def get_cart():
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"status": "error", "message": "user_id обязателен"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT ci.id as cart_item_id,
               c.id as course_id,
               c.title, c.price, c.thumbnail
        FROM cart_items ci
        JOIN courses c ON c.id = ci.course_id
        WHERE ci.user_id = %s
        ORDER BY ci.added_at DESC
    """, (user_id,))

    items = cur.fetchall()
    conn.close()

    return jsonify({"status": "ok", "items": items})


@app.post("/api/cart/add")
def cart_add():
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    course_id = data.get("course_id")

    conn = get_connection()
    cur = conn.cursor()

    # нельзя добавить купленный
    cur.execute("""
        SELECT 1 FROM purchases
        WHERE user_id = %s AND course_id = %s
    """, (user_id, course_id))
    if cur.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "Курс уже куплен"}), 400

    cur.execute("""
        INSERT INTO cart_items (user_id, course_id)
        VALUES (%s, %s)
        ON CONFLICT (user_id, course_id) DO NOTHING
    """, (user_id, course_id))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.post("/api/cart/remove")
def cart_remove():
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    course_id = data.get("course_id")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM cart_items
        WHERE user_id = %s AND course_id = %s
    """, (user_id, course_id))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ============================================================
# PURCHASE
# ============================================================

@app.post("/api/purchase")
def purchase():
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    course_id = data.get("course_id")

    conn = get_connection()
    cur = conn.cursor()

    # уже куплен?
    cur.execute("""
        SELECT 1 FROM purchases
        WHERE user_id = %s AND course_id = %s
    """, (user_id, course_id))
    if cur.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "Уже куплен"}), 400

    # цена
    cur.execute("SELECT price FROM courses WHERE id = %s", (course_id,))
    c = cur.fetchone()
    if not c:
        conn.close()
        return jsonify({"status": "error", "message": "Курс не найден"}), 404

    price = c["price"]

    # баланс
    cur.execute("SELECT balance FROM users WHERE id = %s FOR UPDATE", (user_id,))
    u = cur.fetchone()
    if not u:
        conn.close()
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    if u["balance"] < price:
        conn.close()
        return jsonify({"status": "error", "message": "Недостаточно средств"}), 400

    # списываем деньги
    cur.execute("UPDATE users SET balance = balance - %s WHERE id = %s", (price, user_id))

    # покупка
    cur.execute("INSERT INTO purchases (user_id, course_id) VALUES (%s, %s)", (user_id, course_id))

    # удаляем из корзины
    cur.execute("DELETE FROM cart_items WHERE user_id = %s AND course_id = %s", (user_id, course_id))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ============================================================
# REVIEWS
# ============================================================

@app.post("/api/reviews")
def add_review():
    data = request.get_json(force=True)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO reviews (user_id, course_id, rating, text)
        VALUES (%s, %s, %s, %s)
    """, (data["user_id"], data["course_id"], data["rating"], data["text"]))

    conn.commit()
    recalc_course_rating(data["course_id"], conn)
    conn.close()

    return jsonify({"status": "ok"})



# ============================================================
# PROFILE: MY COURSES + AVATAR + BALANCE
# ============================================================

@app.get("/api/profile/my-courses")
def my_courses():
    user_id = request.args.get("user_id")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT c.id, c.title, c.thumbnail, c.avg_rating, c.ratings_count
        FROM purchases p
        JOIN courses c ON c.id = p.course_id
        WHERE p.user_id = %s
        ORDER BY p.bought_at DESC
    """, (user_id,))

    rows = cur.fetchall()
    conn.close()

    return jsonify({"status": "ok", "courses": rows})


@app.post("/api/profile/avatar")
def profile_avatar():
    data = request.get_json(force=True)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users SET avatar = %s WHERE id = %s
        RETURNING avatar
    """, (data["avatar_url"], data["user_id"]))

    row = cur.fetchone()
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "avatar": row["avatar"]})


@app.post("/api/balance/topup")
def topup():
    data = request.get_json(force=True)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users SET balance = balance + %s WHERE id = %s
        RETURNING balance
    """, (data["amount"], data["user_id"]))

    row = cur.fetchone()
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "balance": row["balance"]})


# ============================================================
# ADMIN PANEL ENDPOINTS
# ============================================================

@app.get("/api/admin/users")
def admin_users():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, phone, balance FROM users ORDER BY id DESC
    """)

    rows = cur.fetchall()
    conn.close()

    return jsonify({"status": "ok", "users": rows})


@app.post("/api/admin/users/update-balance")
def admin_update_balance():
    data = request.get_json(force=True)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users SET balance = %s WHERE id = %s
    """, (data["balance"], data["user_id"]))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.get("/api/admin/reviews")
def admin_reviews():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT r.id, u.name AS user_name,
               c.title AS course_title,
               r.rating, r.text, r.created_at
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        JOIN courses c ON c.id = r.course_id
        ORDER BY r.created_at DESC
    """)

    rows = cur.fetchall()
    conn.close()

    return jsonify({"status": "ok", "reviews": rows})


@app.delete("/api/admin/reviews/<int:review_id>")
def admin_remove_review(review_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM reviews WHERE id = %s", (review_id,))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# COURSES CRUD
@app.get("/api/admin/courses")
def admin_get_courses():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, description, price, thumbnail
        FROM courses ORDER BY id DESC
    """)

    rows = cur.fetchall()
    conn.close()

    return jsonify({"status": "ok", "courses": rows})


@app.post("/api/admin/courses/create")
def admin_course_create():
    data = request.get_json(force=True)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO courses (title, description, price, thumbnail)
        VALUES (%s, %s, %s, %s)
    """, (data["title"], data["description"], data["price"], data["thumbnail"]))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.post("/api/admin/courses/update")
def admin_course_update():
    data = request.get_json(force=True)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE courses
        SET title=%s, description=%s, price=%s, thumbnail=%s
        WHERE id=%s
    """, (data["title"], data["description"], data["price"], data["thumbnail"], data["id"]))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.delete("/api/admin/courses/<int:course_id>")
def admin_course_delete(course_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM courses WHERE id = %s", (course_id,))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# LESSONS CRUD
@app.get("/api/admin/courses/<int:course_id>/lessons")
def admin_get_lessons(course_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, video_url, order_index
        FROM lessons
        WHERE course_id = %s
        ORDER BY order_index
    """, (course_id,))

    rows = cur.fetchall()
    conn.close()

    return jsonify({"status": "ok", "lessons": rows})


@app.post("/api/admin/lessons/create")
def admin_create_lesson():
    data = request.get_json(force=True)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO lessons (course_id, title, video_url, order_index)
        VALUES (%s, %s, %s, %s)
    """, (data["course_id"], data["title"], data["video_url"], data["order_index"]))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.delete("/api/admin/lessons/<int:lesson_id>")
def admin_delete_lesson(lesson_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM lessons WHERE id = %s", (lesson_id,))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
