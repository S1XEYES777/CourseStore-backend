import sqlite3
from flask import Flask, request, jsonify

DB_NAME = "database.db"

app = Flask(__name__)


# =========================
# БАЗА ДАННЫХ (SQLite)
# =========================

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row   # позволяет row["id"]
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    # USERS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT UNIQUE,
        password TEXT NOT NULL,
        balance INTEGER DEFAULT 0
    );
    """)

    # COURSES
    cur.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        youtube_url TEXT,
        position INTEGER DEFAULT 1,
        FOREIGN KEY(course_id) REFERENCES courses(id)
    );
    """)

    # REVIEWS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        stars INTEGER NOT NULL DEFAULT 5,
        text TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(course_id) REFERENCES courses(id)
    );
    """)

    # CART ITEMS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cart_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(course_id) REFERENCES courses(id)
    );
    """)

    # PURCHASES
    cur.execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(course_id) REFERENCES courses(id)
    );
    """)

    conn.commit()
    conn.close()


# =========================
# СЕРВИСНЫЙ ПИНГ
# =========================

@app.get("/api/ping")
def ping():
    return jsonify({"status": "ok", "message": "pong"})


# =========================
# AUTH: РЕГИСТРАЦИЯ / ЛОГИН
# =========================

@app.post("/api/register")
def register():
    data = request.get_json(force=True)

    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()

    if not name or not phone or not password:
        return jsonify({"status": "error", "message": "Заполните все поля"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE phone = ?", (phone,))
    if cur.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "Телефон уже зарегистрирован"}), 400

    cur.execute("""
        INSERT INTO users (name, phone, password, balance)
        VALUES (?, ?, ?, 0)
    """, (name, phone, password))

    user_id = cur.lastrowid
    conn.commit()

    cur.execute("SELECT id, name, phone, balance FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()

    return jsonify({
        "status": "ok",
        "user": {
            "user_id": user["id"],
            "name": user["name"],
            "phone": user["phone"],
            "balance": user["balance"]
        }
    })


@app.post("/api/login")
def login():
    data = request.get_json(force=True)

    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()

    if not phone or not password:
        return jsonify({"status": "error", "message": "Заполните телефон и пароль"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, phone, balance
        FROM users
        WHERE phone = ? AND password = ?
    """, (phone, password))

    user = cur.fetchone()
    conn.close()

    if not user:
        return jsonify({"status": "error", "message": "Неверный телефон или пароль"}), 400

    return jsonify({
        "status": "ok",
        "user": {
            "user_id": user["id"],
            "name": user["name"],
            "phone": user["phone"],
            "balance": user["balance"]
        }
    })


# =========================
# COURSES
# =========================

@app.get("/api/courses")
def get_courses():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, price, author, description, image
        FROM courses
        ORDER BY id DESC
    """)
    rows = cur.fetchall()
    conn.close()

    courses = [dict(r) for r in rows]

    return jsonify({"status": "ok", "courses": courses})


@app.get("/api/courses/one")
def get_course_one():
    course_id = request.args.get("course_id", type=int)
    if not course_id:
        return jsonify({"status": "error", "message": "Нет course_id"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, price, author, description, image
        FROM courses
        WHERE id = ?
    """, (course_id,))
    course = cur.fetchone()

    if not course:
        conn.close()
        return jsonify({"status": "error", "message": "Курс не найден"}), 404

    cur.execute("""
        SELECT id, title, youtube_url, position
        FROM lessons
        WHERE course_id = ?
        ORDER BY position ASC
    """, (course_id,))
    lessons = cur.fetchall()
    conn.close()

    return jsonify({
        "status": "ok",
        "course": {**dict(course), "lessons": [dict(l) for l in lessons]}
    })


