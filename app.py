from flask import Flask
from flask_cors import CORS

# ============================
#  Создаём Flask-приложение
# ============================
app = Flask(
    __name__,
    static_folder="static",
    static_url_path="/static"
)

# Разрешаем доступ фронтенду
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)


# ============================
#  Инициализация базы (ТОЛЬКО ЛОКАЛЬНО)
# ============================
if __name__ == "__main__":
    from db import init_db
    init_db()   # вызывать только локально


# ============================
#  Импорт blueprint'ов
# ============================
from routes.auth import auth_bp
from routes.users import users_bp
from routes.courses import courses_bp
from routes.lessons import lessons_bp
from routes.reviews import reviews_bp
from routes.cart import cart_bp

# ⚠️ УДАЛЕНО — admin_bp (у тебя нет файла routes/admin.py)
# from routes.admin import admin_bp


# ============================
#  Регистрация маршрутов
# ============================
app.regist
