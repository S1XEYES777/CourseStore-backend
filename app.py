import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import psycopg2
from urllib.parse import urlparse
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ============================================================
# DB CONNECT
# ============================================================
DATABASE_URL = os.environ.get("DATABASE_URL")

url = urlparse(DATABASE_URL)
conn = psycopg2.connect(
    database=url.path[1:],
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port
)


def query(sql, params=(), fetch=True):
    cur = conn.cursor()

    try:
        cur.execute(sql, params)
        conn.commit()

        if fetch:
            return cur.fetchall()
        return None

    except Exception as e:
        conn.rollback()
        print("DB ERROR:", e)
        return []

# ============================================================
# STATIC FILES (IMAGES/VIDEOS)
# ============================================================

@app.route("/uploads/<path:filename>")
def uploaded_files(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ============================================================
# REGISTER
# ============================================================
@app.post("/api/register")
def register():
    data = request.json
    name = data.get("name")
    phone = data.get("phone")
    password = data.get("password")

    exists = query("SELECT id FROM users WHERE phone=%s", (phone,))
    if exists:
        return jsonify({"status": "error", "message": "Такой номер уже зарегистрирован"})

    q = query("""
        INSERT INTO users(name, phone, password, balance)
        VALUES (%s, %s, %s, %s)
        RETURNING id, name, phone, balance, avatar
    """, (name, phone, password, 0))

    if q:
        uid, nm, ph, bal, av = q[0]
        return jsonify({
            "status": "ok",
            "user": {
                "id": uid, "name": nm,
                "phone": ph, "balance": bal,
                "avatar": av
            }
        })

    return jsonify({"status": "error"})

# ============================================================
# LOGIN
# ============================================================
@app.post("/api/login")
def login():
    data = request.json
    phone = data.get("phone")
    password = data.get("password")

    q = query("""
        SELECT id, name, phone, balance, avatar
        FROM users WHERE phone=%s AND password=%s
    """, (phone, password))

    if q:
        uid, nm, ph, bal, av = q[0]
        return jsonify({
            "status": "ok",
            "user": {
                "id": uid,
                "name": nm,
                "phone": ph,
                "balance": bal,
                "avatar": av
            }
        })

    return jsonify({"status": "error", "message": "Неверный логин или пароль"})

# ============================================================
# UPLOAD AVATAR
# ============================================================
@app.post("/api/upload_avatar/<int:user_id>")
def upload_avatar(user_id):
    if "avatar" not in request.files:
        return jsonify({"status": "error", "message": "Нет файла"})

    file = request.files["avatar"]
    fname = secure_filename(file.filename)
    path = os.path.join(UPLOAD_FOLDER, fname)
    file.save(path)

    query("UPDATE users SET avatar=%s WHERE id=%s", (fname, user_id), fetch=False)

    q = query("SELECT id,name,phone,balance,avatar FROM users WHERE id=%s", (user_id,))
    uid, nm, ph, bal, av = q[0]

    return jsonify({
        "status": "ok",
        "user": {
            "id": uid, "name": nm,
            "phone": ph, "balance": bal,
            "avatar": av
        }
    })

# ============================================================
# ADD COURSE (ADMIN)
# ============================================================
@app.post("/api/add_course")
def add_course():
    title = request.form.get("title")
    price = request.form.get("price")
    author = request.form.get("author")
    description = request.form.get("description")
    image = request.files.get("image")

    if not image:
        return jsonify({"status": "error", "message": "Нет изображения"})

    fname = secure_filename(image.filename)
    file_path = os.path.join(UPLOAD_FOLDER, fname)
    image.save(file_path)

    query("""
        INSERT INTO courses(title, price, author, description, image)
        VALUES (%s, %s, %s, %s, %s)
    """, (title, price, author, description, fname), fetch=False)

    return jsonify({"status": "ok"})

# ============================================================
# DELETE COURSE
# ============================================================
@app.delete("/api/delete_course/<int:cid>")
def delete_course(cid):
    query("DELETE FROM courses WHERE id=%s", (cid,), fetch=False)
    query("DELETE FROM lessons WHERE course_id=%s", (cid,), fetch=False)
    query("DELETE FROM purchases WHERE course_id=%s", (cid,), fetch=False)
    return jsonify({"status": "ok"})

# ============================================================
# GET COURSES
# ============================================================
@app.get("/api/courses")
def courses():
    rows = query("SELECT id, title, price, author, description, image FROM courses")
    result = []
    for r in rows:
        result.append({
            "id": r[0],
            "title": r[1],
            "price": r[2],
            "author": r[3],
            "description": r[4],
            "image": r[5]
        })
    return jsonify(result)

# ============================================================
# ADD LESSON (VIDEO)
# ============================================================
@app.post("/api/upload_lesson")
def upload_lesson():
    course_id = request.form.get("course_id")
    title = request.form.get("title")
    video = request.files.get("file")

    if not video:
        return jsonify({"status": "error"})

    fname = secure_filename(video.filename)
    path = os.path.join(UPLOAD_FOLDER, fname)
    video.save(path)

    query("""
        INSERT INTO lessons(course_id, title, url)
        VALUES (%s, %s, %s)
    """, (course_id, title, "/" + UPLOAD_FOLDER + "/" + fname), fetch=False)

    return jsonify({"status": "ok"})

# ============================================================
# GET LESSONS (Only if purchased)
# ============================================================
@app.get("/api/get_lessons")
def get_lessons():
    cid = request.args.get("course_id")
    uid = request.args.get("user_id")

    # check if user bought course
    bought = query("SELECT id FROM purchases WHERE user_id=%s AND course_id=%s", (uid, cid))
    if not bought:
        return jsonify({"status": "error", "message": "Нет доступа"})

    rows = query("SELECT title, url FROM lessons WHERE course_id=%s", (cid,))
    return jsonify({
        "status": "ok",
        "lessons": [{"title": r[0], "url": r[1]} for r in rows]
    })

# ============================================================
# PURCHASES
# ============================================================
@app.get("/api/purchases/<int:user_id>")
def my_purchases(user_id):
    rows = query("""
        SELECT c.id, c.title, c.price, c.image
        FROM purchases p
        JOIN courses c ON p.course_id=c.id
        WHERE p.user_id=%s
    """, (user_id,))

    result = []
    for r in rows:
        result.append({
            "id": r[0],
            "title": r[1],
            "price": r[2],
            "image": r[3]
        })

    return jsonify(result)

# ============================================================
# CART — ADD
# ============================================================
@app.post("/api/cart/add")
def cart_add():
    data = request.json
    user = data["user_id"]
    course = data["course_id"]

    # check duplicate
    exists = query("SELECT id FROM cart WHERE user_id=%s AND course_id=%s", (user, course))
    if exists:
        return jsonify({"status": "error", "message": "Уже в корзине"})

    query("INSERT INTO cart(user_id, course_id) VALUES (%s, %s)", (user, course), fetch=False)
    return jsonify({"status": "ok"})

# ============================================================
# CART — REMOVE
# ============================================================
@app.post("/api/cart/remove")
def cart_remove():
    data = request.json
    user = data["user_id"]
    course = data["course_id"]

    query("DELETE FROM cart WHERE user_id=%s AND course_id=%s", (user, course), fetch=False)
    return jsonify({"status": "ok"})

# ============================================================
# GET CART
# ============================================================
@app.get("/api/cart/<int:uid>")
def cart(uid):
    rows = query("""
        SELECT c.id, c.title, c.price, c.image
        FROM cart t
        JOIN courses c ON t.course_id=c.id
        WHERE t.user_id=%s
    """, (uid,))

    return jsonify([
        {"id": r[0], "title": r[1], "price": r[2], "image": r[3]}
        for r in rows
    ])

# ============================================================
# CHECKOUT (BUY COURSES)
# ============================================================
@app.post("/api/cart/checkout/<int:user_id>")
def checkout(user_id):

    # get cart
    cart = query("""
        SELECT c.id, c.price FROM cart t
        JOIN courses c ON t.course_id=c.id
        WHERE t.user_id=%s
    """, (user_id,))

    if not cart:
        return jsonify({"status": "error", "message": "Корзина пуста"})

    # get user balance
    balance = query("SELECT balance FROM users WHERE id=%s", (user_id,))
    balance = balance[0][0]

    total = sum([c[1] for c in cart])

    if balance < total:
        return jsonify({"status": "error", "message": "Недостаточно средств"})

    # write purchases
    for course_id, price in cart:
        # ignore duplicates
        exists = query("SELECT id FROM purchases WHERE user_id=%s AND course_id=%s", (user_id, course_id))
        if not exists:
            query("INSERT INTO purchases(user_id, course_id) VALUES (%s,%s)", (user_id, course_id), fetch=False)

    # remove from cart
    query("DELETE FROM cart WHERE user_id=%s", (user_id,), fetch=False)

    # reduce balance
    newbal = balance - total
    query("UPDATE users SET balance=%s WHERE id=%s", (newbal, user_id), fetch=False)

    # return updated user
    u = query("SELECT id,name,phone,balance,avatar FROM users WHERE id=%s", (user_id,))
    uid, nm, ph, bal, av = u[0]

    return jsonify({
        "status": "ok",
        "user": {
            "id": uid, "name": nm,
            "phone": ph, "balance": bal,
            "avatar": av
        }
    })

# ============================================================
# TOP UP BALANCE
# ============================================================
@app.post("/api/topup")
def topup():
    data = request.json
    user_id = data["user_id"]
    amount = int(data["amount"])

    query("UPDATE users SET balance = balance + %s WHERE id=%s", (amount, user_id), fetch=False)

    u = query("SELECT id,name,phone,balance,avatar FROM users WHERE id=%s", (user_id,))
    uid, nm, ph, bal, av = u[0]

    return jsonify({
        "status": "ok",
        "user": {
            "id": uid, "name": nm, "phone": ph,
            "balance": bal, "avatar": av
        }
    })

# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
