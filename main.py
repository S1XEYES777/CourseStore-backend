from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import base64

app = Flask(__name__)
CORS(app)

# ======================
# Database helper
# ======================

def db():
    return sqlite3.connect("database.db")

def init_db():
    conn = db()
    cur = conn.cursor()

    # Courses
    cur.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            description TEXT,
            author TEXT,
            price TEXT,
            image TEXT
        )
    """)

    # Lessons
    cur.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER,
            title TEXT,
            link TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ======================
# Courses API
# ======================

@app.route("/api/courses", methods=["GET"])
def get_courses():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM courses")
    rows = cur.fetchall()
    conn.close()

    courses = []
    for r in rows:
        courses.append({
            "id": r[0],
            "title": r[1],
            "description": r[2],
            "author": r[3],
            "price": r[4],
            "image": r[5]
        })

    return jsonify({"status": "ok", "courses": courses})


@app.route("/api/courses/add", methods=["POST"])
def add_course():
    data = request.json
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO courses (title, description, author, price, image)
        VALUES (?, ?, ?, ?, ?)
    """, (data["title"], data["description"], data["author"], data["price"], data["image"]))

    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


@app.route("/api/courses/delete", methods=["POST"])
def delete_course():
    data = request.json
    conn = db()
    cur = conn.cursor()

    cur.execute("DELETE FROM courses WHERE id = ?", (data["id"],))
    cur.execute("DELETE FROM lessons WHERE course_id = ?", (data["id"],))

    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


# ======================
# Lessons API
# ======================

@app.route("/api/lessons/<int:course_id>", methods=["GET"])
def get_lessons(course_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM lessons WHERE course_id = ?", (course_id,))
    rows = cur.fetchall()
    conn.close()

    lessons = []
    for r in rows:
        lessons.append({
            "id": r[0],
            "course_id": r[1],
            "title": r[2],
            "link": r[3]
        })

    return jsonify({"status": "ok", "lessons": lessons})


@app.route("/api/lessons/add", methods=["POST"])
def add_lesson():
    data = request.json
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO lessons (course_id, title, link)
        VALUES (?, ?, ?)
    """, (data["course_id"], data["title"], data["link"]))

    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


@app.route("/api/lessons/delete", methods=["POST"])
def delete_lesson():
    data = request.json
    conn = db()
    cur = conn.cursor()

    cur.execute("DELETE FROM lessons WHERE id = ?", (data["id"],))

    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


# ======================
# Start
# ======================
@app.route("/")
def home():
    return "CourseStore Backend running!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
