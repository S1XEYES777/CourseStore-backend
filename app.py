import os
import sqlite3
from flask import Flask, request, jsonify
from flask_cors import CORS

# ============================================
#  НАСТРОЙКИ БАЗЫ ДАННЫХ (SQLite)
# ============================================
DB_NAME = "database.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # dict-подобные строки
    # включаем внешние ключи
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # ===== USERS =====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT UNIQUE,
        password TEXT NOT NULL,
        balance INTEGER DEFAULT 0
    );
    """)

    # ===== COURSES =====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        price INTEGER NOT NULL,
        author TEXT,
        description TEXT,
        image TEXT    -- base64
    );
    """)

    # ===== LESSONS =====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        youtube_url TEXT,
        position INTEGER DEFAULT 1,
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    """)

    # ===== REVIEWS =====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        stars INTEGER NOT NULL DEFAULT 5,
        text TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    """)

    # ===== CART ITEMS =====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cart_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    """)

    # ===== PURCHASES =====
    cur.execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()


# ============================================
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def row_to_dict(row):
    return dict(row) if row is not None else None


def course_public_dict(row_or_dict):
    """
    Приведение курса к формату,
    как в старом JSON backend:
    + image_url (data:image/jpeg;base64,...)
    """
    if isinstance(row_or_dict, sqlite3.Row):
        c = dict(row_or_dict)
    else:
        c = dict(row_or_dict)

    img = c.get("image") or ""
    if img and not img.startswith("data:"):
        c["image_url"] = "data:image/jpeg;base64," + img
    elif img:
        c["image_url"] = img
    else:
        c["image_url"] = None
    return c


def normalize_youtube_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""

    if "youtu.be/" in url:
        return "https://youtu.be/" + url.split("youtu.be/")[1].split("?")[0]

    if "watch?v=" in url:
        vid = url.split("watch?v=")[1].split("&")[0]
        return f"https://youtu.be/{vid}"

    # Если вставили только ID
    if 8 <= len(url) <= 20 and " " not in url:
        return f"https://youtu.be/{url}"

    return url


# ============================================
#  FLASK ПРИЛОЖЕНИЕ
# ============================================

app = Flask(__name__)
CORS(app, supports_credentials=True)


# ============================================
#  ГЛОБАЛЬНЫЙ ХЭНДЛЕР ОШИБОК
# ============================================

@app.errorhandler(Exception)
def handle_any_error(e):
    print("SERVER ERROR:", repr(e))
    return jsonify({"status": "error", "message": str(e)}), 500


# ============================================
#  PING / STATUS
# ============================================

@app.get("/api/ping")
def ping():
    return {"status": "ok", "message": "backend running (sqlite mode)"}


@app.get("/")
def index():
    return {"status": "running", "service": "CourseStore SQLite Backend"}


# ============================================
#  АВТОРИЗАЦИЯ: /api/register, /api/login
# ============================================

@app.post("/api/register")
def register():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()

    if not name or not phone or not password:
        return jsonify({"status": "error", "message": "Заполни все поля"}), 400

    conn = get_connection()
    cur = conn.cursor()

    # проверка телефона
    cur.execute("SELECT id FROM users WHERE phone = ?", (phone,))
    if cur.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "Телефон уже зарегистрирован"}), 400

    cur.execute(
        "INSERT INTO users (name, phone, password, balance) VALUES (?, ?, ?, 0)",
        (name, phone, password),
    )
    uid = cur.lastrowid
    conn.commit()
    conn.close()

    user = {
        "id": uid,
        "name": name,
        "phone": phone,
        "balance": 0,
    }

    # формат как в твоём JSON app.py
    return jsonify({"status": "ok", "user": user})


@app.post("/api/login")
def login():
    data = request.get_json(force=True)
    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, phone, balance FROM users WHERE phone = ? AND password = ?",
        (phone, password),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"status": "error", "message": "Неверный телефон или пароль"}), 400

    user = row_to_dict(row)
    return jsonify({"status": "ok", "user": user})


# ============================================
#  КУРСЫ: /api/courses, /api/courses/one, /api/course
# ============================================

@app.get("/api/courses")
def api_get_courses():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, title, price, author, description, image FROM courses ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()

    courses = [course_public_dict(row) for row in rows]
    return jsonify({"status": "ok", "courses": courses})


