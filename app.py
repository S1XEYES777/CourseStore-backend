import os
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS

import psycopg2
import psycopg2.extras

# =====================================
#  Flask + CORS
# =====================================

app = Flask(__name__)
CORS(app)


# =====================================
#  DATABASE_URL (Render + локально)
# =====================================

# На Render НУЖНО создать переменную окружения DATABASE_URL
# со ссылкой на PostgreSQL.
DATABASE_URL = os.getenv("DATABASE_URL")

# ФОЛБЭК: если переменная не задана (локальный запуск) —
# используем твой URL Render Postgres.
if not DATABASE_URL:
    DATABASE_URL = (
        "postgresql://coursestore_user:"
        "QpbQO0QAxRIwMRLVShTDgVSplVOMiZVQ"
        "@dpg-d4d05l0gjchc73dmfld0-a.oregon-postgres.render.com"
        "/coursestore?sslmode=require"
    )


def get_db():
    """
    Подключение к PostgreSQL.
    Возвращает connection с RealDictCursor.
    """
    return psycopg2.connect(
        DATABASE_URL,
        sslmode="require",
        cursor_factory=psycopg2.extras.RealDictCursor
    )


# =====================================
#  ИНИЦИАЛИЗАЦИЯ ТАБЛИЦ
# =====================================

def init_db():
    conn = get_db()
    cur = conn.cursor()

    # Пользователи
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            balance INTEGER NOT NULL DEFAULT 0,
            avatar TEXT
        );
        """
    )

    # Курсы
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS courses (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            price INTEGER NOT NULL,
            author TEXT,
            description TEXT,
            image TEXT
        );
        """
    )

    # Уроки
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS lessons (
            id SERIAL PRIMARY KEY,
            course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
            title TEXT,
            video_url TEXT,
            position INTEGER DEFAULT 1
        );
        """
    )

    # Корзина
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS cart_items (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE
        );
        """
    )

    # Покупки
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS purchases (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # Отзывы
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reviews (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            course_id INTEGER REFERENCES courses(id),
            stars INTEGER DEFAULT 5,
            text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    conn.commit()
    conn.close()


# ВАЖНО: создаём таблицы при старте приложения
init_db()


# =====================================
#  СЛУЖЕБНОЕ (PING)
# =====================================

@app.get("/api/ping")
def ping():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


# =====================================
#  AUTH: REGISTER + LOGIN
# =====================================

@app.post("/api/register")
def register():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()

    if not name or not phone or not password:
        return {"status": "error", "message": "Заполните все поля"}

    conn = get_db()
    cur = conn.cursor()

    # Проверяем телефон
    cur.execute("SELECT id FROM users WHERE phone = %s", (phone,))
    if cur.fetchone():
        conn.close()
        return {"status": "error", "message": "Телефон уже зарегистрирован"}

    cur.execute(
        """
        INSERT INTO users (name, phone, password)
        VALUES (%s, %s, %s)
        RETURNING *;
        """,
        (name, phone, password),
    )
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
            "avatar": user["avatar"],
        },
    }


@app.post("/api/login")
def login():
    data = request.get_json(force=True)
    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE phone = %s", (phone,))
    row = cur.fetchone()
    conn.close()

    if not row or row["password"] != password:
        return {"status": "error", "message": "Неверный телефон или пароль"}

    return {
        "status": "ok",
        "user": {
            "user_id": row["id"],
            "name": row["name"],
            "phone": row["phone"],
            "balance": row["balance"],
            "avatar": row["avatar"],
        },
    }


# =====================================
#  USER / PROFILE
# =====================================

@app.get("/api/user")
def get_user():
    uid = request.args.get("user_id")
    if not uid:
        return {"status": "error", "message": "user_id обязателен"}

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s", (uid,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return {"status": "error", "message": "Пользователь не найден"}

    return {
        "status": "ok",
        "user": {
            "user_id": row["id"],
            "name": row["name"],
            "phone": row["phone"],
            "balance": row["balance"],
            "avatar": row["avatar"],
        },
    }


@app.post("/api/avatar")
def update_avatar():
    data = request.get_json(force=True)
    uid = data.get("user_id")
    avatar = data.get("avatar")

    if not uid or not avatar:
        return {"status": "error", "message": "user_id и avatar обязательны"}

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET avatar = %s WHERE id = %s", (avatar, uid))
    conn.commit()
    conn.close()

    return {"status": "ok"}


# =====================================
#  COURSES + LESSONS
# =====================================

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
    if not cid:
        return {"status": "error", "message": "course_id обязателен"}

    conn = get_db()
    cur = conn.cursor()

    # сам курс
    cur.execute("SELECT * FROM courses WHERE id = %s", (cid,))
    course = cur.fetchone()

    if not course:
        conn.close()
        return {"status": "error", "message": "Курс не найден"}

    # уроки
    cur.execute(
        """
        SELECT * FROM lessons
        WHERE course_id = %s
        ORDER BY position ASC, id ASC
        """,
        (cid,),
    )
    lessons = cur.fetchall()

    # отзывы
    cur.execute(
        """
        SELECT r.*, u.name AS user_name
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        WHERE r.course_id = %s
        ORDER BY r.created_at DESC;
        """,
        (cid,),
    )
    reviews = cur.fetchall()

    conn.close()

    return {
        "status": "ok",
        "course": course,
        "lessons": lessons,
        "reviews": reviews,
    }


