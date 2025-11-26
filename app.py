import os
import sqlite3
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS

# ============================================================
#  CONFIG
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

app = Flask(__name__)
CORS(app)


# ============================================================
#  DB UTILS
# ============================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(course_id) REFERENCES courses(id)
        );
    """)

    conn.commit()
    conn.close()


def row_to_dict(row):
    return {k: row[k] for k in row.keys()}


# ============================================================
#  SERVICE
# ============================================================

@app.route("/api/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok"})


# ============================================================
#  AUTH (регистрация / логин)
# ============================================================

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    phone = data.get("phone", "").strip()
    password = data.get("password", "").strip()

    if not name or not phone or not password:
        return jsonify({"status": "error", "message": "Заполни все поля"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE phone = ?", (phone,))
    exists = cur.fetchone()
    if exists:
        conn.close()
        return jsonify({"status": "error", "message": "Номер уже зарегистрирован"})

    cur.execute(
        "INSERT INTO users (name, phone, password, balance) VALUES (?, ?, ?, 0)",
        (name, phone, password)
    )
    conn.commit()
    uid = cur.lastrowid
    conn.close()

    return jsonify({
        "status": "ok",
        "user": {
            "user_id": uid,
            "name": name,
            "phone": phone,
            "balance": 0
        }
    })


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    phone = data.get("phone", "").strip()
    password = data.get("password", "").strip()

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE phone = ?", (phone,))
    row = cur.fetchone()
    conn.close()

    if not row or row["password"] != password:
        return jsonify({"status": "error", "message": "Неверный телефон или пароль"})

    user = row_to_dict(row)
    return jsonify({
        "status": "ok",
        "user": {
            "user_id": user["id"],
            "name": user["name"],
            "phone": user["phone"],
            "balance": user["balance"]
        }
    })


# ============================================================
#  PROFILE / BALANCE / МОИ КУРСЫ
# ============================================================

@app.route("/api/profile", methods=["GET"])
def profile():
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"status": "error", "message": "user_id required"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    user = row_to_dict(row)

    # количество купленных курсов
    cur.execute("SELECT COUNT(*) AS c FROM purchases WHERE user_id = ?", (user_id,))
    cnt = cur.fetchone()["c"]

    conn.close()

    return jsonify({
        "status": "ok",
        "user": {
            "id": user["id"],
            "name": user["name"],
            "phone": user["phone"],
            "balance": user["balance"],
            "purchases": cnt
        }
    })


@app.route("/api/profile/add_balance", methods=["POST"])
def add_balance():
    data = request.get_json(force=True)
    user_id = int(data.get("user_id", 0))
    amount = int(data.get("amount", 0))

    if not user_id or amount <= 0:
        return jsonify({"status": "error", "message": "Некорректная сумма"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id))
    conn.commit()

    cur.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()

    return jsonify({"status": "ok", "balance": row["balance"]})


@app.route("/api/my-courses", methods=["GET"])
def my_courses():
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"status": "error", "message": "user_id required"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT c.id, c.title, c.author, c.price, c.description, c.image
        FROM purchases p
        JOIN courses c ON c.id = p.course_id
        WHERE p.user_id = ?
        GROUP BY c.id
    """, (user_id,))
    courses = [row_to_dict(r) for r in cur.fetchall()]

    conn.close()
    return jsonify({"status": "ok", "courses": courses})


# ============================================================
#  COURSES
# ============================================================

@app.route("/api/courses", methods=["GET"])
def get_courses():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM courses ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()

    courses = []
    for r in rows:
        d = row_to_dict(r)
        # для фронта/Tk
        d["image_url"] = None
        courses.append(d)

    return jsonify({"status": "ok", "courses": courses})


