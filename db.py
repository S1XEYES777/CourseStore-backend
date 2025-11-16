import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "course_store.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # -----------------------------
    #   Таблица пользователей
    # -----------------------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        balance INTEGER NOT NULL DEFAULT 0
    );
    """)

    # -----------------------------
    #   Таблица курсов
    # -----------------------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        price INTEGER NOT NULL,
        author TEXT NOT NULL,
        description TEXT NOT NULL,
        image_path TEXT
    );
    """)

    # -----------------------------
    #   Таблица уроков
    # -----------------------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        youtube_url TEXT NOT NULL,
        position INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY(course_id) REFERENCES courses(id)
    );
    """)

    # -----------------------------
    #   Таблица корзины
    # -----------------------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cart_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(course_id) REFERENCES courses(id)
    );
    """)

    # -----------------------------
    #   Таблица покупок
    # -----------------------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(course_id) REFERENCES courses(id)
    );
    """)

    # -----------------------------
    #   Таблица отзывов
    # -----------------------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        rating INTEGER NOT NULL,
        text TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(course_id) REFERENCES courses(id)
    );
    """)

    # -----------------------------
    #   Создать папку для изображений
    # -----------------------------
    images_folder = os.path.join(os.path.dirname(__file__), "static", "images")
    os.makedirs(images_folder, exist_ok=True)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized.")