@app.post("/api/courses/add")
def add_course():
    data = request.get_json(force=True)

    title = (data.get("title") or "").strip()
    author = (data.get("author") or "").strip()
    description = (data.get("description") or "").strip()
    image_b64 = (data.get("image") or "").strip()
    try:
        price = int(data.get("price", 0))
    except:
        price = 0

    if not title or not author or not description or not image_b64 or price <= 0:
        return jsonify({"status": "error", "message": "Неверные данные"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO courses (title, price, author, description, image)
        VALUES (?, ?, ?, ?, ?)
    """, (title, price, author, description, image_b64))

    cid = cur.lastrowid
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "course_id": cid})


@app.post("/api/courses/update")
def update_course():
    data = request.get_json(force=True)

    cid = data.get("id")
    title = (data.get("title") or "").strip()
    author = (data.get("author") or "").strip()
    description = (data.get("description") or "").strip()
    image_b64 = (data.get("image") or "").strip()
    try:
        price = int(data.get("price", 0))
    except:
        price = 0

    if not cid or not title or not author or not description or price <= 0:
        return jsonify({"status": "error", "message": "Неверные данные"}), 400

    conn = get_db()
    cur = conn.cursor()

    if image_b64:
        cur.execute("""
            UPDATE courses
            SET title = ?, price = ?, author = ?, description = ?, image = ?
            WHERE id = ?
        """, (title, price, author, description, image_b64, cid))
    else:
        cur.execute("""
            UPDATE courses
            SET title = ?, price = ?, author = ?, description = ?
            WHERE id = ?
        """, (title, price, author, description, cid))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.post("/api/courses/delete")
def delete_course():
    data = request.get_json(force=True)
    cid = data.get("id")

    if not cid:
        return jsonify({"status": "error", "message": "Нет id"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM lessons WHERE course_id = ?", (cid,))
    cur.execute("DELETE FROM reviews WHERE course_id = ?", (cid,))
    cur.execute("DELETE FROM cart_items WHERE course_id = ?", (cid,))
    cur.execute("DELETE FROM purchases WHERE course_id = ?", (cid,))
    cur.execute("DELETE FROM courses WHERE id = ?", (cid,))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# =========================
# LESSONS
# =========================

def normalize_youtube_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""

    if "youtu.be/" in url:
        return "https://youtu.be/" + url.split("youtu.be/")[1].split("?")[0]

    if "watch?v=" in url:
        vid = url.split("watch?v=")[1].split("&")[0]
        return f"https://youtu.be/{vid}"

    if 8 <= len(url) <= 20 and " " not in url:
        return f"https://youtu.be/{url}"

    return url


@app.get("/api/lessons")
def get_lessons():
    course_id = request.args.get("course_id", type=int)
    if not course_id:
        return jsonify({"status": "error", "message": "Нет course_id"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, youtube_url, position
        FROM lessons
        WHERE course_id = ?
        ORDER BY position ASC
    """, (course_id,))
    lessons = cur.fetchall()
    conn.close()

    return jsonify({"status": "ok", "lessons": [dict(l) for l in lessons]})


@app.post("/api/lessons/add")
def add_lesson():
    data = request.get_json(force=True)

    course_id = data.get("course_id")
    title = (data.get("title") or "").strip()
    raw_link = (
        data.get("youtube_url")
        or data.get("link")
        or data.get("url")
        or ""
    )
    youtube_url = normalize_youtube_url(raw_link)

    if not course_id or not title or not youtube_url:
        return jsonify({"status": "error", "message": "Неверные данные"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT COALESCE(MAX(position), 0) + 1 AS pos FROM lessons WHERE course_id = ?",
        (course_id,)
    )
    row = cur.fetchone()
    pos = row[0] if row else 1

    cur.execute("""
        INSERT INTO lessons (course_id, title, youtube_url, position)
        VALUES (?, ?, ?, ?)
    """, (course_id, title, youtube_url, pos))

    lesson_id = cur.lastrowid
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "lesson_id": lesson_id})