@app.post("/api/courses/add")
def add_course():
    data = request.get_json(force=True)
    title = data.get("title")
    price = data.get("price")
    author = data.get("author")
    description = data.get("description")
    image = data.get("image")

    if not title or price is None:
        return {"status": "error", "message": "Название и цена обязательны"}

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO courses (title, price, author, description, image)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
        """,
        (title, price, author, description, image),
    )
    cid = cur.fetchone()["id"]
    conn.commit()
    conn.close()

    return {"status": "ok", "course_id": cid}


@app.post("/api/lessons/add")
def add_lesson():
    data = request.get_json(force=True)
    course_id = data.get("course_id")
    title = data.get("title")
    video_url = data.get("youtube_url")  # в admin.html именно youtube_url
    position = data.get("position", 1)

    if not course_id or not title or not video_url:
        return {"status": "error", "message": "course_id, title, video_url обязательны"}

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO lessons (course_id, title, video_url, position)
        VALUES (%s, %s, %s, %s);
        """,
        (course_id, title, video_url, position),
    )
    conn.commit()
    conn.close()

    return {"status": "ok"}


@app.post("/api/lessons/delete")
def delete_lesson():
    data = request.get_json(force=True)
    lid = data.get("id")

    if not lid:
        return {"status": "error", "message": "id урока обязателен"}

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM lessons WHERE id = %s", (lid,))
    conn.commit()
    conn.close()

    return {"status": "ok"}


# =====================================
#  CART + BUY
# =====================================

@app.get("/api/cart")
def cart_get():
    uid = request.args.get("user_id")
    if not uid:
        return {"status": "error", "message": "user_id обязателен"}

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ci.id AS cart_id,
               c.id,
               c.title,
               c.price,
               c.author,
               c.image
        FROM cart_items ci
        JOIN courses c ON c.id = ci.course_id
        WHERE ci.user_id = %s;
        """,
        (uid,),
    )
    rows = cur.fetchall()
    conn.close()

    return {"status": "ok", "items": rows}


@app.post("/api/cart/add")
def cart_add():
    data = request.get_json(force=True)
    uid = data.get("user_id")
    cid = data.get("course_id")

    if not uid or not cid:
        return {"status": "error", "message": "user_id и course_id обязательны"}

    conn = get_db()
    cur = conn.cursor()

    # уже в корзине?
    cur.execute(
        """
        SELECT id FROM cart_items
        WHERE user_id = %s AND course_id = %s;
        """,
        (uid, cid),
    )
    if cur.fetchone():
        conn.close()
        return {"status": "ok"}

    cur.execute(
        """
        INSERT INTO cart_items (user_id, course_id)
        VALUES (%s, %s);
        """,
        (uid, cid),
    )
    conn.commit()
    conn.close()

    return {"status": "ok"}


@app.post("/api/cart/remove")
def cart_remove():
    data = request.get_json(force=True)
    cart_id = data.get("cart_id")

    if not cart_id:
        return {"status": "error", "message": "cart_id обязателен"}

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM cart_items WHERE id = %s", (cart_id,))
    conn.commit()
    conn.close()

    return {"status": "ok"}


@app.post("/api/cart/buy")
def buy():
    data = request.get_json(force=True)
    uid = data.get("user_id")

    if not uid:
        return {"status": "error", "message": "user_id обязателен"}

    conn = get_db()
    cur = conn.cursor()

    # содержимое корзины
    cur.execute(
        """
        SELECT c.id, c.price
        FROM cart_items ci
        JOIN courses c ON c.id = ci.course_id
        WHERE ci.user_id = %s;
        """,
        (uid,),
    )
    items = cur.fetchall()

    if not items:
        conn.close()
        return {"status": "error", "message": "Корзина пуста"}

    total = sum(i["price"] for i in items)

    # баланс пользователя
    cur.execute("SELECT balance FROM users WHERE id = %s", (uid,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return {"status": "error", "message": "Пользователь не найден"}

    balance = row["balance"]

    if balance < total:
        conn.close()
        return {"status": "error", "message": "Недостаточно средств"}

    # списываем деньги
    cur.execute(
        """
        UPDATE users
        SET balance = balance - %s
        WHERE id = %s;
        """,
        (total, uid),
    )

    # добавляем покупки
    for it in items:
        cur.execute(
            """
            INSERT INTO purchases (user_id, course_id)
            VALUES (%s, %s);
            """,
            (uid, it["id"]),
        )

    # очищаем корзину
    cur.execute("DELETE FROM cart_items WHERE user_id = %s;", (uid,))

    conn.commit()
    conn.close()

    return {"status": "ok"}


@app.get("/api/my-courses")
def my_courses():
    uid = request.args.get("user_id")
    if not uid:
        return {"status": "error", "message": "user_id обязателен"}

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT c.*
        FROM purchases p
        JOIN courses c ON c.id = p.course_id
        WHERE p.user_id = %s
        GROUP BY c.id
        ORDER BY c.id DESC;
        """,
        (uid,),
    )
    rows = cur.fetchall()
    conn.close()

    return {"status": "ok", "courses": rows}


# =====================================
#  REVIEWS
# =====================================

@app.post("/api/reviews/add")
def add_review():
    data = request.get_json(force=True)
    uid = data.get("user_id")
    cid = data.get("course_id")
    stars = data.get("stars", 5)
    text = data.get("text", "")

    if not uid or not cid:
        return {"status": "error", "message": "user_id и course_id обязательны"}

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO reviews (user_id, course_id, stars, text)
        VALUES (%s, %s, %s, %s);
        """,
        (uid, cid, stars, text),
    )
    conn.commit()
    conn.close()

    return {"status": "ok"}


# =====================================
#  LOCAL RUN
# =====================================

if __name__ == "__main__":
    # для локального запуска
    app.run(host="0.0.0.0", port=5000, debug=True)