def get_course_with_lessons(course_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, title, price, author, description, image FROM courses WHERE id = ?",
        (course_id,),
    )
    course = cur.fetchone()
    if not course:
        conn.close()
        return None

    cur.execute(
        "SELECT id, course_id, title, youtube_url, position "
        "FROM lessons WHERE course_id = ? ORDER BY position ASC",
        (course_id,),
    )
    lessons = [row_to_dict(r) for r in cur.fetchall()]
    conn.close()

    c_pub = course_public_dict(course)
    c_pub["lessons"] = lessons
    return c_pub


@app.get("/api/courses/one")
def api_get_course_one():
    course_id = request.args.get("course_id", type=int)
    if not course_id:
        return jsonify({"status": "error", "message": "Нет course_id"}), 400

    c_pub = get_course_with_lessons(course_id)
    if not c_pub:
        return jsonify({"status": "error", "message": "Курс не найден"}), 404

    return jsonify({"status": "ok", "course": c_pub})


@app.get("/api/course")
def api_get_course_single_alias():
    return api_get_course_one()


@app.post("/api/courses/add")
def api_add_course():
    data = request.get_json(force=True)

    title = (data.get("title") or "").strip()
    author = (data.get("author") or "").strip()
    description = (data.get("description") or "").strip()
    image_b64 = (data.get("image") or "").strip()

    try:
        price = int(data.get("price") or 0)
    except ValueError:
        price = 0

    if not title or not author or not description or not image_b64 or price <= 0:
        return jsonify({"status": "error", "message": "Неверные данные курса"}), 400

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO courses (title, price, author, description, image) "
        "VALUES (?, ?, ?, ?, ?)",
        (title, price, author, description, image_b64),
    )
    cid = cur.lastrowid
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "course_id": cid})


@app.post("/api/courses/update")
def api_update_course():
    data = request.get_json(force=True)

    cid = data.get("id")
    title = (data.get("title") or "").strip()
    author = (data.get("author") or "").strip()
    description = (data.get("description") or "").strip()
    image_b64 = (data.get("image") or "").strip()

    try:
        price = int(data.get("price") or 0)
    except ValueError:
        price = 0

    if not cid or not title or not author or not description or price <= 0:
        return jsonify({"status": "error", "message": "Неверные данные"}), 400

    conn = get_connection()
    cur = conn.cursor()

    if image_b64:
        cur.execute(
            "UPDATE courses SET title=?, price=?, author=?, description=?, image=? "
            "WHERE id=?",
            (title, price, author, description, image_b64, cid),
        )
    else:
        cur.execute(
            "UPDATE courses SET title=?, price=?, author=?, description=? "
            "WHERE id=?",
            (title, price, author, description, cid),
        )

    if cur.rowcount == 0:
        conn.close()
        return jsonify({"status": "error", "message": "Курс не найден"}), 404

    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


@app.post("/api/courses/delete")
def api_delete_course():
    data = request.get_json(force=True)
    cid = data.get("id")

    if not cid:
        return jsonify({"status": "error", "message": "Нет id"}), 400

    conn = get_connection()
    cur = conn.cursor()

    # вручную чистим связанные данные (на случай, если FK не сработает)
    cur.execute("DELETE FROM lessons WHERE course_id = ?", (cid,))
    cur.execute("DELETE FROM reviews WHERE course_id = ?", (cid,))
    cur.execute("DELETE FROM cart_items WHERE course_id = ?", (cid,))
    cur.execute("DELETE FROM purchases WHERE course_id = ?", (cid,))
    cur.execute("DELETE FROM courses WHERE id = ?", (cid,))

    if cur.rowcount == 0:
        conn.close()
        return jsonify({"status": "error", "message": "Курс не найден"}), 404

    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


# ============================================
#  УРОКИ: /api/lessons
# ============================================

@app.get("/api/lessons")
def api_get_lessons():
    course_id = request.args.get("course_id", type=int)
    if not course_id:
        return jsonify({"status": "error", "message": "Нет course_id"}), 400

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, course_id, title, youtube_url, position "
        "FROM lessons WHERE course_id = ? ORDER BY position ASC",
        (course_id,),
    )
    rows = cur.fetchall()
    conn.close()

    lessons = [row_to_dict(r) for r in rows]
    return jsonify({"status": "ok", "lessons": lessons})


