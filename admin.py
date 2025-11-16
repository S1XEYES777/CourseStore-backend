import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import requests
import base64
from io import BytesIO
from PIL import Image, ImageTk

# =========================================
#  URL BACKEND
# =========================================
API = "https://coursestore-backend.onrender.com"

# =========================================
#  API HELPERS
# =========================================
def api_get_courses():
    try:
        r = requests.get(f"{API}/api/courses")
        return r.json()
    except:
        return {"status": "error", "courses": []}

def api_add_course(title, desc, price, author, image_b64):
    data = {
        "title": title,
        "description": desc,
        "price": price,
        "author": author,
        "image": image_b64
    }
    r = requests.post(f"{API}/api/admin/course/add", json=data)
    return r.json()

def api_update_course(course_id, title, desc, price, author, image_b64=None):
    data = {
        "id": course_id,
        "title": title,
        "description": desc,
        "price": price,
        "author": author
    }
    if image_b64:
        data["image"] = image_b64

    r = requests.post(f"{API}/api/admin/course/update", json=data)
    return r.json()

def api_delete_course(course_id):
    r = requests.post(f"{API}/api/admin/course/delete", json={"id": course_id})
    return r.json()

def api_get_lessons(course_id):
    r = requests.get(f"{API}/api/lessons", params={"course_id": course_id})
    return r.json()

def api_add_lesson(course_id, title, link):
    r = requests.post(f"{API}/api/admin/lesson/add", json={
        "course_id": course_id,
        "title": title,
        "youtube_url": link
    })
    return r.json()

def api_delete_lesson(lesson_id):
    r = requests.post(f"{API}/api/admin/lesson/delete", json={"id": lesson_id})
    return r.json()

def api_get_users():
    r = requests.get(f"{API}/api/admin/users")
    return r.json()

def api_update_user(uid, name, phone, password, balance):
    r = requests.post(f"{API}/api/admin/users/update", json={
        "id": uid,
        "name": name,
        "phone": phone,
        "password": password,
        "balance": balance
    })
    return r.json()

def api_delete_user(uid):
    r = requests.post(f"{API}/api/admin/users/delete", json={"id": uid})
    return r.json()

# =========================================
#  GUI BASE
# =========================================
root = tk.Tk()
root.title("Course Store — Admin Panel")
root.state("zoomed")
root.configure(bg="#F3F4F6")

FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_SUB = ("Segoe UI", 12)
FONT_BTN = ("Segoe UI", 11, "bold")

sidebar = tk.Frame(root, bg="#111827", width=220)
sidebar.pack(side="left", fill="y")

main = tk.Frame(root, bg="#F3F4F6")
main.pack(side="right", fill="both", expand=True)

content = tk.Frame(main, bg="#F3F4F6")
content.pack(fill="both", expand=True)

views = {}

def show_view(name):
    for v in views.values():
        v.pack_forget()
    views[name].pack(fill="both", expand=True)
    for b in sidebar_buttons:
        sidebar_buttons[b].config(bg="#111827")
    sidebar_buttons[name].config(bg="#1F2937")

sidebar_buttons = {}

def add_sidebar_button(name, text, row):
    btn = tk.Button(
        sidebar,
        text=text,
        font=FONT_BTN,
        bg="#111827",
        fg="white",
        anchor="w",
        relief="flat",
        padx=20,
        pady=8,
        command=lambda: show_view(name)
    )
    btn.grid(row=row, column=0, sticky="ew")
    sidebar_buttons[name] = btn

# =========================================
#  CREATE CARD UI
# =========================================
def create_card(parent):
    shadow = tk.Frame(parent, bg="#D1D5DB")
    shadow.pack(fill="both", expand=True, padx=20, pady=20)
    card = tk.Frame(shadow, bg="white")
    card.place(relx=0, rely=0, relwidth=1, relheight=1, x=0, y=-2)
    return card

# =========================================
#  COURSES VIEW
# =========================================
courses_view = tk.Frame(content, bg="#F3F4F6")
views["courses"] = courses_view
card = create_card(courses_view)

tabs = ttk.Notebook(card)
tabs.pack(fill="both", expand=True)

tab_add = tk.Frame(tabs, bg="white")
tab_edit = tk.Frame(tabs, bg="white")

tabs.add(tab_add, text="Создать курс")
tabs.add(tab_edit, text="Курсы / редактирование")

# -------------------------
#  CREATE COURSE TAB
# -------------------------
tk.Label(tab_add, text="Создание нового курса", font=FONT_TITLE, bg="white").pack(anchor="w", padx=20, pady=20)

form = tk.Frame(tab_add, bg="white")
form.pack(fill="x", padx=20)

tk.Label(form, text="Название", font=FONT_SUB, bg="white").grid(row=0, column=0, sticky="w")
title_entry = tk.Entry(form, font=FONT_SUB, width=40)
title_entry.grid(row=1, column=0, sticky="w", pady=4)

tk.Label(form, text="Автор", font=FONT_SUB, bg="white").grid(row=2, column=0, sticky="w", pady=(12,0))
author_entry = tk.Entry(form, font=FONT_SUB, width=40)
author_entry.grid(row=3, column=0, sticky="w", pady=4)

