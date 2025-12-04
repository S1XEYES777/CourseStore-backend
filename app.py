import os
import uuid
import secrets
import hashlib
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

# ============================================================
# APP & CONFIG
# ============================================================

app = Flask(__name__)
CORS(app)

# DATABASE_URL для Render (PostgreSQL)
db_url = os.environ.get("DATABASE_URL", "sqlite:///coursestore.db")
# Render иногда добавляет postgres:// вместо postgresql://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Базовая папка для загрузок
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_ROOT = os.path.join(BASE_DIR, "uploads")
os.makedirs(os.path.join(UPLOAD_ROOT, "avatars"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_ROOT, "course_images"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_ROOT, "videos"), exist_ok=True)


# ============================================================
# HELPERS
# ============================================================

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def check_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash


def generate_token() -> str:
    return secrets.token_hex(32)


def get_current_user():
    token = request.headers.get("X-Token")
    if not token:
        return None
    return User.query.filter_by(token=token).first()


def course_to_dict(course, user=None):
    """
    Преобразование курса в словарь для API /api/courses и т.п.
    """
    # Счётчики статистики
    students_count = (
        db.session.query(db.func.count(db.distinct(Purchase.user_id)))
        .filter(Purchase.course_id == course.id)
        .scalar()
    ) or 0
    sales_count = (
        db.session.query(db.func.count(Purchase.id))
        .filter(Purchase.course_id == course.id)
        .scalar()
    ) or 0
    revenue = (
        db.session.query(db.func.coalesce(db.func.sum(Purchase.price_paid), 0))
        .filter(Purchase.course_id == course.id)
        .scalar()
    ) or 0

    # Флаг покупки пользователем
    is_purchased = False
    if user:
        is_purchased = (
            Purchase.query.filter_by(user_id=user.id, course_id=course.id).first()
            is not None
        )

    return {
        "id": course.id,
        "title": course.title,
        "description": course.description,
        "image_url": course.image_url,
        "price_full": course.price_full,
        "price_discount": course.price_discount,
        "price": course.price,
        "students_count": students_count,
        "sales_count": sales_count,
        "revenue": revenue,
        "is_purchased": is_purchased,
    }


def lesson_to_dict(lesson):
    return {
        "id": lesson.id,
        "course_id": lesson.course_id,
        "title": lesson.title,
        "video_url": lesson.video_url,
        "order_index": lesson.order_index,
    }


# ============================================================
# MODELS
# ============================================================

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    name = db.Column(db.String(120))
    email = db.Column(db.String(255))
    avatar_url = db.Column(db.String(255))

    token = db.Column(db.String(128), unique=True)
    is_admin = db.Column(db.Boolean, default=True)  # упростим: все админы

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(255))

    price_full = db.Column(db.Integer, nullable=False, default=0)
    price_discount = db.Column(db.Integer)  # может быть None
    price = db.Column(db.Integer, nullable=False, default=0)  # текущая цена (для удобства)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Lesson(db.Model):
    __tablename__ = "lessons"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    video_url = db.Column(db.String(255), nullable=False)
    order_index = db.Column(db.Integer, default=0)

    course = db.relationship("Course", backref=db.backref("lessons", lazy=True))


class CartItem(db.Model):
    __tablename__ = "cart_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)

    user = db.relationship("User", backref=db.backref("cart_items", lazy=True))
    course = db.relationship("Course", backref=db.backref("carted_by", lazy=True))


class Purchase(db.Model):
    __tablename__ = "purchases"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    price_paid = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("purchases", lazy=True))
    course = db.relationship("Course", backref=db.backref("purchases", lazy=True))


# ============================================================
# DB INIT
# ============================================================

with app.app_context():
    db.create_all()


# ============================================================
# STATIC / UPLOADS
# ============================================================

@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(UPLOAD_ROOT, filename)