@app.post("/api/lessons/add")
def api_add_lesson():
    data = request.get_json(force=True)

    course_id = data.get("course_id")
    title = (data.get("title") or "").strip()

    raw_link = (
        data.get("youtube_url")
        or data.get("link")
        or data.get("url")
        or ""
    ).strip()
    youtube_url = normalize_youtube_url(raw_link)

    if not course_id or not title or not youtube_url:
        return jsonify({"status": "error", "message": "Неверные данные урока"}), 400

    conn = get_connection()
    cur = conn.cursor()

    # Если position не передали — ставим в конец
    position = data.get("position")
    if position is None:
        cur.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 AS pos FROM lessons WHERE course_id = ?",
            (course_id,),
        )
        row = cur.fetchone()
        position = row["pos"] if row and "pos" in row.keys() else 1

    cur.execute(
        "INSERT INTO lessons (course_id, title, youtube_url, position) "
        "VALUES (?, ?, ?, ?)",
        (course_id, title, youtube_url, int(position)),
    )

    lid = cur.lastrowid
    conn.commit()
    conn.close()

    # в старом JSON backend возвращали {"id": lid}
    return jsonify({"status": "ok", "id": lid})


@app.post("/api/lessons/delete")
def api_delete_lesson():
    data = request.get_json(force=True)
    lid = data.get("id")

    if not lid:
        return jsonify({"status": "error", "message": "Нет id"}), 400

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM lessons WHERE id = ?", (lid,))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ============================================
#  ОТЗЫВЫ: /api/reviews, /api/reviews/add
# ============================================

@app.get("/api/reviews")
def api_get_reviews():
    course_id = request.args.get("course_id", type=int)
    if not course_id:
        return jsonify({"status": "error", "message": "Нет course_id"}), 400

    conn = get_connection()
    cur = conn.cursor()

    # добавим имя пользователя (user_name)
    cur.execute("""
        SELECT r.id, r.user_id, r.course_id, r.stars, r.text,
               u.name AS user_name
        FROM reviews r
        JOIN users u ON r.user_id = u.id
        WHERE r.course_id = ?
        ORDER BY r.id DESC
    """, (course_id,))

    rows = cur.fetchall()
    conn.close()

    reviews = [row_to_dict(r) for r in rows]
    return jsonify({"status": "ok", "reviews": reviews})


@app.post("/api/reviews/add")
def api_add_review():
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
    except Exception:
        return jsonify({"status": "error", "message": "Оценка 1–5"}), 400

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO reviews (user_id, course_id, stars, text) "
        "VALUES (?, ?, ?, ?)",
        (user_id, course_id, stars, text),
    )
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ============================================
#  КОРЗИНА: /api/cart
# ============================================

@app.get("/api/cart")
def api_get_cart():
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"status": "error", "message": "Нет user_id"}), 400

    conn = get_connection()
    cur = conn.cursor()

    # берём элементы корзины
    cur.execute(
        "SELECT id, user_id, course_id FROM cart_items WHERE user_id = ?",
        (user_id,),
    )
    cart_rows = cur.fetchall()

    items = []

    for row in cart_rows:
        r = row_to_dict(row)
        cid = r["course_id"]

        cur.execute(
            "SELECT id, title, price, author, description, image "
            "FROM courses WHERE id = ?",
            (cid,),
        )
        course = cur.fetchone()
        if not course:
            continue

        items.append({
            "id": r["id"],
            "course_id": cid,
            "course": course_public_dict(course),
        })

    conn.close()
    return jsonify({"status": "ok", "items": items})


@app.post("/api/cart/add")
def api_cart_add():
    data = request.get_json(force=True)

    user_id = data.get("user_id")
    course_id = data.get("course_id")

    if not user_id or not course_id:
        return jsonify({"status": "error", "message": "Нет user_id или course_id"}), 400

    conn = get_connection()
    cur = conn.cursor()

    # проверяем, что курс существует
    cur.execute("SELECT id FROM courses WHERE id = ?", (course_id,))
    if not cur.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "Курс не найден"}), 404

    # не добавляем дубликаты
    cur.execute(
        "SELECT id FROM cart_items WHERE user_id = ? AND course_id = ?",
        (user_id, course_id),
    )
    if cur.fetchone():
        conn.close()
        return jsonify({"status": "ok", "message": "Уже в корзине"})

    cur.execute(
        "INSERT INTO cart_items (user_id, course_id) VALUES (?, ?)",
        (user_id, course_id),
    )
    cid = cur.lastrowid
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "id": cid})


