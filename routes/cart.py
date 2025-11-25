from flask import Blueprint, request, jsonify
from db import get_connection
import psycopg2.extras

cart_bp = Blueprint("cart", __name__, url_prefix="/api/cart")


# ============================================================
# 📌 Добавить курс в корзину
# ============================================================
@cart_bp.post("/add")
def cart_add():
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    course_id = data.get("course_id")

    if not user_id or not course_id:
        return jsonify({"status": "error", "message": "Нет user_id или course_id"}), 400

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Уже куплен?
    cur.execute("""
        SELECT id FROM cart WHERE user_id=%s AND course_id=%s
    """, (user_id, course_id))
    if cur.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "Курс уже в корзине"}), 400

    # Добавляем
    cur.execute("""
        INSERT INTO cart (user_id, course_id)
        VALUES (%s, %s)
    """, (user_id, course_id))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ============================================================
# 📌 Получить корзину пользователя
# ============================================================
@cart_bp.get("")
def cart_get():
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"status": "error", "message": "Нет user_id"}), 400

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            c.id AS cart_id,
            courses.id AS course_id,
            courses.title,
            courses.price,
            courses.description,
            courses.author,
            courses.image
        FROM cart c
        JOIN courses ON c.course_id = courses.id
        WHERE c.user_id = %s
    """, (user_id,))

    rows = cur.fetchall()
    conn.close()

    items = []
    total = 0

    for r in rows:
        total += r["price"]
        items.append({
            "cart_id": r["cart_id"],
            "course_id": r["course_id"],
            "title": r["title"],
            "price": r["price"],
            "author": r["author"],
            "description": r["description"],
            "image": r["image"]
        })

    return jsonify({
        "status": "ok",
        "items": items,
        "total": total
    })


# ============================================================
# 📌 Удалить один товар из корзины
# ============================================================
@cart_bp.post("/remove")
def cart_remove():
    data = request.get_json(force=True)
    cart_id = data.get("cart_id")

    if not cart_id:
        return jsonify({"status": "error", "message": "Нет cart_id"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM cart WHERE id=%s", (cart_id,))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ============================================================
# 📌 Купить всё из корзины
# ============================================================
@cart_bp.post("/buy")
def cart_buy():
    data = request.get_json(force=True)
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"status": "error", "message": "Нет user_id"}), 400

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Получаем корзину
    cur.execute("""
        SELECT c.course_id, courses.price
        FROM cart c
        JOIN courses ON c.course_id = courses.id
        WHERE c.user_id = %s
    """, (user_id,))
    rows = cur.fetchall()

    if not rows:
        conn.close()
        return jsonify({"status": "error", "message": "Корзина пуста"}), 400

    total = sum(r["price"] for r in rows)

    # Проверяем баланс
    cur.execute("SELECT balance FROM users WHERE id=%s", (user_id,))
    user = cur.fetchone()

    if not user:
        conn.close()
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    if user["balance"] < total:
        conn.close()
        return jsonify({"status": "error", "message": "Недостаточно средств"}), 400

    # Списываем деньги
    new_balance = user["balance"] - total
    cur.execute("UPDATE users SET balance=%s WHERE id=%s", (new_balance, user_id))

    # Добавляем покупки
    for r in rows:
        cur.execute("""
            INSERT INTO reviews (course_id, user_id, text, stars)
            VALUES (%s, %s, '', 0)
        """, (r["course_id"], user_id))

    # Очищаем корзину
    cur.execute("DELETE FROM cart WHERE user_id=%s", (user_id,))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "new_balance": new_balance})
