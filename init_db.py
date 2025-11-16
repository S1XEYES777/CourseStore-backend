import sqlite3

def init_db():
    con = sqlite3.connect("database.db")
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        price INTEGER,
        author TEXT,
        description TEXT,
        image_path TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER,
        title TEXT,
        youtube_url TEXT,
        position INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        password TEXT,
        balance INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER,
        user_id INTEGER,
        text TEXT,
        rating INTEGER
    )
    """)

    con.commit()
    con.close()

if __name__ == "__main__":
    init_db()
    print("DB OK — tables created")
