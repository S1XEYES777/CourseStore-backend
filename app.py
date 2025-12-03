import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
import psycopg2.extras

# ============================================================
# CONFIG
# ============================================================

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

app = Flask(__name__)
CORS(app)  # Разрешаем запросы с фронта


def get_connection():
    # Render PostgreSQL обычно требует sslmode=require, но если уже есть в URL — ок.
    if "sslmode" not in DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    else:
        conn = psycopg2.connect(DATABASE_URL)
    return conn


# ============================================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ
# ============================================================

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # Таблица пользователей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            phone VARCHAR(32) UNIQUE NOT NULL,
            password VARCHAR(128) NOT NULL,
            is_admin BOOLEAN NOT NULL DEFAULT FALSE
        );
    """)

    # Таблица курсов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id SERIAL PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            price NUMERIC(10, 2) NOT NULL DEFAULT 0,
            image TEXT  -- храним dataURL (base64)
        );
    """)

    # Таблица корзины
    cur.execute("""
        CREATE TABLE IF NOT EXISTS carts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
            UNIQUE(user_id, course_id)
        );
    """)

    # Таблица покупок
    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, course_id)
        );
    """)

    conn.commit()
    conn.close()

    ensure_admin_user()


def ensure_admin_user():
    """Создаём админа, если его нет:
       телефон: 77750476284
       пароль: 777
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE phone = %s", ("77750476284",))
    row = cur.fetchone()
    if not row:
        cur.execute("""
            INSERT INTO users (name, phone, password, is_admin)
            VALUES (%s, %s, %s, TRUE)
        """, ("Admin", "77750476284", "777"))
        conn.commit()
    conn.close()


# Инициализация базы при старте приложения
init_db()


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def row_to_user(row):
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "phone": row["phone"],
        "is_admin": row["is_admin"]
    }


def row_to_course(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "price": float(row["price"]) if row["price"] is not None else 0.0,
        "image": row["image"]
    }


# ============================================================
# HEALTHCHECK
# ============================================================

@app.get("/api/ping")
def ping():
    return jsonify({"status": "ok"})


# ============================================================
# АУТЕНТИФИКАЦИЯ / ПОЛЬЗОВАТЕЛИ
# ============================================================

@app.post("/api/register")
def register():
    data = request.get_json(force=True)

    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()

    if not name or not phone or not password:
        return jsonify({
            "status": "error",
            "message": "Заполните имя, телефон и пароль"
        }), 400

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Проверяем, есть ли уже пользователь с этим телефоном
    cur.execute("SELECT id FROM users WHERE phone = %s", (phone,))
    if cur.fetchone():
        conn.close()
        return jsonify({
            "status": "error",
            "message": "Пользователь с таким телефоном уже существует"
        }), 400

    cur.execute("""
        INSERT INTO users (name, phone, password, is_admin)
        VALUES (%s, %s, %s, FALSE)
        RETURNING id, name, phone, is_admin
    """, (name, phone, password))

    user = cur.fetchone()
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "user": row_to_user(user)})


@app.post("/api/login")
def login():
    data = request.get_json(force=True)

    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()

    if not phone or not password:
        return jsonify({
            "status": "error",
            "message": "Введите телефон и пароль"
        }), 400

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT id, name, phone, password, is_admin
        FROM users
        WHERE phone = %s
    """, (phone,))
    row = cur.fetchone()
    conn.close()

    if not row or row["password"] != password:
        return jsonify({
            "status": "error",
            "message": "Неверный телефон или пароль"
        }), 400

    user = {
        "id": row["id"],
        "name": row["name"],
        "phone": row["phone"],
        "is_admin": row["is_admin"]
    }

    return jsonify({"status": "ok", "user": user})


@app.get("/api/users/<int:user_id>")
def get_user_profile(user_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT id, name, phone, is_admin
        FROM users
        WHERE id = %s
    """, (user_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    return jsonify({"status": "ok", "user": row_to_user(row)})


# ============================================================
# КУРСЫ (ПОЛЬЗОВАТЕЛЬСКАЯ ЧАСТЬ)
# ============================================================

@app.get("/api/courses")
def get_courses():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT id, title, description, price, image
        FROM courses
        ORDER BY id DESC
    """)
    rows = cur.fetchall()
    conn.close()

    courses = [row_to_course(r) for r in rows]
    return jsonify({"status": "ok", "courses": courses})


@app.get("/api/courses/<int:course_id>")
def get_course(course_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT id, title, description, price, image
        FROM courses
        WHERE id = %s
    """, (course_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"status": "error", "message": "Курс не найден"}), 404

    return jsonify({"status": "ok", "course": row_to_course(row)})


# ============================================================
# КОРЗИНА
# ============================================================

