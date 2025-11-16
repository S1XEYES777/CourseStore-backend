from flask import Blueprint, request, jsonify
from db import get_connection

cart_bp = Blueprint("cart", __name__)


@cart_bp.post("/api/cart/add")
def cart_add():
    data = request.get_json(force=True)
    user_id = data.get("user_id")
    course_id = data.get("course_id")

    if not user_id or not course_id:
        return jsonify({"status": "error", "message": "Нет user_id или course_id"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id FROM purchases WHERE user_id=? AND course_id=?", (user_id, course_id))
    if cur.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "Курс уже куплен"}), 400

    cur.execute("SELECT id FROM cart_items WHERE user_id=? AND course_id=?", (user_id, course_id))
    if cur.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "Курс уже в корзине"}), 400

    cur.execute("INSERT INTO cart_items (user_id, course_id) VALUES (?, ?)", (user_id, course_id))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@cart_bp.get("/api/cart")
def cart_get():
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"status": "error", "message": "Нет user_id"}), 400

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT ci.id as cart_id, c.id as course_id, c.title, c.price, c.author, c.image_path
        FROM cart_items ci
        JOIN courses c ON ci.course_id = c.id
        WHERE ci.user_id = ?
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
            "image_url": f"/static/images/{r['image_path']}" if r["image_path"] else None
        })

    return jsonify({"status": "ok", "items": items, "total": total})


@cart_bp.post("/api/cart/remove")
def cart_remove():
    data = request.get_json(force=True)
    cart_id = data.get("cart_id")

    if not cart_id:
        return jsonify({"status": "error", "message": "Нет cart_id"}), 400

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM cart_items WHERE id=?", (cart_id,))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@cart_bp.post("/api/cart/buy")
def cart_buy():
    data = request.get_json(force=True)
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"status": "error", "message": "Нет user_id"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT ci.course_id, c.price
        FROM cart_items ci
        JOIN courses c ON ci.course_id = c.id
        WHERE ci.user_id = ?
    """, (user_id,))
    rows = cur.fetchall()

    if not rows:
        conn.close()
        return jsonify({"status": "error", "message": "Корзина пуста"}), 400

    total = sum(r["price"] for r in rows)

    cur.execute("SELECT balance FROM users WHERE id=?", (user_id,))
    user = cur.fetchone()

    if not user:
        conn.close()
        return jsonify({"status": "error", "message": "Пользователь не найден"}), 404

    if user["balance"] < total:
        conn.close()
        return jsonify({"status": "error", "message": "Недостаточно средств"}), 400

    new_balance = user["balance"] - total
    cur.execute("UPDATE users SET balance=? WHERE id=?", (new_balance, user_id))

    for r in rows:
        cur.execute("INSERT INTO purchases (user_id, course_id) VALUES (?, ?)", (user_id, r["course_id"]))

    cur.execute("DELETE FROM cart_items WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "balance": new_balance})