@app.post("/api/cart/remove")
def api_cart_remove():
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    course_id = data.get("course_id")

    if not user_id or not course_id:
        return jsonify({"status": "error", "message": "Нет user_id или course_id"}), 400

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM cart_items WHERE user_id = ? AND course_id = ?",
        (user_id, course_id),
    )
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.post("/api/cart/clear")
def api_cart_clear():
    data = request.get_json(force=True)
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"status": "error", "message": "Нет user_id"}), 400

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.post("/api/cart/buy")
def api_cart_buy():
    """
    Простая логика покупки:
    - считаем total
    - проверяем баланс
    - уменьшаем баланс
    - создаём записи в purchases
    - очищаем корзину
    """
    data = request.get_json(force=True)
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"status": "error", "message": "Нет user_id"}), 400

    conn = get_connection()
    cur = conn.cursor()

    # Товары в корзине
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

    total = sum(row["price"] for row in rows)

    # Баланс пользователя
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

    # Покупки
    for row in rows:
        cur.execute(
            "INSERT INTO purchases (user_id, course_id) VALUES (?, ?)",
            (user_id, row["course_id"]),
        )

    # Очищаем корзину
    cur.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "new_balance": new_balance})


# ============================================
#  ПОЛЬЗОВАТЕЛИ / АДМИН: /api/admin/users
# ============================================

@app.get("/api/admin/users")
def api_admin_users():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, phone, password, balance FROM users ORDER BY id DESC"
    )
    rows = cur.fetchall()
    conn.close()

    users = [row_to_dict(r) for r in rows]
    return jsonify({"status": "ok", "users": users})


@app.post("/api/admin/users/update")
def api_admin_user_update():
    data = request.get_json(force=True)

    uid = data.get("id")
    if not uid:
        return jsonify({"status": "error", "message": "Нет id"}), 400

    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()
    balance = data.get("balance")

    conn = get_connection()
    cur = conn.cursor()

    # получаем текущего пользователя
    cur.execute("SELECT id, name, phone, password, balance FROM users WHERE id = ?", (uid,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    current = row_to_dict(row)

    # если поле пустое — оставляем старое значение
    new_name = name or current["name"]
    new_phone = phone or current["phone"]
    new_password = password or current["password"]

    try:
        new_balance = int(balance) if balance is not None and balance != "" else current["balance"]
    except ValueError:
        conn.close()
        return jsonify({"status": "error", "message": "Баланс должен быть числом"}), 400

    cur.execute("""
        UPDATE users
        SET name = ?, phone = ?, password = ?, balance = ?
        WHERE id = ?
    """, (new_name, new_phone, new_password, new_balance, uid))

    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


@app.post("/api/admin/users/delete")
def api_admin_user_delete():
    data = request.get_json(force=True)
    uid = data.get("id")
    if not uid:
        return jsonify({"status": "error", "message": "Нет id"}), 400

    conn = get_connection()
    cur = conn.cursor()

    # удаляем связанные данные
    cur.execute("DELETE FROM purchases WHERE user_id = ?", (uid,))
    cur.execute("DELETE FROM cart_items WHERE user_id = ?", (uid,))
    cur.execute("DELETE FROM reviews WHERE user_id = ?", (uid,))
    cur.execute("DELETE FROM users WHERE id = ?", (uid,))

    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


# ============================================
#  АЛИАСЫ /api/users (если вдруг где-то используются)
# ============================================

@app.get("/api/users")
def api_get_users():
    return api_admin_users()


@app.post("/api/users/update")
def api_update_user():
    return api_admin_user_update()


@app.post("/api/users/delete")
def api_delete_user():
    return api_admin_user_delete()


# ============================================
#  ЗАПУСК ПРИЛОЖЕНИЯ
# ============================================

if __name__ == "__main__":
    # создаём таблицы, если их ещё нет
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
