from flask import Flask
from flask_cors import CORS

# =====================================
# 1) Правильный импорт и создание БД
# =====================================
from init_db import init_db
init_db()   # <-- создаёт таблицы если их нет

# Импорт маршрутов
from routes.auth import auth_bp
from routes.users import users_bp
from routes.courses import courses_bp
from routes.lessons import lessons_bp
from routes.reviews import reviews_bp
from routes.cart import cart_bp
from routes.admin import admin_bp


# =====================================
# 2) Flask App
# =====================================
app = Flask(
    __name__,
    static_folder="static",
    static_url_path="/static"
)

CORS(app)


# =====================================
# 3) Регистрация Blueprint
# =====================================
app.register_blueprint(auth_bp)
app.register_blueprint(users_bp)
app.register_blueprint(courses_bp)
app.register_blueprint(lessons_bp)
app.register_blueprint(reviews_bp)
app.register_blueprint(cart_bp)
app.register_blueprint(admin_bp)


# =====================================
# 4) Для проверки что сервер работает
# =====================================
@app.get("/api/ping")
def ping():
    return {"status": "ok"}


# =====================================
# 5) Запуск (Render использует это)
# =====================================
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