tk.Label(form, text="Цена", font=FONT_SUB, bg="white").grid(row=4, column=0, sticky="w", pady=(12,0))
price_entry = tk.Entry(form, font=FONT_SUB, width=20)
price_entry.grid(row=5, column=0, sticky="w", pady=4)

tk.Label(form, text="Описание", font=FONT_SUB, bg="white").grid(row=6, column=0, sticky="w", pady=(12,0))
desc_box = tk.Text(form, font=FONT_SUB, height=5, width=60)
desc_box.grid(row=7, column=0, sticky="w")

# ------- image
image_b64_new = None

def choose_image():
    global image_b64_new
    path = filedialog.askopenfilename(filetypes=[("Images", "*.png;*.jpg;*.jpeg")])
    if not path:
        return
    with open(path, "rb") as f:
        data = f.read()
    image_b64_new = base64.b64encode(data).decode()

img_btn = tk.Button(form, text="Выбрать изображение", font=FONT_BTN, bg="#2563EB", fg="white",
                    command=choose_image)
img_btn.grid(row=8, column=0, pady=12)

# ------- lessons add
tk.Label(form, text="Уроки", font=FONT_SUB, bg="white").grid(row=9, column=0, sticky="w")

lesson_title = tk.Entry(form, font=FONT_SUB, width=40)
lesson_title.grid(row=10, column=0, sticky="w")
lesson_title.insert(0, "Название урока")

lesson_link = tk.Entry(form, font=FONT_SUB, width=40)
lesson_link.grid(row=11, column=0, sticky="w", pady=4)
lesson_link.insert(0, "YouTube URL")

lessons_pending = []
less_list = tk.Listbox(form, font=FONT_SUB, width=60, height=5)
less_list.grid(row=12, column=0, pady=4)

def add_pending():
    t = lesson_title.get().strip()
    l = lesson_link.get().strip()
    if not t or not l:
        return
    lessons_pending.append({"title": t, "link": l})
    less_list.insert("end", f"{t} — {l}")
    lesson_title.delete(0, "end")
    lesson_link.delete(0, "end")

tk.Button(form, text="Добавить урок", bg="#10B981", fg="white",
          font=FONT_BTN, command=add_pending).grid(row=13, column=0, sticky="w", pady=4)

# ------- CREATE COURSE BTN
def create_course():
    if not image_b64_new:
        messagebox.showerror("Ошибка", "Выберите изображение")
        return

    title = title_entry.get().strip()
    author = author_entry.get().strip()
    price = price_entry.get().strip()
    desc = desc_box.get("1.0", "end").strip()

    if not title or not author or not price or not desc:
        messagebox.showerror("Ошибка", "Заполните все поля")
        return

    res = api_add_course(title, desc, price, author, image_b64_new)
    if res["status"] != "ok":
        messagebox.showerror("Ошибка", res.get("message", "Не удалось создать"))
        return

    course_id = res["course_id"]

    for l in lessons_pending:
        api_add_lesson(course_id, l["title"], l["link"])

    messagebox.showinfo("Готово", "Курс создан!")
    load_courses()

tk.Button(tab_add, text="Создать курс", bg="#2563EB", fg="white",
          font=FONT_BTN, command=create_course).pack(anchor="e", padx=20, pady=20)

# -------------------------
#  EDIT COURSES TAB
# -------------------------
tree = ttk.Treeview(tab_edit, columns=("id", "title", "author", "price"), show="headings")
tree.heading("id", text="ID")
tree.heading("title", text="Название")
tree.heading("author", text="Автор")
tree.heading("price", text="Цена")
tree.pack(fill="both", expand=True, padx=20, pady=20)

COURSES = []

def load_courses():
    global COURSES
    tree.delete(*tree.get_children())
    res = api_get_courses()
    COURSES = res.get("courses", [])
    for c in COURSES:
        tree.insert("", "end", values=(c["id"], c["title"], c["author"], c["price"]))

load_courses()

# =========================================
#  USERS VIEW
# =========================================
users_view = tk.Frame(content, bg="#F3F4F6")
views["users"] = users_view
card_u = create_card(users_view)

tk.Label(card_u, text="Пользователи системы", font=FONT_TITLE, bg="white").pack(anchor="w", padx=20, pady=20)

users_tree = ttk.Treeview(card_u, columns=("id", "name", "phone", "balance"), show="headings")
for col, txt in [("id","ID"), ("name","Имя"), ("phone","Телефон"), ("balance","Баланс")]:
    users_tree.heading(col, text=txt)

users_tree.pack(fill="both", expand=True, padx=20)

def load_users():
    users_tree.delete(*users_tree.get_children())
    res = api_get_users()
    for u in res.get("users", []):
        users_tree.insert("", "end", values=(u["id"], u["name"], u["phone"], u["balance"]))

load_users()

# =========================================
#  SIDEBAR BUTTONS
# =========================================
add_sidebar_button("courses", "📚 Курсы", 0)
add_sidebar_button("users", "👤 Пользователи", 1)

show_view("courses")

root.mainloop()
