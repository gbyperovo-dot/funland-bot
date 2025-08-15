# web_app.py
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, send_from_directory
import os
import json
import time
import threading
from datetime import datetime
from dotenv import load_dotenv
import requests

# --- Загрузка переменных окружения ---
load_dotenv()

# --- Создание приложения ---
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super-secret-key")

# --- Глобальные переменные ---
KNOWLEDGE_BASE = {}
BOOKINGS = []
conversation_history = {}
LOG_FILE = "bot_log.json"

# --- Пути ---
KNOWLEDGE_FILE = "knowledge_base.json"
BOOKINGS_FILE = "bookings.json"
BACKUPS_DIR = "backups"

# --- Вспомогательные функции ---

def load_knowledge_base():
    """Загружает базу знаний из JSON"""
    global KNOWLEDGE_BASE
    if os.path.exists(KNOWLEDGE_FILE):
        try:
            with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
                KNOWLEDGE_BASE = json.load(f)
            print(f"✅ Загружено {len(KNOWLEDGE_BASE)} вопросов из {KNOWLEDGE_FILE}")
        except Exception as e:
            print(f"❌ Ошибка загрузки базы знаний: {e}")
    else:
        print("⚠️ Файл knowledge_base.json не найден.")

def save_knowledge_base():
    """Сохраняет базу знаний + резервная копия"""
    try:
        if not os.path.exists(BACKUPS_DIR):
            os.makedirs(BACKUPS_DIR)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUPS_DIR, f"knowledge_base_{timestamp}.json")
        shutil.copy2(KNOWLEDGE_FILE, backup_path)
        with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
            json.dump(KNOWLEDGE_BASE, f, ensure_ascii=False, indent=4)
        print("✅ База знаний сохранена")
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")

def load_bookings():
    """Загружает бронирования"""
    global BOOKINGS
    if os.path.exists(BOOKINGS_FILE):
        try:
            with open(BOOKINGS_FILE, "r", encoding="utf-8") as f:
                BOOKINGS = json.load(f)
            print(f"✅ Загружено {len(BOOKINGS)} бронирований")
        except Exception as e:
            print(f"❌ Ошибка загрузки бронирований: {e}")
    else:
        BOOKINGS = []

def save_booking(data):
    """Сохраняет новое бронирование"""
    BOOKINGS.append(data)
    with open(BOOKINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(BOOKINGS, f, ensure_ascii=False, indent=4)

def log_interaction(question, answer, source):
    """Логирует диалог"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "answer": answer,
        "source": source
    }
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
        else:
            logs = []
        logs.append(log_entry)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"❌ Ошибка логирования: {e}")

def call_yandex_gpt(prompt, history=None):
    """Вызов Yandex GPT с повторными попытками"""
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Authorization": f"Api-Key {os.getenv('YANDEX_API_KEY')}",
        "x-folder-id": os.getenv("YANDEX_FOLDER_ID"),
        "Content-Type": "application/json"
    }
    messages = [{"role": "system", "text": "Ты — дружелюбный консультант. Отвечай кратко, структурированно, с эмодзи."}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "text": prompt})

    payload = {
        "modelUri": f"gpt://{os.getenv('YANDEX_FOLDER_ID')}/yandexgpt-lite",
        "completionOptions": {
            "stream": False,
            "temperature": 0.3,
            "maxTokens": 1000
        },
        "messages": messages
    }

    for attempt in range(3):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                return response.json()["result"]["alternatives"][0]["message"]["text"]
            elif response.status_code == 401:
                return "❌ Ошибка авторизации. Проверьте API-ключ."
            elif response.status_code == 400:
                return "❌ Ошибка параметров. Проверьте folder_id."
            else:
                print(f"⚠️ Ошибка GPT (попытка {attempt + 1}): {response.status_code}")
                time.sleep(1)
        except Exception as e:
            print(f"⚠️ Ошибка подключения (попытка {attempt + 1}): {str(e)}")
            time.sleep(1)
    return "❌ Не удалось получить ответ. Попробуйте позже."

# --- Загрузка данных ---
load_knowledge_base()
load_bookings()

# --- Маршруты ---

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    question = data.get("question", "").strip().lower()
    user_id = data.get("user_id", "default")

    if user_id not in conversation_history:
        conversation_history[user_id] = []

    # Поиск в базе знаний
    for key in KNOWLEDGE_BASE:
        if key in question:
            answer = KNOWLEDGE_BASE[key]
            conversation_history[user_id].append({"role": "user", "text": question})
            conversation_history[user_id].append({"role": "assistant", "text": answer})
            log_interaction(question, answer, "knowledge_base")
            return jsonify({"answer": answer})

    # Запрос к Yandex GPT
    gpt_answer = call_yandex_gpt(question, conversation_history[user_id])
    conversation_history[user_id].append({"role": "user", "text": question})
    conversation_history[user_id].append({"role": "assistant", "text": gpt_answer})
    log_interaction(question, gpt_answer, "yandex_gpt")
    return jsonify({"answer": gpt_answer})

@app.route("/booking", methods=["GET", "POST"])
def booking():
    if request.method == "POST":
        name = request.form.get("name")
        phone = request.form.get("phone")
        date = request.form.get("date")
        guests = request.form.get("guests")
        event_type = request.form.get("event_type")
        if not all([name, phone, date, guests, event_type]):
            return render_template("booking.html", error="Заполните все поля!")
        new_booking = {
            "name": name,
            "phone": phone,
            "date": date,
            "guests": guests,
            "event_type": event_type,
            "created_at": datetime.now().strftime("%d.%m.%Y %H:%M")
        }
        BOOKINGS.append(new_booking)
        with open(BOOKINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(BOOKINGS, f, ensure_ascii=False, indent=4)
        return render_template("booking.html", success="Спасибо! Мы свяжемся с вами.")
    return render_template("booking.html")

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("username") == os.getenv("ADMIN_USER", "admin") and \
           request.form.get("password") == os.getenv("ADMIN_PASS", "1"):
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        flash("❌ Неверный логин или пароль", "error")
    return render_template("admin/login.html")

@app.route("/admin")
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    return render_template("admin/dashboard.html", bookings=BOOKINGS)

@app.route("/admin/knowledge", methods=["GET", "POST"])
def knowledge_edit():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        action = request.form.get("action")
        question = request.form.get("question", "").strip().lower()
        answer = request.form.get("answer", "").strip()

        if action == "add" and question and answer and question not in KNOWLEDGE_BASE:
            KNOWLEDGE_BASE[question] = answer
            save_knowledge_base()
            flash("✅ Вопрос добавлен", "success")

        elif action == "edit" and question in KNOWLEDGE_BASE and answer:
            KNOWLEDGE_BASE[question] = answer
            save_knowledge_base()
            flash("✅ Ответ обновлён", "success")

        elif action == "delete" and question in KNOWLEDGE_BASE:
            del KNOWLEDGE_BASE[question]
            save_knowledge_base()
            flash("✅ Вопрос удалён", "success")

    return render_template("admin/knowledge_edit.html", knowledge=KNOWLEDGE_BASE)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    flash("Вы вышли из админки", "info")
    return redirect(url_for("index"))

@app.route("/static/<path:path>")
def send_static(path):
    return send_from_directory("static", path)

@app.route("/birthday_calc")
def birthday_calc():
    return render_template("birthday_calc.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)