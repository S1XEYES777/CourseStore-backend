from flask import Flask
from flask_cors import CORS

# ============================
#  ИНИЦИАЛИЗАЦИЯ БАЗЫ
# ============================
from db import init_db
init_db()

# ============================
#  Импорт blueprint'ов
# ============================
from routes.auth import auth_bp
from routes.users import users_bp
from routes.courses import courses_bp
from routes.lessons import lessons_bp
from routes.reviews import reviews_bp
from routes.cart import cart_bp
# admin_bp — НЕ нужен, так как у тебя отдельное Tkinter приложение

# ============================
#  Создаём Flask-приложение
# ============================
app = Flask(
    __name__,
    static_folder="static",
    static_url_path="/static"
)

# Разрешаем запросы со всех доменов (фронтенд → бэкенд)
CORS(app, supports_credentials=True)

# ============================
#  Регистрируем маршруты
# ============================
app.register_blueprint(auth_bp)
app.register_blueprint(users_bp)
app.register_blueprint(courses_bp)
app.register_blueprint(lessons_bp)
app.register_blueprint(reviews_bp)
app.register_blueprint(cart_bp)

# ============================
#  Проверка сервера
# ============================
@app.get("/api/ping")
def ping():
    return {"status": "ok"}

# ============================
#  Запуск локально
# ============================
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