@app.route("/api/courses/add", methods=["POST"])
def add_course():
    data = request.get_json(force=True)
    title = data.get("title", "").strip()
    price = int(data.get("price", 0))
    author = data.get("author", "").strip()
    description = data.get("description", "").strip()
    image = data.get("image")

    if not title or not author or not description or price <= 0:
        return jsonify({"status": "error", "message": "Некорректные данные курса"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO courses (title, price, author, description, image)
        VALUES (?, ?, ?, ?, ?)
    """, (title, price, author, description, image))
    conn.commit()
    cid = cur.lastrowid
    conn.close()

    return jsonify({"status": "ok", "id": cid, "course_id": cid})


@app.route("/api/courses/update", methods=["POST"])
def update_course():
    data = request.get_json(force=True)
    cid = int(data.get("id", 0))
    title = data.get("title", "").strip()
    price = int(data.get("price", 0))
    author = data.get("author", "").strip()
    description = data.get("description", "").strip()
    image = data.get("image", None)

    if not cid or not title or not author or not description or price <= 0:
        return jsonify({"status": "error", "message": "Некорректные данные"}), 400

    conn = get_db()
    cur = conn.cursor()

    if image:
        cur.execute("""
            UPDATE courses
            SET title=?, price=?, author=?, description=?, image=?
            WHERE id=?
        """, (title, price, author, description, image, cid))
    else:
        cur.execute("""
            UPDATE courses
            SET title=?, price=?, author=?, description=?
            WHERE id=?
        """, (title, price, author, description, cid))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.route("/api/courses/delete", methods=["POST"])
def delete_course():
    data = request.get_json(force=True)
    cid = int(data.get("id", 0))

    if not cid:
        return jsonify({"status": "error", "message": "id required"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM lessons WHERE course_id = ?", (cid,))
    cur.execute("DELETE FROM cart_items WHERE course_id = ?", (cid,))
    cur.execute("DELETE FROM purchases WHERE course_id = ?", (cid,))
    cur.execute("DELETE FROM reviews WHERE course_id = ?", (cid,))
    cur.execute("DELETE FROM courses WHERE id = ?", (cid,))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ============================================================
#  LESSONS
# ============================================================

@app.route("/api/lessons", methods=["GET"])
def get_lessons():
    course_id = request.args.get("course_id", type=int)
    if not course_id:
        return jsonify({"status": "error", "lessons": []})

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM lessons
        WHERE course_id = ?
        ORDER BY position ASC, id ASC
    """, (course_id,))
    rows = cur.fetchall()
    conn.close()

    lessons = [row_to_dict(r) for r in rows]
    return jsonify({"status": "ok", "lessons": lessons})


@app.route("/api/lessons/add", methods=["POST"])
def add_lesson():
    data = request.get_json(force=True)
    course_id = int(data.get("course_id", 0))
    title = data.get("title", "").strip()
    youtube_url = data.get("youtube_url", "").strip()
    position = int(data.get("position", 0))

    if not course_id or not title or not youtube_url:
        return jsonify({"status": "error", "message": "Поля урока пустые"}), 400

    conn = get_db()
    cur = conn.cursor()

    if position <= 0:
        cur.execute("SELECT COALESCE(MAX(position),0)+1 AS p FROM lessons WHERE course_id = ?", (course_id,))
        position = cur.fetchone()["p"]

    cur.execute("""
        INSERT INTO lessons (course_id, title, youtube_url, position)
        VALUES (?, ?, ?, ?)
    """, (course_id, title, youtube_url, position))
    conn.commit()
    lid = cur.lastrowid
    conn.close()

    return jsonify({"status": "ok", "id": lid})


@app.route("/api/lessons/delete", methods=["POST"])
def delete_lesson():
    data = request.get_json(force=True)
    lid = int(data.get("id", 0))

    if not lid:
        return jsonify({"status": "error", "message": "id required"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM lessons WHERE id = ?", (lid,))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ============================================================
#  CART
# ============================================================

@app.route("/api/cart", methods=["GET"])
def get_cart():
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"status": "error", "message": "user_id required", "items": []})

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            ci.id AS cart_id,
            c.id AS course_id,
            c.title,
            c.author,
            c.price,
            c.description,
            c.image
        FROM cart_items ci
        JOIN courses c ON c.id = ci.course_id
        WHERE ci.user_id = ?
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()

    items = []
    for r in rows:
        d = row_to_dict(r)
        d["image_url"] = None
        items.append(d)

    return jsonify({"status": "ok", "items": items})


@app.route("/api/cart/add", methods=["POST"])
def cart_add():
    data = request.get_json(force=True)
    user_id = int(data.get("user_id", 0))
    course_id = int(data.get("course_id", 0))

    if not user_id or not course_id:
        return jsonify({"status": "error", "message": "user_id и course_id обязательны"}), 400

    conn = get_db()
    cur = conn.cursor()

    # не дублируем
    cur.execute("""
        SELECT id FROM cart_items
        WHERE user_id = ? AND course_id = ?
    """, (user_id, course_id))
    if cur.fetchone():
        conn.close()
        return jsonify({"status": "ok", "message": "Уже в корзине"})

    cur.execute("""
        INSERT INTO cart_items (user_id, course_id)
        VALUES (?, ?)
    """, (user_id, course_id))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.route("/api/cart/remove", methods=["POST"])
def cart_remove():
    data = request.get_json(force=True)
    cart_id = int(data.get("cart_id", 0))

    if not cart_id:
        return jsonify({"status": "error", "message": "cart_id required"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM cart_items WHERE id = ?", (cart_id,))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.route("/api/cart/buy", methods=["POST"])
def cart_buy():
    data = request.get_json(force=True)
    user_id = int(data.get("user_id", 0))

    if not user_id:
        return jsonify({"status": "error", "message": "user_id required"}), 400

    conn = get_db()
    cur = conn.cursor()

    # все позиции
    cur.execute("""
        SELECT ci.course_id, c.price
        FROM cart_items ci
        JOIN courses c ON c.id = ci.course_id
        WHERE ci.user_id = ?
    """, (user_id,))
    rows = cur.fetchall()

    if not rows:
        conn.close()
        return jsonify({"status": "error", "message": "Корзина пуста"})

    total = sum(r["price"] for r in rows)

    # проверяем баланс
    cur.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    u = cur.fetchone()
    if not u:
        conn.close()
        return jsonify({"status": "error", "message": "Пользователь не найден"})

    balance = u["balance"]
    if balance < total:
        conn.close()
        return jsonify({"status": "error", "message": "Недостаточно средств"})

    # списываем деньги
    cur.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (total, user_id))

    # добавляем покупки (без дублей)
    for r in rows:
        cid = r["course_id"]
        cur.execute("""
            SELECT id FROM purchases
            WHERE user_id = ? AND course_id = ?
        """, (user_id, cid))
        exists = cur.fetchone()
        if not exists:
            cur.execute("""
                INSERT INTO purchases (user_id, course_id, created_at)
                VALUES (?, ?, ?)
            """, (user_id, cid, datetime.utcnow().isoformat()))

    # очищаем корзину
    cur.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "total": total})