# ============================================================
# AUTH
# ============================================================

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(force=True)
    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()

    if not phone or not password:
        return jsonify({"error": "Телефон и пароль обязательны"}), 400

    if User.query.filter_by(phone=phone).first():
        return jsonify({"error": "Пользователь с таким телефоном уже существует"}), 400

    user = User(
        phone=phone,
        password_hash=hash_password(password),
        name=data.get("name"),
        email=data.get("email"),
        token=generate_token(),
    )
    db.session.add(user)
    db.session.commit()

    return jsonify({
        "user": {
            "id": user.id,
            "phone": user.phone,
            "name": user.name,
            "email": user.email,
            "avatar_url": user.avatar_url,
            "token": user.token,
        }
    })


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    phone = (data.get("phone") or "").strip()
    password = (data.get("password") or "").strip()

    user = User.query.filter_by(phone=phone).first()
    if not user or not check_password(password, user.password_hash):
        return jsonify({"error": "Неверный телефон или пароль"}), 400

    if not user.token:
        user.token = generate_token()
        db.session.commit()

    return jsonify({
        "user": {
            "id": user.id,
            "phone": user.phone,
            "name": user.name,
            "email": user.email,
            "avatar_url": user.avatar_url,
            "token": user.token,
        }
    })


@app.route("/api/me", methods=["GET"])
def me():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Не авторизован"}), 401

    return jsonify({
        "user": {
            "id": user.id,
            "phone": user.phone,
            "name": user.name,
            "email": user.email,
            "avatar_url": user.avatar_url,
            "token": user.token,
        }
    })


# ============================================================
# AVATAR UPLOAD
# ============================================================

