# web_app.py
import os
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory
from dotenv import load_dotenv
import requests
import time

# 1. Создаём приложение
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super-secret-key")

# 2. Загружаем переменные окружения
load_dotenv()

# 3. Роут для статики
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

# --- База знаний ---
KNOWLEDGE_BASE = {
    "меню": (
        "🏠 **Главное меню**\n\n"
        "Выберите интересующую тему:\n"
        "• `vr`\n"
        "• `батуты`\n"
        "• `нерф`\n"
        "• `день рождения`\n"
        "• `выпускные`\n"
        "• `выездные мероприятия`\n"
        "• `забронировать`\n"
        "• `акции`\n"
        "• `цены`"
    ),
    "vr": (
        "🎮 **VR-зоны**\n\n"
        "Игры в шлемах HTC Vive и Oculus.\n"
        "Можно играть вдвоём!\n"
        "Цены: 300 ₽ за 30 мин, 500 ₽ за час, 900 ₽ за 2 часа.\n"
        "Подробнее: [VR-зоны](/vr_zones)"
    ),
    "батуты": (
        "🏀 **Батутный центр**\n\n"
        "Площадка для игр и трюков на батутах.\n\n"
        "**Цены:**\n"
        "- 500 ₽ за час\n"
        "- 4000 ₽ за 10 посещений\n"
        "Подробнее: [Батутный центр](/batuts_center)"
    ),
    "нерф": (
        "🔫 **Нерф-арена**\n\n"
        "Тактические баталии с мягкими дротиками.\n"
        "Команды до 6 человек.\n"
        "Цены: 2500 ₽ (до 6 чел), 3500 ₽ (до 8 чел).\n"
        "Подробнее: [Нерф-арена](/nerf_arena)"
    ),
    "день рождения": (
        "🎉 **День рождения в FunLand**\n\n"
        "Мы организуем яркие и незабываемые дни рождения для детей и взрослых!\n\n"
        "**Что входит:**\n"
        "- Аниматор или ведущий\n"
        "- Праздничное оформление\n"
        "- Игры и активности (батуты, нерф, VR)\n"
        "- Чаепитие с тортом\n"
        "- Фото на память\n\n"
        "**Пакеты:**\n"
        "- Стандарт: 8000 ₽ (до 10 человек)\n"
        "- Экстрим: 12 000 ₽ (до 12 человек)\n"
        "- VR-приключение: 15 000 ₽ (до 8 человек)\n\n"
        "Хотите забронировать? Напишите: *«хочу забронировать день рождения»*"
    ),
    "выпускные": (
        "🎓 **Выпускные в FunLand**\n\n"
        "Проведите выпускной незабываемо — с активными играми, VR и весёлой атмосферой!\n\n"
        "**Что предлагаем:**\n"
        "- Тематическое оформление\n"
        "- Командные игры (нерф, батуты)\n"
        "- VR-квесты\n"
        "- Фотозона и видеосъёмка\n"
        "- Кофейная пауза с десертами\n\n"
        "**Цены:**\n"
        "- От 1500 ₽ с человека (минимум 15 человек)\n"
        "- Скидка 10% при бронировании на 20+ человек\n\n"
        "Идеально подходит для выпускных 9-х и 11-х классов!"
    ),
    "выездные мероприятия": (
        "🚐 **Выездные мероприятия**\n\n"
        "Мы приезжаем к вам! Проводим активные игры, нерф-батлы и VR-станции на вашей площадке.\n\n"
        "**Где можно:**\n"
        "- Школы и детские сады\n"
        "- Парки и скверы\n"
        "- Дома отдыха и лагеря\n"
        "- Корпоративные мероприятия\n\n"
        "**Что везём:**\n"
        "- Переносные батуты\n"
        "- Нерф-арена (до 8 человек)\n"
        "- VR-шлемы (до 4 станций)\n"
        "- Ведущий и оборудование\n\n"
        "**Цены:**\n"
        "- От 10 000 ₽ за 3 часа\n"
        "- Доплата 1000 ₽ за каждые 10 км от центра города\n\n"
        "Отлично подходит для детских праздников и корпоративов!"
    ),
    "забронировать": (
        "📅 **Форма бронирования**\n\n"
        "Перейдите в [форму бронирования](/booking)\n"
        "Укажите имя, телефон, дату, количество гостей и тип события.\n"
        "Мы свяжемся с вами для подтверждения."
    ),
    "акции": (
        "🎁 **Акции**\n\n"
        "• Детям до 7 лет — **50% скидка**\n"
        "• Семейный пакет — **+ VR бесплатно**\n"
        "• Студенческий день — **-20% по пятницам**"
    ),
    "цены": "💰 Все цены: [Смотреть здесь](/prices)",
    "привет": "👋 Привет! Рад вас видеть в FunLand! 😊",
    "пока": "👋 До скорого! Приходите снова!",
    "помощь": "💬 Напишите, что вас интересует — я помогу!",
    "как связаться с оператором": (
        "📞 **Как связаться с оператором:**\n\n"
        "Телефон: +7 (XXX) XXX-XX-XX\n"
        "Email: info@funland.ru\n"
        "WhatsApp: +7 (XXX) XXX-XX-XX"
    ),
}

# --- Системный промпт ---
SYSTEM_PROMPT = (
    "Ты — дружелюбный консультант развлекательного центра FunLand. "
    "Отвечай кратко, информативно, с эмодзи. "
    "Если вопрос о наших услугах — отвечай точно. "
    "Если о игре (Superhot, Aimcat) — расскажи как геймер. "
    "Не выдумывай цены. Если не уверен — предложи связаться с оператором."
)

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

    messages = [{"role": "system", "text": SYSTEM_PROMPT}]
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

    for key in KNOWLEDGE_BASE:
        if key in question:
            answer = KNOWLEDGE_BASE[key]
            conversation_history[user_id].append({"role": "user", "text": question})
            conversation_history[user_id].append({"role": "assistant", "text": answer})
            log_interaction(question, answer, "knowledge_base")
            return jsonify({"answer": answer})

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

@app.route("/birthday")
def birthday():
    return render_template("birthday.html")

@app.route("/birthday_calc")
def birthday_calc():
    return render_template("birthday_calc.html")

@app.route("/events")
def events():
    return render_template("events.html")

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

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("index"))

# --- Запуск ---
load_bookings()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)