# ============================================================
#  ADMIN: USERS
# ============================================================

@app.route("/api/admin/users", methods=["GET"])
def admin_users():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, phone, balance FROM users ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()

    users = [row_to_dict(r) for r in rows]
    return jsonify({"status": "ok", "users": users})


@app.route("/api/admin/users/update", methods=["POST"])
def admin_user_update():
    data = request.get_json(force=True)
    uid = int(data.get("id", 0))
    name = data.get("name", "").strip()
    phone = data.get("phone", "").strip()
    password = data.get("password", "").strip()
    balance = int(data.get("balance", 0))

    if not uid or not name or not phone:
        return jsonify({"status": "error", "message": "Некорректные данные"}), 400

    conn = get_db()
    cur = conn.cursor()

    if password:
        cur.execute("""
            UPDATE users
            SET name=?, phone=?, password=?, balance=?
            WHERE id=?
        """, (name, phone, password, balance, uid))
    else:
        cur.execute("""
            UPDATE users
            SET name=?, phone=?, balance=?
            WHERE id=?
        """, (name, phone, balance, uid))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.route("/api/admin/users/delete", methods=["POST"])
def admin_user_delete():
    data = request.get_json(force=True)
    uid = int(data.get("id", 0))

    if not uid:
        return jsonify({"status": "error", "message": "id required"}), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM cart_items WHERE user_id = ?", (uid,))
    cur.execute("DELETE FROM purchases WHERE user_id = ?", (uid,))
    cur.execute("DELETE FROM reviews WHERE user_id = ?", (uid,))
    cur.execute("DELETE FROM users WHERE id = ?", (uid,))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ============================================================
#  ENTRY POINT
# ============================================================

init_db()

if __name__ == "__main__":
    # локальный запуск
    app.run(host="0.0.0.0", port=5000, debug=True)
