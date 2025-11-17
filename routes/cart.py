from flask import Blueprint, request, jsonify, url_for, current_app
from db import get_connection
import psycopg2.extras
import os, base64

cart_bp = Blueprint("cart", __name__)


# ============================================================
# 📌 Добавить курс в корзину
# ============================================================
@cart_bp.post("/api/cart/add")
def cart_add():
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    course_id = data.get("course_id")

    if not user_id or not course_id:
        return jsonify({"status": "error", "message": "Нет user_id или course_id"}), 400

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Уже куплен?
    cur.execute(
        "SELECT id FROM purchases WHERE user_id=%s AND course_id=%s",
        (user_id, course_id),
    )
    if cur.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "Курс уже куплен"}), 400

    # Уже в корзине?
    cur.execute(
        "SELECT id FROM cart_items WHERE user_id=%s AND course_id=%s",
        (user_id, course_id),
    )
    if cur.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "Курс уже в корзине"}), 400

    # Добавляем
    cur.execute(
        "INSERT INTO cart_items (user_id, course_id) VALUES (%s, %s)",
        (user_id, course_id),
    )

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ============================================================
# 📌 Получить корзину пользователя
# ============================================================
@cart_bp.get("/api/cart")
def cart_get():
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"status": "error", "message": "Нет user_id"}), 400

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            ci.id AS cart_id,
            c.id AS course_id,
            c.title,
            c.price,
            c.description,
            c.author,
            c.image_path
        FROM cart_items ci
        JOIN courses c ON ci.course_id = c.id
        WHERE ci.user_id = %s
    """, (user_id,))

    rows = cur.fetchall()
    conn.close()

    items = []
    total = 0

    for r in rows:
        total += r["price"]

        # image_url
        if r["image_path"]:
            image_url = url_for(
                "static",
                filename=f"images/{r['image_path']}",
                _external=True,
            )
        else:
            image_url = None

        items.append({
            "cart_id": r["cart_id"],
            "course_id": r["course_id"],
            "title": r["title"],
            "price": r["price"],
            "author": r["author"],
            "description": r["description"],
            "image_url": image_url
        })

    return jsonify({
        "status": "ok",
        "items": items,
        "total": total
    })


# ============================================================
# 📌 Удалить один товар из корзины
# ============================================================
@cart_bp.post("/api/cart/remove")
def cart_remove():
    data = request.get_json(force=True)
    cart_id = data.get("cart_id")

    if not cart_id:
        return jsonify({"status": "error", "message": "Нет cart_id"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM cart_items WHERE id=%s", (cart_id,))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


# ============================================================
# 📌 Купить всё из корзины
# ============================================================
@cart_bp.post("/api/cart/buy")
def cart_buy():
    data = request.get_json(force=True)
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"status": "error", "message": "Нет user_id"}), 400

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Берем корзину
    cur.execute("""
        SELECT ci.course_id, c.price
        FROM cart_items ci
        JOIN courses c ON ci.course_id = c.id
        WHERE ci.user_id = %s
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

    # Списываем
    new_balance = user["balance"] - total
    cur.execute("UPDATE users SET balance=%s WHERE id=%s", (new_balance, user_id))

    # Записываем покупки
    for r in rows:
        cur.execute(
            "INSERT INTO purchases (user_id, course_id) VALUES (%s, %s)",
            (user_id, r["course_id"]),
        )

    # Чистим корзину
    cur.execute("DELETE FROM cart_items WHERE user_id=%s", (user_id,))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "balance": new_balance})
