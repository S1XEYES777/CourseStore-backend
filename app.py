from flask import Flask
from flask_cors import CORS

# ============================
#  ИНИЦИАЛИЗАЦИЯ БАЗЫ
# ============================
from db import init_db
init_db()

# ============================
#  ИМПОРТ ROUTES (Blueprints)
# ============================
from routes.auth import auth_bp
from routes.users import users_bp
from routes.courses import courses_bp
from routes.lessons import lessons_bp
from routes.reviews import reviews_bp
from routes.cart import cart_bp
# admin_bp — НЕ нужен (Tkinter — отдельное приложение)

# ============================
#  СОЗДАЁМ FLASK ПРИЛОЖЕНИЕ
# ============================
app = Flask(
    __name__,
    static_folder="static",
    static_url_path="/static"
)

# Разрешаем фронту общаться с backend
CORS(app, supports_credentials=True)

# ============================
#  РЕГИСТРАЦИЯ ВСЕХ ROUTES
# ============================
app.register_blueprint(auth_bp)
app.register_blueprint(users_bp)
app.register_blueprint(courses_bp)
app.register_blueprint(lessons_bp)
app.register_blueprint(reviews_bp)
app.register_blueprint(cart_bp)

# ============================
#  ПРОВЕРКА СЕРВЕРА (для GUI + Render)
# ============================
@app.get("/api/ping")
def ping():
    return {"status": "ok", "message": "backend running"}

# ============================
#  ГЛАВНАЯ
# ============================
@app.get("/")
def index():
    return {"status": "running", "service": "CourseStore Backend"}

# ============================
#  ЗАПУСК (Render + локально)
# ============================
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    # Debug выключен, потому что Render не любит Debug
    app.run(host="0.0.0.0", port=port)
