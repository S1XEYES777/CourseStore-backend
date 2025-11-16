from flask import Flask
from flask_cors import CORS
import os

# Импорт маршрутов
from routes.auth import auth_bp
from routes.users import users_bp
from routes.courses import courses_bp
from routes.lessons import lessons_bp
from routes.reviews import reviews_bp
from routes.cart import cart_bp
from routes.admin import admin_bp

from db import init_db


app = Flask(
    __name__,
    static_folder="static",             # Папка со статикой
    static_url_path="/static"           # URL для статических файлов
)

CORS(app)  # Чтобы frontend и Admin.py могли работать с backend


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



@app.get("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)




