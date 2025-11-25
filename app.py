from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import base64
import os

app = Flask(__name__)
CORS(app)

DB = "database.db"


# ============================================================
# DB INIT
# ============================================================
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT UNIQUE,
        password TEXT,
        balance INTEGER DEFAULT 0
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS courses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        price INTEGER,
        author TEXT,
        description TEXT,
        image TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS lessons(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER,
        title TEXT,
        youtube_url TEXT,
        position INTEGER
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS reviews(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        course_id INTEGER,
        stars INTEGER,
        text TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS cart(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        course_id INTEGER
    )
    """)

    conn.commit()
    conn.close()


# ============================================================
# 🔥 ПИНГ — проверка сервера
# ============================================================
@app.get("/api/ping")
def ping():
    return jsonify({"status": "ok"})


# ============================================================
# 🟦 COURSES
# ============================================================
@app.get("/api/courses")
def get_courses():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT * FROM courses ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()

    return jsonify({"status": "ok", "courses": [dict(r) for r in rows]})


@app.post("/api/courses/add")
def add_course():
    data = request.get_json()

    title = data.get("title")
    price = data.get("price")
    author = data.get("author")
    desc = data.get("description")
    img = data.get("image")

    if not title or not price or not author or not desc or not img:
        return jsonify({"status": "error", "message": "Неверные данные"}), 400

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        INSERT INTO courses (title, price, author, description, image)
        VALUES (?, ?, ?, ?, ?)
    """, (title, price, author, desc, img))

    course_id = c.lastrowid
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "course_id": course_id})


@app.post("/api/courses/update")
def update_course():
    data = request.get_json()

    course_id = data.get("id")
    title = data.get("title")
    price = data.get("price")
    author = data.get("author")
    description = data.get("description")
    img = data.get("image")

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    if img:
        c.execute("""
            UPDATE courses SET title=?, price=?, author=?, description=?, image=?
            WHERE id=?
        """, (title, price, author, description, img, course_id))
    else:
        c.execute("""
            UPDATE courses SET title=?, price=?, author=?, description=?
            WHERE id=?
        """, (title, price, author, description, course_id))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.post("/api/courses/delete")
def delete_course():
    data = request.get_json()
    course_id = data.get("id")

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("DELETE FROM lessons WHERE course_id=?", (course_id,))
    c.execute("DELETE FROM reviews WHERE course_id=?", (course_id,))
    c.execute("DELETE FROM cart WHERE course_id=?", (course_id,))
    c.execute("DELETE FROM courses WHERE id=?", (course_id,))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ============================================================
# 🎬 LESSONS
# ============================================================
@app.get("/api/lessons")
def get_lessons():
    cid = request.args.get("course_id")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT * FROM lessons
        WHERE course_id=?
        ORDER BY position ASC
    """, (cid,))

    rows = c.fetchall()
    conn.close()

    return jsonify({"status": "ok", "lessons": [dict(r) for r in rows]})


@app.post("/api/lessons/add")
def add_lesson():
    data = request.get_json()

    cid = data.get("course_id")
    title = data.get("title")
    url = data.get("youtube_url")

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM lessons WHERE course_id=?", (cid,))
    pos = c.fetchone()[0]

    c.execute("""
        INSERT INTO lessons(course_id, title, youtube_url, position)
        VALUES (?, ?, ?, ?)
    """, (cid, title, url, pos))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.post("/api/lessons/delete")
def delete_lesson():
    data = request.get_json()
    lid = data.get("id")

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("DELETE FROM lessons WHERE id=?", (lid,))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ============================================================
# 👤 USERS
# ============================================================
@app.get("/api/admin/users")
def admin_get_users():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT * FROM users ORDER BY id DESC")
    rows = c.fetchall()

    conn.close()
    return jsonify({"status": "ok", "users": [dict(r) for r in rows]})


@app.post("/api/admin/users/update")
def admin_update_user():
    data = request.get_json()

    uid = data.get("id")
    name = data.get("name")
    phone = data.get("phone")
    password = data.get("password")
    balance = data.get("balance")

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
        UPDATE users SET name=?, phone=?, password=?, balance=?
        WHERE id=?
    """, (name, phone, password, balance, uid))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.post("/api/admin/users/delete")
def admin_delete_user():
    data = request.get_json()
    uid = data.get("id")

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("DELETE FROM reviews WHERE user_id=?", (uid,))
    c.execute("DELETE FROM cart WHERE user_id=?", (uid,))
    c.execute("DELETE FROM users WHERE id=?", (uid,))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ============================================================
# 🛒 CART
# ============================================================
@app.post("/api/cart/add")
def cart_add():
    data = request.get_json()

    uid = data.get("user_id")
    cid = data.get("course_id")

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT id FROM cart WHERE user_id=? AND course_id=?", (uid, cid))
    if c.fetchone():
        return jsonify({"status": "error", "message": "Уже в корзине"})

    c.execute("INSERT INTO cart(user_id, course_id) VALUES (?, ?)", (uid, cid))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.get("/api/cart")
def cart_get():
    uid = request.args.get("user_id")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
    SELECT cart.id AS cart_id, courses.*
    FROM cart
    JOIN courses ON courses.id = cart.course_id
    WHERE cart.user_id=?
    """, (uid,))

    rows = c.fetchall()

    conn.close()

    total = sum(r["price"] for r in rows)

    return jsonify({
        "status": "ok",
        "items": [dict(r) for r in rows],
        "total": total
    })


# ============================================================
# ⭐ REVIEWS
# ============================================================
@app.post("/api/reviews/add")
def add_review():
    data = request.get_json()

    uid = data.get("user_id")
    cid = data.get("course_id")
    stars = data.get("stars")
    text = data.get("text")

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
        INSERT INTO reviews(user_id, course_id, stars, text)
        VALUES (?, ?, ?, ?)
    """, (uid, cid, stars, text))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ============================================================
# STARTUP
# ============================================================
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
