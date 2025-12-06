from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import psycopg2
import os

app = Flask(__name__)
CORS(app)

# Папка для загрузки файлов
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# =============== БАЗА ДАННЫХ ===============

conn = psycopg2.connect(
    host="dpg-d4d05l0gjchc73dmfld0-a.oregon-postgres.render.com",
    database="coursestore",
    user="coursestore_user",
    password="QpbQO0QAxRIwMRLVShTDgVSplVOMiZVQ"
)


# =============== ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ===============

def dict_user(row):
    return {
        "id": row[0],
        "name": row[1],
        "phone": row[2],
        "password": row[3],
        "balance": row[4],
        "avatar": row[5]
    }


# =============== РЕГИСТРАЦИЯ ===============

@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    name = data["name"]
    phone = data["phone"]
    password = data["password"]

    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE phone=%s", (phone,))
    if cur.fetchone():
        return jsonify({"status": "error", "message": "Номер телефона занят"})

    cur.execute("""
        INSERT INTO users (name, phone, password, balance)
        VALUES (%s, %s, %s, 0) RETURNING *
    """, (name, phone, password))
    row = cur.fetchone()
    conn.commit()

    user = dict_user(row)
    return jsonify({"status": "ok", "user": user})


# =============== ВХОД ===============

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    phone = data["phone"]
    password = data["password"]

    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE phone=%s AND password=%s", (phone, password))
    row = cur.fetchone()

    if not row:
        return jsonify({"status": "error", "message": "Неверный логин или пароль"})

    user = dict_user(row)
    return jsonify({"status": "ok", "user": user})


# =============== АВАТАРКА ===============

@app.route("/api/upload_avatar", methods=["POST"])
def upload_avatar():
    user_id = request.form.get("user_id")
    file = request.files.get("avatar")

    if not user_id or not file:
        return jsonify({"status": "error", "message": "Нет данных"})

    filename = f"avatar_{user_id}.png"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    cur = conn.cursor()
    cur.execute("UPDATE users SET avatar=%s WHERE id=%s", (filename, user_id))
    conn.commit()

    return jsonify({"status": "ok", "filename": filename})


# ОТДАТЬ ФАЙЛ
@app.route("/uploads/<path:path>")
def send_uploaded(path):
    return send_from_directory(UPLOAD_FOLDER, path)


# =============== ПОПОЛНЕНИЕ БАЛАНСА ===============

@app.route("/api/add_balance", methods=["POST"])
def add_balance():
    data = request.json
    uid = data["user_id"]
    amount = int(data["amount"])

    cur = conn.cursor()
    cur.execute("UPDATE users SET balance = balance + %s WHERE id=%s RETURNING balance", (amount, uid))
    new_balance = cur.fetchone()[0]
    conn.commit()

    return jsonify({"status": "ok", "new_balance": new_balance})


# =============== КУРСЫ ===============

@app.route("/api/courses")
def get_courses():
    cur = conn.cursor()
    cur.execute("SELECT * FROM courses")
    rows = cur.fetchall()

    result = []
    for r in rows:
        result.append({
            "id": r[0],
            "title": r[1],
            "price": r[2],
            "image": r[3]
        })

    return jsonify(result)


@app.route("/api/admin/add_course", methods=["POST"])
def admin_add_course():
    title = request.form.get("title")
    price = request.form.get("price")
    image = request.files.get("image")

    if not title or not price or not image:
        return jsonify({"status": "error", "message": "Заполните все поля"})

    filename = f"course_{title.replace(' ', '_')}.png"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    image.save(filepath)

    cur = conn.cursor()
    cur.execute("INSERT INTO courses (title, price, image) VALUES (%s, %s, %s)",
                (title, price, filename))
    conn.commit()

    return jsonify({"status": "ok"})


@app.route("/api/admin/delete_course/<int:cid>", methods=["DELETE"])
def admin_delete_course(cid):
    cur = conn.cursor()
    cur.execute("DELETE FROM courses WHERE id=%s", (cid,))
    conn.commit()
    return jsonify({"status": "ok"})


# =============== КОРЗИНА ===============

@app.route("/api/cart/add", methods=["POST"])
def cart_add():
    data = request.json
    uid = data["user_id"]
    cid = data["course_id"]

    cur = conn.cursor()
    cur.execute("INSERT INTO cart (user_id, course_id) VALUES (%s, %s)", (uid, cid))
    conn.commit()

    return jsonify({"status": "ok"})


@app.route("/api/cart/<int:uid>")
def get_cart(uid):
    cur = conn.cursor()
    cur.execute("""
        SELECT courses.id, courses.title, courses.price
        FROM cart
        JOIN courses ON cart.course_id = courses.id
        WHERE cart.user_id=%s
    """, (uid,))

    rows = cur.fetchall()
    result = []
    for r in rows:
        result.append({"id": r[0], "title": r[1], "price": r[2]})

    return jsonify(result)


@app.route("/api/cart/remove", methods=["POST"])
def cart_remove():
    data = request.json
    uid = data["user_id"]
    cid = data["course_id"]

    cur = conn.cursor()
    cur.execute("DELETE FROM cart WHERE user_id=%s AND course_id=%s", (uid, cid))
    conn.commit()

    return jsonify({"status": "ok"})


# =============== ПОКУПКА ===============

@app.route("/api/cart/checkout/<int:uid>", methods=["POST"])
def checkout(uid):
    cur = conn.cursor()

    # забрать курсы
    cur.execute("""
        SELECT course_id FROM cart WHERE user_id=%s
    """, (uid,))
    cart_items = cur.fetchall()

    # сохранить покупки
    for item in cart_items:
        cur.execute("INSERT INTO purchased (user_id, course_id) VALUES (%s, %s)",
                    (uid, item[0]))

    # очистить корзину
    cur.execute("DELETE FROM cart WHERE user_id=%s", (uid,))
    conn.commit()

    return jsonify({"status": "ok"})


# =============== МОИ КУРСЫ ===============

@app.route("/api/purchases/<int:uid>")
def get_purchases(uid):
    cur = conn.cursor()
    cur.execute("""
        SELECT courses.id, courses.title, courses.price
        FROM purchased
        JOIN courses ON purchased.course_id = courses.id
        WHERE purchased.user_id=%s
    """, (uid,))

    rows = cur.fetchall()
    result = []
    for r in rows:
        result.append({"id": r[0], "title": r[1], "price": r[2]})

    return jsonify(result)

@app.route("/api/upload_avatar", methods=["POST"])
def upload_avatar():
    user_id = request.form.get("user_id")
    file = request.files.get("avatar")

    if not user_id or not file:
        return jsonify({"status": "error", "message": "Нет файла"})

    filename = f"avatar_{user_id}.png"
    filepath = os.path.join("uploads", filename)
    file.save(filepath)

    cur = conn.cursor()
    cur.execute("UPDATE users SET avatar=%s WHERE id=%s", (filename, user_id))
    conn.commit()

    return jsonify({"status": "ok", "filename": filename})

# =============== ЗАПУСК ===============

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
