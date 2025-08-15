# web_app.py
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import os
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory
from dotenv import load_dotenv
import requests
import time
import threading

# --- Загружаем переменные окружения ---
load_dotenv()

# --- Создаём приложение ---
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super-secret-key")

# --- Роут для статики ---
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

# --- Конфигурация ---
BOOKINGS_FILE = "bookings.json"
LOG_FILE = "bot_log.json"
bookings = []

# --- Yandex GPT ---
YANDEX_GPT_API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
YANDEX_GPT_MODEL = "yandexgpt-lite"
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY", "AQVN1yUDXvnO8SFPcpT5yD4oWrQAol4Gx5GtQqYW")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID", "b1gl7ugev7botoao0fa6")

# --- Админка ---
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "1")

# --- История диалога ---
conversation_history = {}

# --- База знаний (из файла) ---
KNOWLEDGE_BASE = {}

def load_knowledge_base():
    """Загружает базу знаний из JSON-файла"""
    global KNOWLEDGE_BASE
    try:
        with open("knowledge_base.json", "r", encoding="utf-8") as f:
            KNOWLEDGE_BASE = json.load(f)
        print(f"✅ Загружено {len(KNOWLEDGE_BASE)} вопросов из knowledge_base.json")
    except FileNotFoundError:
        print("⚠️ Файл knowledge_base.json не найден. Создайте его.")
    except Exception as e:
        print(f"❌ Ошибка загрузки базы знаний: {e}")

# --- Автозагрузка базы знаний ---
def watch_kb_file():
    """Следит за изменениями в knowledge_base.json"""
    last_mod = 0
    while True:
        try:
            current_mod = os.path.getmtime("knowledge_base.json")
            if current_mod != last_mod:
                load_knowledge_base()
                print("🔄 База знаний обновлена!")
                last_mod = current_mod
        except Exception as e:
            pass
        time.sleep(2)

# Запускаем фоновый поток
threading.Thread(target=watch_kb_file, daemon=True).start()

# --- Загрузка бронирований ---
def load_bookings():
    global bookings
    try:
        with open(BOOKINGS_FILE, "r", encoding="utf-8") as f:
            bookings = json.load(f)
        print(f"✅ Загружено {len(bookings)} бронирований")
    except FileNotFoundError:
        print("📁 Файл bookings.json не найден. Будет создан при первой записи.")
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")

def save_bookings():
    with open(BOOKINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(bookings, f, ensure_ascii=False, indent=4)
    print(f"💾 Сохранено {len(bookings)} бронирований")

# --- Логирование ---
def log_interaction(question, answer, source):
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "answer": answer,
        "source": source
    }
    try:
        logs = []
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    logs = json.loads(content)
        logs.append(log_entry)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        print(f"📝 Лог записан: {source.upper()} → '{question[:30]}...'")
    except Exception as e:
        print(f"⚠️ Ошибка записи лога: {e}")

# --- Вызов Yandex GPT с retry ---
def call_yandex_gpt(prompt, history=None):
    headers = {
        "Authorization": f"Api-Key {YANDEX_API_KEY}",
        "Content-Type": "application/json"
    }

    messages = [{"role": "system", "text": (
        "Ты — дружелюбный консультант развлекательного центра FunLand. "
        "Отвечай кратко, информативно, с эмодзи. "
        "Если вопрос о наших услугах — отвечай точно. "
        "Если о игре (Superhot, Aimcat) — расскажи как геймер. "
        "Не выдумывай цены. Если не уверен — предложи связаться с оператором."
    )}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "text": prompt})

    payload = {
        "modelUri": f"gpt://{YANDEX_FOLDER_ID}/{YANDEX_GPT_MODEL}",
        "completionOptions": {"maxTokens": 1000, "temperature": 0.7},
        "messages": messages
    }

    for attempt in range(3):
        try:
            response = requests.post(YANDEX_GPT_API_URL, headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                result = response.json()
                return result["result"]["alternatives"][0]["message"]["text"]
            elif response.status_code == 401:
                return f"❌ Ошибка авторизации: {response.json().get('error', {}).get('message', 'Неизвестная ошибка')}"
            elif response.status_code == 400:
                return f"❌ Ошибка параметров: {response.json().get('error', {}).get('message', 'Неизвестная ошибка')}"
            else:
                print(f"⚠️ Ошибка GPT (попытка {attempt + 1}): {response.status_code}")
                time.sleep(1)
        except Exception as e:
            print(f"⚠️ Ошибка подключения (попытка {attempt + 1}): {str(e)}")
            time.sleep(1)

    return "❌ Не удалось получить ответ от Yandex GPT. Попробуйте позже."

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

    # Отправляем в Yandex GPT
    response = call_yandex_gpt(question, conversation_history[user_id])
    conversation_history[user_id].append({"role": "user", "text": question})
    conversation_history[user_id].append({"role": "assistant", "text": response})
    log_interaction(question, response, "yandex_gpt")
    return jsonify({"answer": response})

# --- Страницы ---
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
        bookings.append(new_booking)
        save_bookings()
        return render_template("booking.html", success="Спасибо! Мы свяжемся с вами.")
    return render_template("booking.html")

@app.route("/bookings")
def bookings_list():
    return render_template("bookings_list.html", bookings=bookings)

# --- Админка ---
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("username") == ADMIN_USER and request.form.get("password") == ADMIN_PASS:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        return render_template("admin/login.html", error="Неверный логин или пароль")
    return render_template("admin/login.html")

@app.route("/admin")
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    return render_template("admin/dashboard.html", bookings=bookings)

@app.route("/admin/knowledge")
def knowledge_edit():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    return render_template("admin/knowledge_edit.html", knowledge=KNOWLEDGE_BASE)

@app.route("/admin/knowledge/save", methods=["POST"])
def save_knowledge():
    if not session.get("admin_logged_in"):
        return jsonify({"status": "error", "message": "Доступ запрещён"})
    
    data = {k: v.strip() for k, v in request.form.items() if v.strip()}
    
    try:
        with open("knowledge_base.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        load_knowledge_base()  # Обновляем в памяти
        return jsonify({"status": "success", "message": "База знаний сохранена!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("index"))

# --- Запуск ---
load_knowledge_base()
load_bookings()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
    
    
# --- Редактирование базы знаний (встроено в админку) ---

@app.route("/admin/knowledge", methods=["GET", "POST"])
def knowledge_edit():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    global KNOWLEDGE_BASE

    if request.method == "POST":
        action = request.form.get("action")

        if action == "add":
            question = request.form.get("question", "").strip().lower()
            answer = request.form.get("answer", "").strip()
            if question and answer and question not in KNOWLEDGE_BASE:
                KNOWLEDGE_BASE[question] = answer
                save_knowledge_base()
                flash("✅ Вопрос добавлен", "success")
            else:
                flash("❌ Вопрос уже существует или пустой", "error")

        elif action == "edit":
            question = request.form.get("question", "").strip().lower()
            answer = request.form.get("answer", "").strip()
            if question in KNOWLEDGE_BASE and answer:
                KNOWLEDGE_BASE[question] = answer
                save_knowledge_base()
                flash("✅ Ответ обновлён", "success")
            else:
                flash("❌ Неверный вопрос или пустой ответ", "error")

        elif action == "delete":
            question = request.form.get("question", "").strip().lower()
            if question in KNOWLEDGE_BASE:
                del KNOWLEDGE_BASE[question]
                save_knowledge_base()
                flash("✅ Вопрос удалён", "success")
            else:
                flash("❌ Вопрос не найден", "error")

    return render_template("admin/knowledge_edit.html", knowledge=KNOWLEDGE_BASE)