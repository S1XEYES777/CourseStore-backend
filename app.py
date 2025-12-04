import os
import uuid
import datetime
from functools import wraps

from flask import (
    Flask, request, jsonify, send_from_directory, g
)
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image

import psycopg2
import psycopg2.extras

# =======================================
#   НАСТРОЙКИ ПРИЛОЖЕНИЯ
# =======================================
app = Flask(__name__)
CORS(app, supports_credentials=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_ROOT = os.path.join(BASE_DIR, "uploads")

COURSE_IMG_FOLDER = os.path.join(UPLOAD_ROOT, "course_images")
AVATAR_FOLDER = os.path.join(UPLOAD_ROOT, "avatars")
VIDEO_FOLDER = os.path.join(UPLOAD_ROOT, "videos")

for folder in (COURSE_IMG_FOLDER, AVATAR_FOLDER, VIDEO_FOLDER):
    os.makedirs(folder, exist_ok=True)

# Ограничение размера файла (например, до 500 МБ)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024

ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "webp"}
ALLOWED_VIDEO_EXT = {"mp4", "mov", "mkv", "avi"}

# PostgreSQL: URL берём из переменной окружения DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL")


# =======================================
#   ПОДКЛЮЧЕНИЕ К БД
# =======================================
def get_db():
    if "db" not in g:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL не задан в переменных окружения")
        g.db = psycopg2.connect(DATABASE_URL, sslmode="require")
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    cur = db.cursor()
    # users
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT,
            email TEXT,
            phone TEXT UNIQUE,
            password_hash TEXT,
            avatar_url TEXT,
            is_admin BOOLEAN DEFAULT FALSE,
            token TEXT
        );
    """)
    # courses
    cur.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            price NUMERIC(10, 2) DEFAULT 0,
            image_url TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    # lessons
    cur.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            id SERIAL PRIMARY KEY,
            course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            video_url TEXT NOT NULL,
            order_index INTEGER DEFAULT 0
        );
    """)
    # cart_items
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cart_items (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
            UNIQUE (user_id, course_id)
        );
    """)
    # purchases
    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
            purchased_at TIMESTAMP DEFAULT NOW(),
            UNIQUE (user_id, course_id)
        );
    """)
    db.commit()
    cur.close()

    # создаём админа, если нет
    ensure_admin_user()


def ensure_admin_user():
    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    phone = "77750476284"
    cur.execute("SELECT * FROM users WHERE phone = %s", (phone,))
    user = cur.fetchone()
    if not user:
        password_hash = generate_password_hash("777")
        cur.execute("""
            INSERT INTO users (name, email, phone, password_hash, is_admin)
            VALUES (%s, %s, %s, %s, %s)
        """, ("Admin", "admin@example.com", phone, password_hash, True))
        db.commit()
    cur.close()


# =======================================
#   ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =======================================
def allowed_file(filename, allowed_ext):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_ext


def resize_image(input_path, output_path, target_size):
    """
    target_size: (width, height)
    """
    img = Image.open(input_path)
    img = img.convert("RGB")
    img.thumbnail(target_size)
    img.save(output_path, optimize=True, quality=85)


def compress_video(input_path, output_path, target_height=720):
    """
    Пытаемся сжать видео, если есть moviepy/ffmpeg.
    Если не получилось – просто сохраняем исходный файл.
    """
    try:
        from moviepy.editor import VideoFileClip
        clip = VideoFileClip(input_path)
        w, h = clip.size

        if h > target_height:
            new_w = int(w * target_height / h)
            clip = clip.resize(newsize=(new_w, target_height))

        clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            bitrate="2000k",
            threads=2
        )
        clip.close()
        if os.path.exists(input_path):
            os.remove(input_path)
    except Exception:
        # Если возникла ошибка – просто переименовываем файл
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
        except Exception:
            pass
        os.replace(input_path, output_path)


def generate_token():
    return uuid.uuid4().hex


def get_current_user(require_auth=True):
    """
    Получаем пользователя по токену из заголовка:
      X-Token: <token>
    """
    token = request.headers.get("X-Token")
    if not token:
        if require_auth:
            return None
        return None

    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM users WHERE token = %s", (token,))
    user = cur.fetchone()
    cur.close()

    if not user and require_auth:
        return None
    return user


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_current_user(require_auth=True)
        if not user:
            return jsonify({"error": "Необходима авторизация"}), 401
        g.current_user = user
        return func(*args, **kwargs)
    return wrapper


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_current_user(require_auth=True)
        if not user:
            return jsonify({"error": "Необходима авторизация"}), 401
        if not user["is_admin"]:
            return jsonify({"error": "Доступ только для админа"}), 403
        g.current_user = user
        return func(*args, **kwargs)
    return wrapper


