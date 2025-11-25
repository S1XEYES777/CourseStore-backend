import os
from flask import Flask, jsonify
from flask_cors import CORS

# ==== ИМПОРТ БЛЮПРИНТОВ ====
from routes.auth import auth_bp
from routes.cart import cart_bp
from routes.courses import courses_bp
from routes.lessons import lessons_bp
from routes.reviews import reviews_bp
from routes.users import users_bp

# ==========================
#  НАСТРОЙКА ПРИЛОЖЕНИЯ
# ==========================
app = Flask(__name__)
CORS(app, supports_credentials=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)


# ==========================
#  ГЛОБАЛЬНЫЙ ХЭНДЛЕР ОШИБОК
# ==========================
@app.errorhandler(Exception)
def handle_any_error(e):
    print("SERVER ERROR:", repr(e))
    return jsonify({"status": "error", "message": str(e)}), 500


# ==========================
#  PING / STATUS
# ==========================
@app.get("/api/ping")
def ping():
    return {"status": "ok", "message": "backend running (json mode)"}


@app.get("/")
def index():
    return {"status": "running", "service": "CourseStore JSON Backend"}


# ==========================
#  РЕГИСТРАЦИЯ БЛЮПРИНТОВ
# ==========================
app.register_blueprint(auth_bp)
app.register_blueprint(cart_bp)
app.register_blueprint(courses_bp)
app.register_blueprint(lessons_bp)
app.register_blueprint(reviews_bp)
app.register_blueprint(users_bp)


# ==========================
#  ЛОКАЛЬНЫЙ ЗАПУСК
# ==========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
