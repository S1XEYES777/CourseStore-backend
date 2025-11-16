import os
import psycopg2
import psycopg2.extras

# URL твоей базы Postgres (можно оставить так, можно взять из переменной среды)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://coursestore_user:QpbQO0QAxRIwMRLVShTDgVSplVOMiZVQ@dpg-d4d05l0gjchc73dmfld0-a.oregon-postgres.render.com/coursestore?sslmode=require"
)


def get_connection():
    """
    Открываем подключение к PostgreSQL.
    row_factory = dict → row["id"] и т.п. будут работать, как в SQLite.
    """
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # ========= USERS ==========
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        phone TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        balance INTEGER NOT NULL DEFAULT 0
    );
    """)

    # ========= COURSES ==========
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

    # ========= LESSONS ==========
    cur.execute("""
    CREATE TABLE IF NOT EXISTS lessons (
        id SERIAL PRIMARY KEY,
        course_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        youtube_url TEXT NOT NULL,
        position INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    """)

    # ========= CART ==========
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cart_items (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    """)

    # ========= PURCHASES ==========
    cur.execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    """)

    # ========= REVIEWS ==========
    cur.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        rating INTEGER NOT NULL,
        text TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized.")