# =======================================
#   СТАТИКА: ФАЙЛЫ В uploads/
# =======================================
@app.route("/uploads/<path:filename>")
def serve_uploads(filename):
    return send_from_directory(UPLOAD_ROOT, filename)


# =======================================
#   АУТЕНТИФИКАЦИЯ
# =======================================
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    phone = data.get("phone", "").strip()
    password = data.get("password", "").strip()

    if not phone or not password:
        return jsonify({"error": "Телефон и пароль обязательны"}), 400

    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("SELECT id FROM users WHERE phone = %s", (phone,))
    if cur.fetchone():
        cur.close()
        return jsonify({"error": "Пользователь с таким телефоном уже существует"}), 400

    password_hash = generate_password_hash(password)
    token = generate_token()

    cur.execute("""
        INSERT INTO users (name, email, phone, password_hash, token)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, name, email, phone, avatar_url, is_admin, token
    """, (name, email, phone, password_hash, token))
    user = cur.fetchone()
    db.commit()
    cur.close()

    return jsonify({"user": dict(user)})


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    phone = data.get("phone", "").strip()
    password = data.get("password", "").strip()

    if not phone or not password:
        return jsonify({"error": "Телефон и пароль обязательны"}), 400

    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM users WHERE phone = %s", (phone,))
    user = cur.fetchone()

    if not user:
        cur.close()
        return jsonify({"error": "Неверный телефон или пароль"}), 400

    if not check_password_hash(user["password_hash"], password):
        cur.close()
        return jsonify({"error": "Неверный телефон или пароль"}), 400

    # обновим токен
    token = generate_token()
    cur.execute("UPDATE users SET token = %s WHERE id = %s", (token, user["id"]))
    db.commit()

    cur.execute("SELECT id, name, email, phone, avatar_url, is_admin, token FROM users WHERE id = %s", (user["id"],))
    user_updated = cur.fetchone()
    cur.close()

    return jsonify({"user": dict(user_updated)})


@app.route("/api/me", methods=["GET"])
@login_required
def me():
    user = g.current_user
    data = {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "phone": user["phone"],
        "avatar_url": user["avatar_url"],
        "is_admin": user["is_admin"],
    }
    return jsonify({"user": data})


# =======================================
#   АВАТАР ПОЛЬЗОВАТЕЛЯ
# =======================================
@app.route("/api/user/avatar", methods=["POST"])
@login_required
def upload_avatar():
    user = g.current_user
    file = request.files.get("file")

    if not file:
        return jsonify({"error": "Файл не отправлен"}), 400

    if not allowed_file(file.filename, ALLOWED_IMAGE_EXT):
        return jsonify({"error": "Недопустимый формат изображения"}), 400

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"user_{user['id']}_{uuid.uuid4().hex}.{ext}"

    tmp_path = os.path.join(AVATAR_FOLDER, f"tmp_{filename}")
    final_path = os.path.join(AVATAR_FOLDER, filename)

    file.save(tmp_path)
    resize_image(tmp_path, final_path, (256, 256))

    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    avatar_url = f"/uploads/avatars/{filename}"

    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE users SET avatar_url = %s WHERE id = %s", (avatar_url, user["id"]))
    db.commit()
    cur.close()

    return jsonify({"status": "ok", "avatar_url": avatar_url})


# =======================================
#   ЗАГРУЗКА ИЗОБРАЖЕНИЙ (КУРСЫ)
# =======================================
@app.route("/api/upload/image", methods=["POST"])
@admin_required
def upload_image():
    img_type = request.form.get("type", "course")
    file = request.files.get("file")

    if not file:
        return jsonify({"error": "Файл не отправлен"}), 400

    if not allowed_file(file.filename, ALLOWED_IMAGE_EXT):
        return jsonify({"error": "Недопустимый формат изображения"}), 400

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"

    if img_type == "avatar":
        folder = AVATAR_FOLDER
        target_size = (256, 256)
        url_prefix = "avatars"
    else:
        folder = COURSE_IMG_FOLDER
        target_size = (800, 450)
        url_prefix = "course_images"

    tmp_path = os.path.join(folder, f"tmp_{filename}")
    final_path = os.path.join(folder, filename)

    file.save(tmp_path)
    resize_image(tmp_path, final_path, target_size)

    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    file_url = f"/uploads/{url_prefix}/{filename}"
    return jsonify({"status": "ok", "url": file_url})


