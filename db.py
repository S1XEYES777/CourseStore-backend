import psycopg2
import psycopg2.extras
import os

DATABASE_URL = "postgresql://coursestore_user:QpbQO0QAxRIwMRLVShTDgVSplVOMiZVQ@dpg-d4d05l0gjchc73dmfld0-a.oregon-postgres.render.com/coursestore"

def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        phone TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        balance INTEGER DEFAULT 0
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        price INTEGER NOT NULL,
        author TEXT NOT NULL,
        description TEXT NOT NULL,
        image_path TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS lessons (
        id SERIAL PRIMARY KEY,
        course_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        youtube_url TEXT NOT NULL,
        position INTEGER DEFAULT 1,
        FOREIGN KEY(course_id) REFERENCES courses(id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        rating INTEGER NOT NULL,
        text TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)

    conn.commit()
    conn.close()
