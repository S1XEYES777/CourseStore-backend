import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

os.makedirs(DATA_DIR, exist_ok=True)

# ============================
#  ПУТИ К JSON-ФАЙЛАМ
# ============================
FILES = {
    "users":      os.path.join(DATA_DIR, "users.json"),
    "courses":    os.path.join(DATA_DIR, "courses.json"),
    "lessons":    os.path.join(DATA_DIR, "lessons.json"),
    "reviews":    os.path.join(DATA_DIR, "reviews.json"),
    "cart":       os.path.join(DATA_DIR, "cart.json"),
    "purchases":  os.path.join(DATA_DIR, "purchases.json"),
}


# ============================
#  ЧТЕНИЕ JSON
# ============================
def read_json(name):
    path = FILES[name]
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


# ============================
#  ЗАПИСЬ JSON
# ============================
def write_json(name, data):
    path = FILES[name]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ============================
#  ГЕНЕРАТОР ID
# ============================
def next_id(records):
    if not records:
        return 1
    return max(item["id"] for item in records) + 1


# ============================
#  ИНИЦИАЛИЗАЦИЯ (создание файлов)
# ============================
def init_db():
    for name, path in FILES.items():
        if not os.path.exists(path):
            write_json(name, [])


if __name__ == "__main__":
    init_db()
    print("JSON database initialized ✔")