# =======================================
#   ЗАГРУЗКА ВИДЕО
# =======================================
@app.route("/api/upload/video", methods=["POST"])
@admin_required
def upload_video():
    """
    form-data:
      file: видео
      course_id: id курса
    """
    course_id = request.form.get("course_id")
    if not course_id:
        return jsonify({"error": "course_id обязателен"}), 400

    file = request.files.get("file")
    if not file:
        return jsonify({"error": "Файл не отправлен"}), 400

    if not allowed_file(file.filename, ALLOWED_VIDEO_EXT):
        return jsonify({"error": "Недопустимый формат видео"}), 400

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename_raw = f"course{course_id}_{uuid.uuid4().hex}.{ext}"

    tmp_path = os.path.join(VIDEO_FOLDER, f"tmp_{filename_raw}")
    final_path = os.path.join(VIDEO_FOLDER, filename_raw)

    file.save(tmp_path)
    compress_video(tmp_path, final_path)

    file_url = f"/uploads/videos/{filename_raw}"

    # урок в БД создаём отдельным запросом /api/admin/lessons
    return jsonify({
        "status": "ok",
        "url": file_url,
        "course_id": int(course_id)
    })


# =======================================
#   КУРСЫ
# =======================================
@app.route("/api/courses", methods=["GET"])
def list_courses():
    """
    Опционально берём токен, чтобы показать is_purchased.
    """
    token = request.headers.get("X-Token")
    user_id = None
    if token:
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT id FROM users WHERE token = %s", (token,))
        row = cur.fetchone()
        cur.close()
        if row:
            user_id = row[0]

    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("""
        SELECT c.id, c.title, c.description, c.price, c.image_url, c.created_at
        FROM courses c
        ORDER BY c.created_at DESC;
    """)
    courses = cur.fetchall()

    result = []
    for c in courses:
        item = dict(c)
        item["price"] = float(item["price"]) if item["price"] is not None else 0.0
        item["is_purchased"] = False
        if user_id:
            cur2 = db.cursor()
            cur2.execute("""
                SELECT 1 FROM purchases
                WHERE user_id = %s AND course_id = %s
            """, (user_id, c["id"]))
            if cur2.fetchone():
                item["is_purchased"] = True
            cur2.close()
        result.append(item)

    cur.close()
    return jsonify({"courses": result})


@app.route("/api/courses/<int:course_id>", methods=["GET"])
def get_course(course_id):
    """
    Если курс не куплен – уроки не отдаем.
    """
    token = request.headers.get("X-Token")
    user_id = None
    if token:
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT id FROM users WHERE token = %s", (token,))
        row = cur.fetchone()
        cur.close()
        if row:
            user_id = row[0]

    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""
        SELECT id, title, description, price, image_url, created_at
        FROM courses WHERE id = %s
    """, (course_id,))
    course = cur.fetchone()

    if not course:
        cur.close()
        return jsonify({"error": "Курс не найден"}), 404

    course_data = dict(course)
    course_data["price"] = float(course_data["price"]) if course_data["price"] is not None else 0.0

    is_purchased = False
    if user_id:
        cur.execute("""
            SELECT 1 FROM purchases
            WHERE user_id = %s AND course_id = %s
        """, (user_id, course_id))
        if cur.fetchone():
            is_purchased = True

    course_data["is_purchased"] = is_purchased

    lessons = []
    if is_purchased:
        cur.execute("""
            SELECT id, title, video_url, order_index
            FROM lessons
            WHERE course_id = %s
            ORDER BY order_index ASC, id ASC
        """, (course_id,))
        rows = cur.fetchall()
        for r in rows:
            lessons.append(dict(r))

    course_data["lessons"] = lessons
    cur.close()
    return jsonify({"course": course_data})


@app.route("/api/admin/courses", methods=["POST"])
@admin_required
def create_course():
    data = request.get_json(force=True)
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    price = data.get("price", 0)
    image_url = data.get("image_url", "").strip()

    if not title:
        return jsonify({"error": "Название курса обязательно"}), 400

    try:
        price_val = float(price)
    except (TypeError, ValueError):
        price_val = 0.0

    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""
        INSERT INTO courses (title, description, price, image_url)
        VALUES (%s, %s, %s, %s)
        RETURNING id, title, description, price, image_url, created_at
    """, (title, description, price_val, image_url))
    course = cur.fetchone()
    db.commit()
    cur.close()

    course = dict(course)
    course["price"] = float(course["price"]) if course["price"] is not None else 0.0
    return jsonify({"course": course})