@app.route("/api/user/avatar", methods=["POST"])
def upload_avatar():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Не авторизован"}), 401

    file = request.files.get("file")
    if not file:
        return jsonify({"error": "Файл не найден"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    fname = f"{uuid.uuid4().hex}{ext}"
    rel_path = os.path.join("avatars", fname)
    abs_path = os.path.join(UPLOAD_ROOT, rel_path)
    file.save(abs_path)

    user.avatar_url = f"/uploads/{rel_path}"
    db.session.commit()

    return jsonify({"avatar_url": user.avatar_url})


# ============================================================
# COURSES (PUBLIC)
# ============================================================

@app.route("/api/courses", methods=["GET"])
def get_courses():
    user = get_current_user()
    courses = Course.query.order_by(Course.id.desc()).all()
    return jsonify({
        "courses": [course_to_dict(c, user=user) for c in courses]
    })


@app.route("/api/courses/<int:course_id>", methods=["GET"])
def get_course(course_id):
    user = get_current_user()
    course = Course.query.get(course_id)
    if not course:
        return jsonify({"error": "Курс не найден"}), 404

    course_data = course_to_dict(course, user=user)
    lessons = Lesson.query.filter_by(course_id=course.id) \
        .order_by(Lesson.order_index.asc(), Lesson.id.asc()).all()

    course_data["lessons"] = [lesson_to_dict(l) for l in lessons]

    is_purchased = False
    if user:
        is_purchased = Purchase.query.filter_by(
            user_id=user.id, course_id=course.id
        ).first() is not None
    course_data["is_purchased"] = is_purchased

    return jsonify({"course": course_data})


@app.route("/api/my-courses", methods=["GET"])
def my_courses():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Не авторизован"}), 401

    course_ids = [p.course_id for p in user.purchases]
    courses = Course.query.filter(Course.id.in_(course_ids)).all()

    return jsonify({
        "courses": [course_to_dict(c, user=user) for c in courses]
    })


# ============================================================
# CART
# ============================================================

@app.route("/api/cart", methods=["GET"])
def get_cart():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Не авторизован"}), 401

    items = CartItem.query.filter_by(user_id=user.id).all()
    result = []
    total = 0

    for item in items:
        c = item.course
        price = c.price or c.price_full or 0
        result.append({
            "id": item.id,
            "course_id": c.id,
            "title": c.title,
            "image_url": c.image_url,
            "price": price,
        })
        total += price

    return jsonify({"items": result, "total": total})


@app.route("/api/cart/add", methods=["POST"])
def cart_add():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Не авторизован"}), 401

    data = request.get_json(force=True)
    course_id = data.get("course_id")
    course = Course.query.get(course_id)
    if not course:
        return jsonify({"error": "Курс не найден"}), 404

    if Purchase.query.filter_by(user_id=user.id, course_id=course.id).first():
        return jsonify({"error": "Курс уже куплен"}), 400

    if CartItem.query.filter_by(user_id=user.id, course_id=course.id).first():
        return jsonify({"error": "Курс уже в корзине"}), 400

    item = CartItem(user_id=user.id, course_id=course.id)
    db.session.add(item)
    db.session.commit()

    return jsonify({"message": "Добавлено в корзину"})


@app.route("/api/cart/remove", methods=["POST"])
def cart_remove():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Не авторизован"}), 401

    data = request.get_json(force=True)
    course_id = data.get("course_id")
    item = CartItem.query.filter_by(user_id=user.id, course_id=course_id).first()
    if not item:
        return jsonify({"error": "Курс не найден в корзине"}), 404

    db.session.delete(item)
    db.session.commit()

    return jsonify({"message": "Удалено"})


@app.route("/api/cart/checkout", methods=["POST"])
def cart_checkout():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Не авторизован"}), 401

    items = CartItem.query.filter_by(user_id=user.id).all()
    if not items:
        return jsonify({"error": "Корзина пуста"}), 400

    for item in items:
        c = item.course
        if Purchase.query.filter_by(user_id=user.id, course_id=c.id).first():
            continue

        price = c.price or c.price_full or 0
        p = Purchase(user_id=user.id, course_id=c.id, price_paid=price)
        db.session.add(p)
        db.session.delete(item)

    db.session.commit()
    return jsonify({"message": "Покупка успешна"})


# ============================================================
# UPLOADS (IMAGE / VIDEO)
# ============================================================

@app.route("/api/upload/image", methods=["POST"])
def upload_image():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Не авторизован"}), 401

    file = request.files.get("file")
    if not file:
        return jsonify({"error": "Файл не найден"}), 400

    img_type = request.form.get("type", "course")
    subdir = "course_images"
    if img_type == "avatar":
        subdir = "avatars"

    ext = os.path.splitext(file.filename)[1].lower()
    fname = f"{uuid.uuid4().hex}{ext}"
    rel_path = os.path.join(subdir, fname)
    abs_path = os.path.join(UPLOAD_ROOT, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    file.save(abs_path)

    url = f"/uploads/{rel_path}"
    return jsonify({"url": url})


@app.route("/api/upload/video", methods=["POST"])
def upload_video():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Не авторизован"}), 401

    file = request.files.get("file")
    if not file:
        return jsonify({"error": "Файл не найден"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    fname = f"{uuid.uuid4().hex}{ext}"
    rel_path = os.path.join("videos", fname)
    abs_path = os.path.join(UPLOAD_ROOT, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    file.save(abs_path)

    url = f"/uploads/{rel_path}"
    return jsonify({"url": url})


# ============================================================
# ADMIN HELPERS
# ============================================================

def require_admin():
    user = get_current_user()
    if not user:
        return None, jsonify({"error": "Не авторизован"}), 401
    # если нужен только один админ — можно тут проверить phone
    return user, None, None


# ============================================================
# ADMIN: COURSES
# ============================================================

@app.route("/api/admin/courses", methods=["POST"])
def admin_create_course():
    _, err, code = require_admin()
    if err:
        return err, code

    data = request.get_json(force=True)
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Название обязательно"}), 400

    price_full = data.get("price_full") or data.get("price") or 0
    price_discount = data.get("price_discount")
    if price_discount:
        price = int(price_discount)
    else:
        price = int(price_full)

    course = Course(
        title=title,
        description=data.get("description"),
        image_url=data.get("image_url"),
        price_full=int(price_full),
        price_discount=int(price_discount) if price_discount else None,
        price=price,
    )
    db.session.add(course)
    db.session.commit()

    return jsonify({"course": course_to_dict(course)})


@app.route("/api/admin/courses/<int:course_id>", methods=["PUT"])
def admin_update_course(course_id):
    _, err, code = require_admin()
    if err:
        return err, code

    course = Course.query.get(course_id)
    if not course:
        return jsonify({"error": "Курс не найден"}), 404

    data = request.get_json(force=True)
    if "title" in data:
        course.title = data.get("title") or course.title
    if "description" in data:
        course.description = data.get("description")
    if "image_url" in data and data["image_url"]:
        course.image_url = data["image_url"]

    if "price_full" in data or "price_discount" in data or "price" in data:
        price_full = data.get("price_full", course.price_full)
        price_discount = data.get("price_discount", course.price_discount)
        course.price_full = int(price_full)
        course.price_discount = int(price_discount) if price_discount else None
        if course.price_discount and course.price_discount > 0:
            course.price = course.price_discount
        else:
            course.price = course.price_full

    db.session.commit()
    return jsonify({"course": course_to_dict(course)})


@app.route("/api/admin/courses/<int:course_id>", methods=["DELETE"])
def admin_delete_course(course_id):
    _, err, code = require_admin()
    if err:
        return err, code

    course = Course.query.get(course_id)
    if not course:
        return jsonify({"error": "Курс не найден"}), 404

    Lesson.query.filter_by(course_id=course_id).delete()
    CartItem.query.filter_by(course_id=course_id).delete()
    Purchase.query.filter_by(course_id=course_id).delete()
    db.session.delete(course)
    db.session.commit()

    return jsonify({"message": "Курс удалён"})


@app.route("/api/admin/courses/<int:course_id>/stats", methods=["GET"])
def admin_course_stats(course_id):
    _, err, code = require_admin()
    if err:
        return err, code

    course = Course.query.get(course_id)
    if not course:
        return jsonify({"error": "Курс не найден"}), 404

    students_count = (
        db.session.query(db.func.count(db.distinct(Purchase.user_id)))
        .filter(Purchase.course_id == course.id)
        .scalar()
    ) or 0
    sales_count = (
        db.session.query(db.func.count(Purchase.id))
        .filter(Purchase.course_id == course.id)
        .scalar()
    ) or 0
    revenue = (
        db.session.query(db.func.coalesce(db.func.sum(Purchase.price_paid), 0))
        .filter(Purchase.course_id == course.id)
        .scalar()
    ) or 0

    return jsonify({
        "course_id": course.id,
        "students_count": int(students_count),
        "sales_count": int(sales_count),
        "revenue": int(revenue),
    })


# ============================================================
# ADMIN: LESSONS
# ============================================================

@app.route("/api/admin/lessons", methods=["POST"])
def admin_create_lesson():
    _, err, code = require_admin()
    if err:
        return err, code

    data = request.get_json(force=True)
    course_id = data.get("course_id")
    title = (data.get("title") or "").strip()
    video_url = (data.get("video_url") or "").strip()
    order_index = data.get("order_index") or 0

    if not course_id or not title or not video_url:
        return jsonify({"error": "course_id, title и video_url обязательны"}), 400

    if not Course.query.get(course_id):
        return jsonify({"error": "Курс не найден"}), 404

    lesson = Lesson(
        course_id=course_id,
        title=title,
        video_url=video_url,
        order_index=int(order_index),
    )
    db.session.add(lesson)
    db.session.commit()

    return jsonify({"lesson": lesson_to_dict(lesson)})


@app.route("/api/admin/lessons/reorder", methods=["POST"])
def admin_reorder_lessons():
    _, err, code = require_admin()
    if err:
        return err, code

    data = request.get_json(force=True)
    lesson_id = data.get("lesson_id")
    swap_with_id = data.get("swap_with_id")

    l1 = Lesson.query.get(lesson_id)
    l2 = Lesson.query.get(swap_with_id)
    if not l1 or not l2:
        return jsonify({"error": "Урок(и) не найден"}), 404

    l1.order_index, l2.order_index = l2.order_index, l1.order_index
    db.session.commit()

    return jsonify({"message": "Порядок изменён"})


@app.route("/api/admin/lessons/<int:lesson_id>", methods=["DELETE"])
def admin_delete_lesson(lesson_id):
    _, err, code = require_admin()
    if err:
        return err, code

    lesson = Lesson.query.get(lesson_id)
    if not lesson:
        return jsonify({"error": "Урок не найден"}), 404

    db.session.delete(lesson)
    db.session.commit()
    return jsonify({"message": "Урок удалён"})


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/api/ping")
def ping():
    return jsonify({"status": "ok"})


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