@app.get("/api/cart/<int:user_id>")
def get_cart(user_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT c.id, c.title, c.description, c.price, c.image
        FROM carts cart
        JOIN courses c ON c.id = cart.course_id
        WHERE cart.user_id = %s
        ORDER BY cart.id DESC
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()

    courses = [row_to_course(r) for r in rows]
    return jsonify({"status": "ok", "courses": courses})


@app.post("/api/cart/add")
def add_to_cart():
    data = request.get_json(force=True)

    user_id = data.get("user_id")
    course_id = data.get("course_id")

    if not user_id or not course_id:
        return jsonify({"status": "error", "message": "user_id и course_id обязательны"}), 400

    conn = get_connection()
    cur = conn.cursor()

    # Нельзя добавить, если уже куплен
    cur.execute("""
        SELECT id FROM purchases
        WHERE user_id = %s AND course_id = %s
    """, (user_id, course_id))
    if cur.fetchone():
        conn.close()
        return jsonify({
            "status": "error",
            "message": "Курс уже куплен"
        }), 400

    # Добавляем в корзину (если ещё нет)
    cur.execute("""
        INSERT INTO carts (user_id, course_id)
        VALUES (%s, %s)
        ON CONFLICT (user_id, course_id) DO NOTHING
    """, (user_id, course_id))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.post("/api/cart/remove")
def remove_from_cart():
    data = request.get_json(force=True)

    user_id = data.get("user_id")
    course_id = data.get("course_id")

    if not user_id or not course_id:
        return jsonify({"status": "error", "message": "user_id и course_id обязательны"}), 400

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM carts
        WHERE user_id = %s AND course_id = %s
    """, (user_id, course_id))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.post("/api/cart/checkout")
def checkout_cart():
    data = request.get_json(force=True)

    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "message": "user_id обязателен"}), 400

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Берём курсы из корзины
    cur.execute("""
        SELECT course_id FROM carts
        WHERE user_id = %s
    """, (user_id,))
    rows = cur.fetchall()

    if not rows:
        conn.close()
        return jsonify({"status": "error", "message": "Корзина пуста"}), 400

    # Добавляем в покупки
    for r in rows:
        cid = r["course_id"]
        cur.execute("""
            INSERT INTO purchases (user_id, course_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (user_id, cid))

    # Очищаем корзину
    cur.execute("DELETE FROM carts WHERE user_id = %s", (user_id,))
    conn.commit()

    # Возвращаем купленные курсы
    cur.execute("""
        SELECT c.id, c.title, c.description, c.price, c.image
        FROM purchases p
        JOIN courses c ON c.id = p.course_id
        WHERE p.user_id = %s
        ORDER BY p.id DESC
    """, (user_id,))
    courses = [row_to_course(r) for r in cur.fetchall()]

    conn.close()

    return jsonify({"status": "ok", "courses": courses})


# ============================================================
# ПОКУПКИ ПОЛЬЗОВАТЕЛЯ
# ============================================================

@app.get("/api/purchases/<int:user_id>")
def get_purchases(user_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT c.id, c.title, c.description, c.price, c.image
        FROM purchases p
        JOIN courses c ON c.id = p.course_id
        WHERE p.user_id = %s
        ORDER BY p.id DESC
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()

    courses = [row_to_course(r) for r in rows]
    return jsonify({"status": "ok", "courses": courses})


# ============================================================
# АДМИН: КУРСЫ
# ============================================================

def is_admin_user(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT is_admin FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return False
    return bool(row[0])


@app.post("/api/admin/courses")
def admin_create_course():
    data = request.get_json(force=True)

    user_id = data.get("user_id")
    if not user_id or not is_admin_user(user_id):
        return jsonify({"status": "error", "message": "Нет прав"}), 403

    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    price = data.get("price", 0)
    image = data.get("image")  # dataURL (base64) либо None

    if not title:
        return jsonify({"status": "error", "message": "Название обязательно"}), 400

    try:
        price = float(price)
    except Exception:
        price = 0

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        INSERT INTO courses (title, description, price, image)
        VALUES (%s, %s, %s, %s)
        RETURNING id, title, description, price, image
    """, (title, description, price, image))
    row = cur.fetchone()
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "course": row_to_course(row)})


@app.get("/api/admin/courses")
def admin_list_courses():
    user_id = request.args.get("user_id", type=int)
    if not user_id or not is_admin_user(user_id):
        return jsonify({"status": "error", "message": "Нет прав"}), 403

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT id, title, description, price, image
        FROM courses
        ORDER BY id DESC
    """)
    rows = cur.fetchall()
    conn.close()

    courses = [row_to_course(r) for r in rows]
    return jsonify({"status": "ok", "courses": courses})


if __name__ == "__main__":
    # Локальный запуск
    app.run(host="0.0.0.0", port=5000, debug=True)