@app.route("/api/admin/lessons", methods=["POST"])
@admin_required
def create_lesson():
    data = request.get_json(force=True)
    course_id = data.get("course_id")
    title = data.get("title", "").strip()
    video_url = data.get("video_url", "").strip()
    order_index = data.get("order_index", 0)

    if not course_id or not title or not video_url:
        return jsonify({"error": "course_id, title и video_url обязательны"}), 400

    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""
        INSERT INTO lessons (course_id, title, video_url, order_index)
        VALUES (%s, %s, %s, %s)
        RETURNING id, course_id, title, video_url, order_index
    """, (course_id, title, video_url, order_index))
    lesson = cur.fetchone()
    db.commit()
    cur.close()

    return jsonify({"lesson": dict(lesson)})


# =======================================
#   КОРЗИНА
# =======================================
@app.route("/api/cart", methods=["GET"])
@login_required
def get_cart():
    user = g.current_user
    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("""
        SELECT ci.course_id,
               c.title,
               c.price,
               c.image_url
        FROM cart_items ci
        JOIN courses c ON c.id = ci.course_id
        WHERE ci.user_id = %s
    """, (user["id"],))
    items = cur.fetchall()
    cur.close()

    result = []
    total = 0.0
    for i in items:
        price = float(i["price"]) if i["price"] is not None else 0.0
        result.append({
            "course_id": i["course_id"],
            "title": i["title"],
            "price": price,
            "image_url": i["image_url"]
        })
        total += price

    return jsonify({"items": result, "total": total})


@app.route("/api/cart/add", methods=["POST"])
@login_required
def cart_add():
    user = g.current_user
    data = request.get_json(force=True)
    course_id = data.get("course_id")

    if not course_id:
        return jsonify({"error": "course_id обязателен"}), 400

    db = get_db()
    cur = db.cursor()

    # Нельзя добавить, если уже куплен
    cur.execute("""
        SELECT 1 FROM purchases
        WHERE user_id = %s AND course_id = %s
    """, (user["id"], course_id))
    if cur.fetchone():
        cur.close()
        return jsonify({"error": "Курс уже куплен"}), 400

    # Добавляем в корзину
    try:
        cur.execute("""
            INSERT INTO cart_items (user_id, course_id)
            VALUES (%s, %s)
            ON CONFLICT (user_id, course_id) DO NOTHING
        """, (user["id"], course_id))
        db.commit()
    finally:
        cur.close()

    return jsonify({"status": "ok"})


@app.route("/api/cart/remove", methods=["POST"])
@login_required
def cart_remove():
    user = g.current_user
    data = request.get_json(force=True)
    course_id = data.get("course_id")

    if not course_id:
        return jsonify({"error": "course_id обязателен"}), 400

    db = get_db()
    cur = db.cursor()
    cur.execute("""
        DELETE FROM cart_items
        WHERE user_id = %s AND course_id = %s
    """, (user["id"], course_id))
    db.commit()
    cur.close()

    return jsonify({"status": "ok"})


@app.route("/api/cart/checkout", methods=["POST"])
@login_required
def cart_checkout():
    """
    Фейковая оплата: всё, что в корзине, становится купленным.
    """
    user = g.current_user
    db = get_db()
    cur = db.cursor()

    # Получаем все курсы из корзины
    cur.execute("""
        SELECT course_id FROM cart_items
        WHERE user_id = %s
    """, (user["id"],))
    rows = cur.fetchall()
    course_ids = [r[0] for r in rows]

    if not course_ids:
        cur.close()
        return jsonify({"error": "Корзина пуста"}), 400

    # Создаём покупки
    for cid in course_ids:
        cur.execute("""
            INSERT INTO purchases (user_id, course_id, purchased_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, course_id) DO NOTHING
        """, (user["id"], cid, datetime.datetime.utcnow()))

    # Очищаем корзину
    cur.execute("""
        DELETE FROM cart_items
        WHERE user_id = %s
    """, (user["id"],))
    db.commit()
    cur.close()

    return jsonify({"status": "ok"})


# =======================================
#   МОИ КУРСЫ
# =======================================
@app.route("/api/my-courses", methods=["GET"])
@login_required
def my_courses():
    user = g.current_user
    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("""
        SELECT c.id, c.title, c.description, c.price, c.image_url, c.created_at
        FROM purchases p
        JOIN courses c ON c.id = p.course_id
        WHERE p.user_id = %s
        ORDER BY p.purchased_at DESC
    """, (user["id"],))
    rows = cur.fetchall()
    cur.close()

    result = []
    for c in rows:
        item = dict(c)
        item["price"] = float(item["price"]) if item["price"] is not None else 0.0
        result.append(item)

    return jsonify({"courses": result})


# =======================================
#   ПРОВЕРКА
# =======================================
@app.route("/api/ping")
def ping():
    return jsonify({"status": "ok"})


# =======================================
#   ЗАПУСК ПРИ ЛОКАЛЬНОМ СТАРТЕ
# =======================================
if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
