import sqlite3
import os

DB_NAME = "database.db"


def init_db():
    # Создаём БД если её нет
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # ========== ТАБЛИЦА ПОЛЬЗОВАТЕЛЕЙ ==========
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        password TEXT,
        balance INTEGER DEFAULT 0
    );
    """)

    # ========== ТАБЛИЦА КУРСОВ ==========
    cur.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        price INTEGER NOT NULL,
        author TEXT,
        description TEXT,
        image TEXT        -- base64 изображение
    );
    """)

    # ========== ТАБЛИЦА УРОКОВ ==========
    cur.execute("""
    CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        youtube_url TEXT,
        position INTEGER DEFAULT 0,
        FOREIGN KEY(course_id) REFERENCES courses(id)
    );
    """)

    # ========== ТАБЛИЦА ОТЗЫВОВ ==========
    cur.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        text TEXT NOT NULL,
        rating INTEGER DEFAULT 5,
        FOREIGN KEY(course_id) REFERENCES courses(id),
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)

    # ========== ТАБЛИЦА КОРЗИНЫ ==========
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cart (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(course_id) REFERENCES courses(id)
    );
    """)

    conn.commit()
    conn.close()
    print("База данных инициализирована.")
