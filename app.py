from flask import Flask
from flask_cors import CORS

from db import init_db        # ← ВАЖНО: используем только ЭТО init_db!
init_db()                     # ← и вызываем ТОЛЬКО ОДИН раз

# Импорт маршрутов
from routes.auth import auth_bp
from routes.users import users_bp
from routes.courses import courses_bp
from routes.lessons import lessons_bp
from routes.reviews import reviews_bp
from routes.cart import cart_bp
from routes.admin import admin_bp


app = Flask(
    __name__,
    static_folder="static",       # Папка со статикой
    static_url_path="/static"     # URL для статики
)

CORS(app)  # Разрешаем доступ фронтенду и Tkinter


# -------------------------------------
#        РЕГИСТРАЦИЯ МАРШРУТОВ
# -------------------------------------
app.register_blueprint(auth_bp)
app.register_blueprint(users_bp)
app.register_blueprint(courses_bp)
app.register_blueprint(lessons_bp)
app.register_blueprint(reviews_bp)
app.register_blueprint(cart_bp)
app.register_blueprint(admin_bp)


# -------------------------------------
#   ПРОВЕРКА РАБОТЫ СЕРВЕРА
# -------------------------------------
@app.get("/api/ping")
def ping():
    return {"status": "ok"}


# -------------------------------------
#   ЗАПУСК ПРИ ЛОКАЛЬНОМ СТАРТЕ
# -------------------------------------
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
