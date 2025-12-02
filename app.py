from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg
import psycopg.rows
import os

# ============================================================
# APP
# ============================================================

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    return psycopg.connect(DATABASE_URL, sslmode="require")


# ============================================================
# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ПЕРЕСЧЁТА РЕЙТИНГА
# ============================================================

def recalc_course_rating(course_id, conn=None):
    close = False
    if conn is None:
        conn = get_connection()
        close = True

    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(AVG(rating)::NUMERIC(3,2), 0), COUNT(*)
        FROM reviews
        WHERE course_id = %s
    """, (course_id,))
    avg_rating, count = cur.fetchone()

    cur.execute("""
        UPDATE courses
        SET avg_rating = %s,
            ratings_count = %s
        WHERE id = %s
    """, (avg_rating, count, course_id))

    conn.commit()
    if close:
        conn.close()


# ============================================================
# КУРСЫ
# ============================================================

@app.get("/api/courses")
def get_courses():
    user_id = request.args.get("user_id", type=int)

    conn = get_connection()
    cur = conn.cursor(row_factory=psycopg.rows.dict_row)

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

    courses = cur.fetchall()
    conn.close()

    return jsonify({"status": "ok", "courses": courses})


@app.get("/api/courses/<int:course_id>")
def course_details(course_id):
    user_id = request.args.get("user_id", type=int)

    conn = get_connection()
    cur = conn.cursor(row_factory=psycopg.rows.dict_row)

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

    # проверка покупки
    is_purchased = False
    if user_id:
        cur.execute("""
            SELECT 1 FROM purchases
            WHERE user_id = %s AND course_id = %s
        """, (user_id, course_id))
        is_purchased = cur.fetchone() is not None

    course["is_purchased"] = is_purchased

    # уроки (только купленному)
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
# КОРЗИНА
# ============================================================

@app.get("/api/cart")
def get_cart():
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"status": "error", "message": "user_id обязателен"}), 400

    conn = get_connection()
    cur = conn.cursor(row_factory=psycopg.rows.dict_row)

    cur.execute("""
        SELECT ci.id AS cart_item_id,
               c.id AS course_id,
               c.title, c.price, c.thumbnail
        FROM cart_items ci
        JOIN courses c ON c.id = ci.course_id
        WHERE ci.user_id = %s
        ORDER BY ci.addadded_at DESC
    """, (user_id,))

    items = cur.fetchall()
    conn.close()
    return jsonify({"status": "ok", "items": items})


@app.post("/api/cart/add")
def cart_add():
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    course_id = data.get("course_id")

    if not user_id or not course_id:
        return jsonify({"status": "error", "message": "Не хватает данных"}), 400

    conn = get_connection()
    cur = conn.cursor()

    # уже куплен?
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
# ПОКУПКА
# ============================================================

@app.post("/api/purchase")
def purchase():
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    course_id = data.get("course_id")

    if not user_id or not course_id:
        return jsonify({"status": "error", "message": "Не хватает данных"}), 400

    conn = get_connection()
    cur = conn.cursor(row_factory=psycopg.rows.dict_row)

    # уже куплен?
    cur.execute("""
        SELECT 1 FROM purchases
        WHERE user_id = %s AND course_id = %s
    """, (user_id, course_id))
    if cur.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "Курс уже куплен"}), 400

    # цена
    cur.execute("SELECT price FROM courses WHERE id = %s", (course_id,))
    c = cur.fetchone()
    if not c:
        conn.close()
        return jsonify({"status": "error", "message": "Курс не найден"}), 404

    price = c["price"]

    # баланс
    cur.execute("SELECT balance FROM users WHERE id = %s FOR UPDATE", (user_id,))
    balance_row = cur.fetchone()
    if not balance_row:
        conn.close()
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    if balance_row["balance"] < price:
        conn.close()
        return jsonify({"status": "error", "message": "Недостаточно средств"}), 400

    # списываем + запись о покупке
    cur.execute("UPDATE users SET balance = balance - %s WHERE id = %s",
                (price, user_id))

    cur.execute("INSERT INTO purchases (user_id, course_id) VALUES (%s, %s)",
                (user_id, course_id))

    cur.execute("DELETE FROM cart_items WHERE user_id = %s AND course_id = %s",
                (user_id, course_id))

    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


# ============================================================
# ОТЗЫВЫ
# ============================================================

@app.post("/api/reviews")
def add_review():
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    course_id = data.get("course_id")
    rating = data.get("rating")
    text = (data.get("text") or "").strip()

    if not all([user_id, course_id, rating]):
        return jsonify({"status": "error", "message": "Не хватает данных"}), 400

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
    cur = conn.cursor(row_factory=psycopg.rows.dict_row)

    cur.execute("""
        SELECT r.id, r.user_id, u.name AS user_name,
               r.rating, r.text, r.created_at
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        WHERE r.course_id = %s
          AND (r.rating >= 3 OR r.user_id = %s)
        ORDER BY r.created_at DESC
    """, (course_id, user_id))

    reviews = cur.fetchall()
    conn.close()

    return jsonify({"status": "ok", "reviews": reviews})


# ============================================================
# ПРОФИЛЬ
# ============================================================

@app.get("/api/profile/my-courses")
def my_courses():
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"status": "error", "message": "user_id обязателен"}), 400

    conn = get_connection()
    cur = conn.cursor(row_factory=psycopg.rows.dict_row)

    cur.execute("""
        SELECT c.id, c.title, c.thumbnail,
               c.avg_rating, c.ratings_count
        FROM purchases p
        JOIN courses c ON c.id = p.course_id
        WHERE p.user_id = %s
        ORDER BY p.bought_at DESC
    """, (user_id,))

    courses = cur.fetchall()
    conn.close()

    return jsonify({"status": "ok", "courses": courses})


# ============================================================
# АДМИН
# ============================================================

@app.get("/api/admin/reviews")
def admin_reviews():
    conn = get_connection()
    cur = conn.cursor(row_factory=psycopg.rows.dict_row)

    cur.execute("""
        SELECT r.id, r.user_id, u.name AS user_name,
               r.course_id, c.title AS course_title,
               r.rating, r.text, r.created_at
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        JOIN courses c ON c.id = r.course_id
        ORDER BY r.created_at DESC
    """)

    reviews = cur.fetchall()
    conn.close()

    return jsonify({"status": "ok", "reviews": reviews})


@app.delete("/api/admin/reviews/<int:review_id>")
def admin_remove_review(review_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT course_id FROM reviews WHERE id = %s", (review_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"status": "error", "message": "Отзыв не найден"}), 404

    course_id = row[0]

    cur.execute("DELETE FROM reviews WHERE id = %s", (review_id,))
    conn.commit()

    recalc_course_rating(course_id, conn)
    conn.close()

    return jsonify({"status": "ok"})


@app.get("/api/admin/courses/ratings")
def admin_courses_ratings():
    conn = get_connection()
    cur = conn.cursor(row_factory=psycopg.rows.dict_row)

    cur.execute("""
        SELECT id, title, avg_rating, ratings_count
        FROM courses
        ORDER BY id DESC
    """)

    courses = cur.fetchall()
    conn.close()

    return jsonify({"status": "ok", "courses": courses})


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    app.run()