@app.post("/api/lessons/delete")
def delete_lesson():
    data = request.get_json(force=True)
    lesson_id = data.get("id")

    if not lesson_id:
        return jsonify({"status": "error", "message": "Нет id"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# =========================
# REVIEWS
# =========================

@app.get("/api/reviews")
def get_reviews():
    course_id = request.args.get("course_id", type=int)
    if not course_id:
        return jsonify({"status": "error", "message": "Нет course_id"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT r.id, r.stars, r.text, u.name AS user_name
        FROM reviews r
        JOIN users u ON r.user_id = u.id
        WHERE r.course_id = ?
        ORDER BY r.id DESC
    """, (course_id,))
    rows = cur.fetchall()
    conn.close()

    return jsonify({
        "status": "ok",
        "reviews": [dict(r) for r in rows]
    })


@app.post("/api/reviews/add")
def add_review():
    data = request.get_json(force=True)

    user_id = data.get("user_id")
    course_id = data.get("course_id")
    stars = data.get("stars")
    text = (data.get("text") or "").strip()

    if not user_id or not course_id or not text:
        return jsonify({"status": "error", "message": "Неверные данные"}), 400

    try:
        stars = int(stars)
        if stars < 1 or stars > 5:
            raise ValueError
    except:
        return jsonify({"status": "error", "message": "Оценка должна быть от 1 до 5"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO reviews (user_id, course_id, stars, text)
        VALUES (?, ?, ?, ?)
    """, (user_id, course_id, stars, text))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# =========================
# CART (минимум)
# =========================

@app.post("/api/cart/add")
def cart_add():
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    course_id = data.get("course_id")

    if not user_id or not course_id:
        return jsonify({"status": "error", "message": "Нет user_id или course_id"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id FROM cart_items WHERE user_id = ? AND course_id = ?
    """, (user_id, course_id))
    if cur.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "Курс уже в корзине"}), 400

    cur.execute("""
        INSERT INTO cart_items (user_id, course_id)
        VALUES (?, ?)
    """, (user_id, course_id))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.get("/api/cart")
def cart_get():
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"status": "error", "message": "Нет user_id"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            c.id AS cart_id,
            courses.id AS course_id,
            courses.title,
            courses.price,
            courses.description,
            courses.author,
            courses.image
        FROM cart_items c
        JOIN courses ON c.course_id = courses.id
        WHERE c.user_id = ?
    """, (user_id,))

    rows = cur.fetchall()
    conn.close()

    items = []
    total = 0

    for r in rows:
        r = dict(r)
        total += r["price"]
        items.append({
            "cart_id": r["cart_id"],
            "course_id": r["course_id"],
            "title": r["title"],
            "price": r["price"],
            "author": r["author"],
            "description": r["description"],
            "image": r["image"],
        })

    return jsonify({
        "status": "ok",
        "items": items,
        "total": total
    })


@app.post("/api/cart/remove")
def cart_remove():
    data = request.get_json(force=True)
    cart_id = data.get("cart_id")

    if not cart_id:
        return jsonify({"status": "error", "message": "Нет cart_id"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM cart_items WHERE id = ?", (cart_id,))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.post("/api/cart/buy")
def cart_buy():
    data = request.get_json(force=True)
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"status": "error", "message": "Нет user_id"}), 400

    conn = get_db()
    cur = conn.cursor()

    # корзина
    cur.execute("""
        SELECT c.course_id, courses.price
        FROM cart_items c
        JOIN courses ON c.course_id = courses.id
        WHERE c.user_id = ?
    """, (user_id,))
    rows = cur.fetchall()

    if not rows:
        conn.close()
        return jsonify({"status": "error", "message": "Корзина пуста"}), 400

    total = sum(r["price"] for r in rows)

    # баланс
    cur.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    if not user:
        conn.close()
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    balance = user["balance"]
    if balance < total:
        conn.close()
        return jsonify({"status": "error", "message": "Недостаточно средств"}), 400

    new_balance = balance - total
    cur.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id))

    for r in rows:
        cur.execute("""
            INSERT INTO purchases (user_id, course_id)
            VALUES (?, ?)
        """, (user_id, r["course_id"]))

    cur.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "new_balance": new_balance})


# =========================
# USERS (для Tkinter admin)
# =========================

@app.get("/api/admin/users")
def admin_get_users():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, phone, password, balance
        FROM users
        ORDER BY id DESC
    """)
    rows = cur.fetchall()
    conn.close()

    return jsonify({"status": "ok", "users": [dict(r) for r in rows]})


@app.post("/api/admin/users/update")
def admin_update_user():
    data = request.get_json(force=True)

    uid = data.get("id")
    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()
    balance = data.get("balance")

    if not uid or not name or not phone or not password:
        return jsonify({"status": "error", "message": "Неверные данные"}), 400

    try:
        balance = int(balance)
    except:
        return jsonify({"status": "error", "message": "Баланс должен быть числом"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET name = ?, phone = ?, password = ?, balance = ?
        WHERE id = ?
    """, (name, phone, password, balance, uid))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.post("/api/admin/users/delete")
def admin_delete_user():
    data = request.get_json(force=True)
    uid = data.get("id")

    if not uid:
        return jsonify({"status": "error", "message": "Нет id"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM purchases WHERE user_id = ?", (uid,))
    cur.execute("DELETE FROM cart_items WHERE user_id = ?", (uid,))
    cur.execute("DELETE FROM reviews WHERE user_id = ?", (uid,))
    cur.execute("DELETE FROM users WHERE id = ?", (uid,))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# =========================
# MAIN
# =========================

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
