from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from psycopg import connect
from psycopg.rows import dict_row

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.getenv("DATABASE_URL")


# =============== DB ==================

def get_connection():
    return connect(DATABASE_URL, row_factory=dict_row, autocommit=False)


# =========== РЕЙТИНГ КУРСА =================

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


# =============== LOGIN ==================

@app.post("/api/login")
def login():
    data = request.get_json(force=True)
    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, phone, balance, is_admin, avatar
        FROM users
        WHERE phone = %s AND password = %s
    """, (phone, password))

    user = cur.fetchone()
    conn.close()

    if not user:
        return jsonify({"status": "error", "message": "Неверный телефон или пароль"}), 400

    return jsonify({"status": "ok", "user": user})


# =============== REGISTER ==================

@app.post("/api/register")
def register():
    data = request.get_json(force=True)

    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()

    if not name or not phone or not password:
        return jsonify({"status": "error", "message": "Заполните все поля"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM users WHERE phone = %s", (phone,))
    if cur.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "Телефон уже зарегистрирован"}), 400

    cur.execute("""
        INSERT INTO users (name, phone, password, balance)
        VALUES (%s, %s, %s, 10000)
        RETURNING id, name, phone, balance, is_admin, avatar
    """, (name, phone, password))

    user = cur.fetchone()
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "user": user})


# =============== COURSES ==================

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
            SELECT
                id, title, description, price,
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


# =============== CART ==================

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


# =============== PURCHASE ==================

@app.post("/api/purchase")
def purchase():
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    course_id = data.get("course_id")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT 1 FROM purchases
        WHERE user_id = %s AND course_id = %s
    """, (user_id, course_id))
    if cur.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "Курс уже куплен"}), 400

    cur.execute("SELECT price FROM courses WHERE id = %s", (course_id,))
    c = cur.fetchone()
    if not c:
        conn.close()
        return jsonify({"status": "error", "message": "Курс не найден"}), 404

    price = c["price"]

    cur.execute("SELECT balance FROM users WHERE id = %s FOR UPDATE", (user_id,))
    u = cur.fetchone()
    if not u:
        conn.close()
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    if u["balance"] < price:
        conn.close()
        return jsonify({"status": "error", "message": "Недостаточно средств"}), 400

    cur.execute("UPDATE users SET balance = balance - %s WHERE id = %s", (price, user_id))
    cur.execute("INSERT INTO purchases (user_id, course_id) VALUES (%s, %s)", (user_id, course_id))
    cur.execute("DELETE FROM cart_items WHERE user_id = %s AND course_id = %s", (user_id, course_id))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# =============== REVIEWS ==================

@app.post("/api/reviews")
def add_review():
    data = request.get_json(force=True)

    user_id = data.get("user_id")
    course_id = data.get("course_id")
    rating = data.get("rating")
    text = (data.get("text") or "").strip()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO reviews (user_id, course_id, rating, text)
        VALUES (%s, %s, %s, %s)
    """, (user_id, course_id, rating, text))

    conn.commit()
    recalc_course_rating(course_id, conn)
    conn.close()

    return jsonify({"status": "ok"})


@app.get("/api/courses/<int:course_id>/reviews")
def get_reviews(course_id):
    user_id = request.args.get("user_id", type=int, default=0)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT r.id, r.user_id, u.name AS user_name,
               r.rating, r.text, r.created_at
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        WHERE r.course_id = %s
          AND (r.rating >= 3 OR r.user_id = %s)
        ORDER BY r.created_at DESC
    """, (course_id, user_id))

    rows = cur.fetchall()
    conn.close()
    return jsonify({"status": "ok", "reviews": rows})


# =============== PROFILE ==================

@app.get("/api/profile/my-courses")
def my_courses():
    user_id = request.args.get("user_id", type=int)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT c.id, c.title, c.thumbnail,
               c.avg_rating, c.ratings_count
        FROM purchases p
        JOIN courses c ON c.id = p.course_id
        WHERE p.user_id = %s
        ORDER BY p.bought_at DESC
    """, (user_id,))

    rows = cur.fetchall()
    conn.close()

    return jsonify({"status": "ok", "courses": rows})


# =============== POPUP BALANCE ==================

@app.post("/api/balance/topup")
def balance_topup():
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    amount = data.get("amount")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET balance = balance + %s
        WHERE id = %s
        RETURNING balance
    """, (amount, user_id))

    row = cur.fetchone()
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "balance": row["balance"]})


# =============== AVATAR ==================

@app.post("/api/profile/avatar")
def set_avatar():
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    avatar_url = data.get("avatar_url")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET avatar = %s
        WHERE id = %s
        RETURNING avatar
    """, (avatar_url, user_id))

    row = cur.fetchone()
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "avatar": row["avatar"]})


# =============== ADMIN: USERS ==================

@app.get("/api/admin/users")
def admin_get_users():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, phone, balance, avatar, is_admin
        FROM users
        ORDER BY id DESC
    """)

    rows = cur.fetchall()
    conn.close()

    return jsonify({"status": "ok", "users": rows})


@app.post("/api/admin/users/update-balance")
def admin_update_balance():
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    balance = data.get("balance")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET balance = %s
        WHERE id = %s
    """, (balance, user_id))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# =============== ADMIN: COURSES ==================

@app.get("/api/admin/courses")
def admin_courses():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, description, price, thumbnail
        FROM courses
        ORDER BY id DESC
    """)

    rows = cur.fetchall()
    conn.close()
    return jsonify({"status": "ok", "courses": rows})


@app.post("/api/admin/courses/create")
def admin_course_create():
    data = request.get_json(force=True)

    title = data.get("title")
    description = data.get("description")
    price = data.get("price")
    thumbnail = data.get("thumbnail")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO courses (title, description, price, thumbnail)
        VALUES (%s, %s, %s, %s)
    """, (title, description, price, thumbnail))

    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


@app.post("/api/admin/courses/update")
def admin_course_update():
    data = request.get_json(force=True)
    id = data.get("id")
    title = data.get("title")
    description = data.get("description")
    price = data.get("price")
    thumbnail = data.get("thumbnail")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE courses
        SET title = %s,
            description = %s,
            price = %s,
            thumbnail = %s
        WHERE id = %s
    """, (title, description, price, thumbnail, id))

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


# =============== ADMIN: LESSONS ==================

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
def admin_lesson_create():
    data = request.get_json(force=True)

    course_id = data.get("course_id")
    title = data.get("title")
    video_url = data.get("video_url")
    order_index = data.get("order_index")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO lessons (course_id, title, video_url, order_index)
        VALUES (%s, %s, %s, %s)
    """, (course_id, title, video_url, order_index))

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


# =============== ADMIN: REVIEWS ==================

@app.get("/api/admin/reviews")
def admin_reviews():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT r.id, r.user_id, u.name AS user_name,
               r.course_id, c.title AS course_title,
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

    cur.execute("SELECT course_id FROM reviews WHERE id = %s", (review_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify({"status": "error", "message": "Отзыв не найден"}), 404

    course_id = row["course_id"]

    cur.execute("DELETE FROM reviews WHERE id = %s", (review_id,))
    conn.commit()

    recalc_course_rating(course_id, conn)
    conn.close()

    return jsonify({"status": "ok"})


# =============== RUN ==================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
