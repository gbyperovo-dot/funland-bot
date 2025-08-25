# web_app.py
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, send_from_directory, abort, make_response
import os
import json
import time
import shutil
from datetime import datetime
from dotenv import load_dotenv
import requests
import socket
import logging
import re
import functools

# - Настройка логирования -
logging.basicConfig(filename='audit.log',
                    level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# - Загрузка переменных окружения -
load_dotenv()

# - Создание приложения -
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super-secret-key-for-d-space-bot")

# - ОТКЛЮЧЕНИЕ КЭШИРОВАНИАЯ -
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# - Глобальные переменные -
KNOWLEDGE_BASE = {}
BOOKINGS = []
conversation_history = {}
LOG_FILE = "bot_log.json"
BACKUPS_DIR = "backups"
os.makedirs(BACKUPS_DIR, exist_ok=True)

# - Пути -
KNOWLEDGE_FILE = "knowledge_base.json"
BOOKINGS_FILE = "bookings.json"
SUGGESTIONS_FILE = "suggestions.json"
MENU_FILE = "menu.json"
MENU_CATEGORIES_FILE = "menu_categories.json"

# - Константы системных категорий меню -
SYSTEM_CATEGORIES = ['attractions', 'events', 'services', 'info']

# - Глобальная переменная -
suggestionMap = {}
MENU_CACHE = None

# - Декоратор для отключения кэширования -
def no_cache(view):
    @functools.wraps(view)
    def no_cache_view(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    return no_cache_view

# - Вспомогательные функции -
def load_knowledge_base():
    """Загружает базу знаний из JSON"""
    global KNOWLEDGE_BASE
    if os.path.exists(KNOWLEDGE_FILE):
        try:
            with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
                KNOWLEDGE_BASE = json.load(f)
            print("✅ База знаний загружена")
        except Exception as e:
            print(f"❌ Ошибка загрузки базы знаний: {e}")
    else:
        KNOWLEDGE_BASE = {
            "привет": "👋 Привет! Рад вас видеть в D-Space! 😊\nГотов помочь с выбором развлечений",
            "пока": "👋 До свидания! Приходите еще!",
            "спасибо": "Пожалуйста! Рад был помочь! 😊"
        }
        save_knowledge_base()
        print("✅ Создана база знаний по умолчанию")

def save_knowledge_base():
    """Сохраняет базу знаний в JSON"""
    try:
        with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
            json.dump(KNOWLEDGE_BASE, f, ensure_ascii=False, indent=4)
        print("✅ База знаний сохранены")
    except Exception as e:
        print(f"❌ Ошибка сохранения базы знаний: {e}")

def load_bookings():
    """Загружает бронирования из JSON"""
    global BOOKINGS
    if os.path.exists(BOOKINGS_FILE):
        try:
            with open(BOOKINGS_FILE, "r", encoding="utf-8") as f:
                BOOKINGS = json.load(f)
            print("✅ Бронирования загружены")
        except Exception as e:
            print(f"❌ Ошибка загрузки бронирований: {e}")
    else:
        BOOKINGS = []
        print("✅ Создан файл бронирований по умолчанию")

def save_bookings():
    """Сохраняет бронирования в JSON"""
    try:
        with open(BOOKINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(BOOKINGS, f, ensure_ascii=False, indent=4)
        print("✅ Бронирования сохранены")
    except Exception as e:
        print(f"❌ Ошибка сохранения бронирований: {e}")

def load_suggestion_map():
    """Загружает контекстные подсказки из JSON"""
    global suggestionMap
    
    # Пытаемся загрузить из файла
    if os.path.exists(SUGGESTIONS_FILE):
        try:
            with open(SUGGESTIONS_FILE, "r", encoding="utf-8") as f:
                suggestionMap = json.load(f)
            print("✅ Подсказки загружены из файла")
            return  # Выходим после успешной загрузки
        except Exception as e:
            print(f"❌ Ошибка загрузки подсказок: {e}")
            suggestionMap = {}
    
    # Создаем дефолтные подсказки ТОЛЬКО если файла нет или ошибка загрузки
    suggestionMap = {
        "vr": [
            {"text": "Игры", "question": "игры в vr", "answer": "У нас есть различные VR-игры: экшены, гонки, головоломки! 🎮"},
            {"text": "Цены", "question": "стоимость vr", "answer": "VR-сеанс стоит от 300 рублей за 30 минут! 💰"},
            {"text": "Забронировать", "question": "забронировать vr", "answer": "Чтобы забронировать VR, перейдите на страницу бронирования! 📅"},
            {"text": "Правила", "question": "правила безопасности в vr", "answer": "В VR-зоне необходимо соблюдать технику безопасности! ⚠️"}
        ],
        "батуты": [
            {"text": "Для детей?", "question": "можно ли на батуты с маленькими детьми", "answer": "Да, у нас есть специальные батуты для детей от 3 лет! 👶"},
            {"text": "Цены", "question": "стоимость батутов", "answer": "Батутный центр - от 500 рублей за час! 🏀"},
            {"text": "Забронировать", "question": "забронировать батуты", "answer": "Забронируйте батуты через нашу систему бронирования! 🎯"},
            {"text": "Аниматор", "question": "есть ли аниматор на батуты", "answer": "Да, мы предоставляем услуги аниматора для детских праздников! 🎪"}
        ],
        "default": [
            {"text": "Забронировать", "question": "хочу забронировать", "answer": "Перейдите на страницу бронирования для оформления заказа! 📋"},
            {"text": "Цены", "question": "цены", "answer": "Цены зависят от выбранного аттракциона. Уточните у нашего менеджера! 💵"}
        ]
    }
    
    # Сохраняем дефолтные подсказки только при первом создании
    try:
        with open(SUGGESTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(suggestionMap, f, ensure_ascii=False, indent=4)
        print("✅ Создан файл suggestions.json по умолчанию")
    except Exception as e:
        print(f"❌ Ошибка сохранения подсказок: {e}")

def save_suggestion_map():
    """Сохраняет контекстные подсказки в JSON"""
    try:
        with open(SUGGESTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(suggestionMap, f, ensure_ascii=False, indent=4)
        print("✅ Подсказки сохранены")
    except Exception as e:
        print(f"❌ Ошибка сохранения подсказок: {e}")

def load_menu_categories():
    """Загружает категории меню из JSON файла."""
    if os.path.exists(MENU_CATEGORIES_FILE):
        try:
            with open(MENU_CATEGORIES_FILE, 'r', encoding='utf-8') as f:
                categories = json.load(f)
            # Преобразуем в структуру, ожидаемую шаблоном
            return {
                "system_categories": {
                    "attractions": "🎪 Аттракционы",
                    "events": "🎉 Мероприятия",
                    "services": "🛠️ Услуги",
                    "info": "ℹ️ Информация"
                },
                "custom_categories": {k: v for k, v in categories.items() 
                                    if k not in ['attractions', 'events', 'services', 'info']}
            }
        except Exception as e:
            print(f"❌ Ошибка загрузки категорий меню: {e}")
            return {
                "system_categories": {
                    "attractions": "🎪 Аттракционы",
                    "events": "🎉 Мероприятия",
                    "services": "🛠️ Услуги",
                    "info": "ℹ️ Информация"
                },
                "custom_categories": {}
            }
    else:
        default_categories = {
            "attractions": "🎪 Аттракционы",
            "events": "🎉 Мероприятия",
            "services": "🛠️ Услуги",
            "info": "ℹ️ Информация"
        }
        save_menu_categories(default_categories)
        return {
            "system_categories": default_categories,
            "custom_categories": {}
        }

def save_menu_categories(categories_dict):
    """Сохраняет категории меню в JSON файл."""
    try:
        # Сохраняем как плоский словарь для обратной совместимости
        flat_categories = {}
        if "system_categories" in categories_dict:
            flat_categories.update(categories_dict["system_categories"])
        if "custom_categories" in categories_dict:
            flat_categories.update(categories_dict["custom_categories"])
        
        with open(MENU_CATEGORIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(flat_categories, f, ensure_ascii=False, indent=2)
        print("✅ Категории меню сохранены")
    except Exception as e:
        print(f"❌ Ошибка сохранения категорий меню: {e}")

def load_menu():
    """Загружает меню из JSON"""
    global MENU_CACHE
    
    # Используем кэш если есть
    if MENU_CACHE is not None:
        return MENU_CACHE
        
    menu_items = []
    if os.path.exists(MENU_FILE):
        try:
            with open(MENU_FILE, "r", encoding="utf-8") as f:
                menu_items = json.load(f)
            print("✅ Меню загружено")
            MENU_CACHE = menu_items
        except Exception as e:
            print(f"❌ Ошибка загрузки меню: {e}")
    else:
        menu_items = [
            {"admin_text": "VR-зоны", "display_text": "🎮 VR-зоны — от 300 ₽", "question": "vr", "category": "attractions", "price_info": "от 300 ₽", "suggestion_topic": "vr"},
            {"admin_text": "Батуты", "display_text": "🏀 Батутный центр — от 500 ₽", "question": "батуты", "category": "attractions", "price_info": "от 500 ₽", "suggestion_topic": "батуты"},
            {"admin_text": "Нерф", "display_text": "🔫 Нерф-арена — от 2500 ₽", "question": "нерф", "category": "attractions", "price_info": "от 2500 ₽", "suggestion_topic": "default"},
            {"admin_text": "День рождения", "display_text": "🎉 День рождения", "question": "день рождения", "category": "events", "price_info": "", "suggestion_topic": "default"},
            {"admin_text": "Выпускные", "display_text": "🎓 Выпускные", "question": "выпускные", "category": "events", "price_info": "", "suggestion_topic": "default"},
            {"admin_text": "Мероприятия", "display_text": "🎪 Мероприятия", "question": "мероприятия", "category": "events", "price_info": "", "suggestion_topic": "default"}
        ]
        with open(MENU_FILE, "w", encoding="utf-8") as f:
            json.dump(menu_items, f, ensure_ascii=False, indent=4)
        print("✅ Создан файл menu.json по умолчанию")
        MENU_CACHE = menu_items
    return menu_items

def save_menu(menu_items):
    """Сохраняет меню в JSON"""
    try:
        with open(MENU_FILE, "w", encoding="utf-8") as f:
            json.dump(menu_items, f, ensure_ascii=False, indent=4)
        print("✅ Меню сохранено")
        
        # 🔥 Принудительно обновляем глобальную переменную
        global MENU_CACHE
        MENU_CACHE = menu_items
        
    except Exception as e:
        print(f"❌ Ошибка сохранения меню: {e}")

# - Загрузка данных при старте -
load_knowledge_base()
load_bookings()
load_suggestion_map()
load_menu()

# - Маршруты -
@app.route("/")
def index():
    """Главная страница"""
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    """Обработка чат-сообщений с возвратом подсказок"""
    try:
        data = request.json
        question = data.get("message", "").strip().lower()
        
        print(f"🔍 Вопрос: {question}")
        print(f"📋 Доступные темы подсказок: {list(suggestionMap.keys())}")

        if not question:
            return jsonify({"response": "Пожалуйста, задайте вопрос.", "source": "error", "suggestions": []})
        
        # Сначала проверяем suggestionMap (подсказки с ответами)
        response = None
        source = "suggestion_map"
        suggestions = []
        found_topic = None
        
        # Ищем ответ в suggestionMap по точному совпадению вопроса
        for topic, items in suggestionMap.items():
            for item in items:
                if item["question"] == question:
                    response = item.get("answer")
                    found_topic = topic
                    print(f"✅ Найден ответ в теме: {topic}")
                    break
            if response:
                break
        
        # Если не нашли в suggestionMap, проверяем базу знаний
        if not response:
            response = KNOWLEDGE_BASE.get(question)
            source = "knowledge_base"
            if response:
                print(f"✅ Найден ответ в базе знаний")
        
        # Если все еще нет ответа, используем Yandex GPT
        if not response:
            try:
                response = call_yandex_gpt(question)
                source = "yandex_gpt"
                print(f"✅ Ответ от Yandex GPT")
            except Exception as e:
                response = f"❌ Ошибка: {str(e)}"
                source = "error"
        
        # Получаем подсказки для текущей темы
        if found_topic:
            # Если нашли тему в suggestionMap, берем все подсказки из этой темы
            suggestions = [{"text": s["text"], "question": s["question"]} for s in suggestionMap.get(found_topic, [])]
            print(f"🎯 Подсказки из темы: {found_topic}")
        else:
            # Если не нашли тему, ищем по меню - определяем тему по простому вопросу
            menu_items = load_menu()
            menu_topic = None
            
            # Ищем соответствующий пункт меню
            for item in menu_items:
                if item["question"] == question:
                    menu_topic = item.get("suggestion_topic")
                    print(f"📌 Найден пункт меню с темой: {menu_topic}")
                    break
            
            # Если нашли тему в меню, берем подсказки для этой темы
            if menu_topic and menu_topic in suggestionMap:
                suggestions = [{"text": s["text"], "question": s["question"]} for s in suggestionMap.get(menu_topic, [])]
                print(f"🎯 Подсказки из темы меню: {menu_topic}")
            else:
                # Если тема не найдена, используем дефолтные подсказки
                suggestions = [{"text": s["text"], "question": s["question"]} for s in suggestionMap.get("default", [])]
                print(f"🎯 Использованы дефолтные подсказки")
        
        print(f"🎯 Найдено подсказок: {len(suggestions)}")
        print(f"🎯 Список подсказок: {[s['text'] for s in suggestions]}")
        
        log_interaction(question, response, source)
        return jsonify({
            "response": response,
            "source": source,
            "suggestions": suggestions
        })
    
    except Exception as e:
        print(f"❌ Ошибка в функции chat: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"response": "❌ Произошла ошибка при обработке запроса", "source": "error", "suggestions": []})

@app.route("/ask", methods=["POST"])
def ask():
    """Обработка вопросов"""
    data = request.json
    question = data.get("question", "").strip().lower()
    if not question:
        return jsonify({"answer": "Пожалуйста, задайте вопрос."})
    
    response = KNOWLEDGE_BASE.get(question)
    source = "knowledge_base"
    if not response:
        try:
            response = call_yandex_gpt(question)
            source = "yandex_gpt"
        except Exception as e:
            response = f"❌ Ошибка: {str(e)}"
            source = "error"
    
    log_interaction(question, response, source)
    return jsonify({"answer": response})

@app.route("/feedback", methods=["POST"])
def feedback():
    """Сохранение оценки ответа"""
    data = request.json
    question = data.get("question")
    feedback = data.get("feedback")
    feedback_file = "feedback.json"
    logs = []
    if os.path.exists(feedback_file):
        try:
            with open(feedback_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    logs = json.loads(content)
        except:
            pass
    logs.append({
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "feedback": feedback
    })
    try:
        with open(feedback_file, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=4)
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"❌ Ошибка сохранения оценки: {e}")
        return jsonify({"status": "error", "message": str(e)})

@app.route("/suggestions/<topic>")
def get_suggestions_by_topic(topic):
    """Возвращает подсказки для указанной темы"""
    try:
        # Ищем подсказки для указанной темы
        suggestions = suggestionMap.get(topic.lower(), [])
        
        # Если для темы нет подсказок, используем дефолтные
        if not suggestions:
            suggestions = suggestionMap.get("default", [])
            
        return jsonify({"suggestions": suggestions})
    except Exception as e:
        print(f"❌ Ошибка получения подсказок для темы {topic}: {e}")
        return jsonify({"suggestions": []})

@app.route("/api/menu-display")
def get_menu_display():
    """API для получения меню с отображаемым текстом"""
    menu_items = load_menu()
    display_items = []
    
    for item in menu_items:
        display_items.append({
            "text": item.get("display_text", item.get("admin_text", "")),
            "question": item.get("question", ""),
            "suggestion_topic": item.get("suggestion_topic", "default")
        })
    
    return jsonify(display_items)

@app.route("/admin/suggestions")
def admin_suggestions():
    """Редактирование контекстных подсказки"""
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    return render_template("admin/suggestions.html", suggestion_map=suggestionMap)

@app.route("/admin/suggestions", methods=["POST"])
def add_suggestion():
    """Добавление новой подсказки с ответом"""
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    
    topic = request.form.get("topic").strip().lower()
    text = request.form.get("suggestion-text").strip()
    question = request.form.get("suggestion-question").strip().lower()
    answer = request.form.get("suggestion-answer").strip()
    
    if not topic or not text or not question or not answer:
        flash("❌ Все поля обязательны", "error")
        return redirect(url_for("admin_suggestions"))
    
    if topic not in suggestionMap:
        suggestionMap[topic] = []
    
    if any(s["text"] == text for s in suggestionMap[topic]):
        flash("❌ Подсказка с таким названием уже существует", "error")
        return redirect(url_for("admin_suggestions"))
    
    # Добавляем answer в подсказку
    suggestionMap[topic].append({
        "text": text,
        "question": question,
        "answer": answer
    })
    
    save_suggestion_map()
    flash("✅ Подсказка добавлена", "success")
    return redirect(url_for("admin_suggestions"))

@app.route("/suggestion-answer", methods=["POST"])
def get_suggestion_answer():
    """Возвращает ответ для подсказки по вопросу из suggestionMap"""
    data = request.json
    question = data.get("question", "").strip().lower()

    if not question:
        return jsonify({"answer": "❌ Вопрос не указан"}), 400

    # Ищем ответ в suggestionMap
    for topic, suggestions in suggestionMap.items():
        for suggestion in suggestions:
            if suggestion.get("question", "").strip().lower() == question:
                return jsonify({"answer": suggestion.get("answer", "❌ Ответ не найден")})

    return jsonify({"answer": "❌ Ответ не найден"}), 404

@app.route("/admin/suggestions/delete/<topic>/<text>")
def delete_suggestion(topic, text):
    """Удаление подсказки"""
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    
    if topic in suggestionMap:
        suggestionMap[topic] = [s for s in suggestionMap[topic] if s["text"] != text]
        save_suggestion_map()
        flash("✅ Подсказка удалена", "success")
    else:
        flash("❌ Ошибка удаления", "error")
    
    return redirect(url_for("admin_suggestions"))

@app.route("/admin/menu")
def admin_menu():
    """Страница редактирования меню"""
    if not session.get("admin_logged_in"):
        flash("❌ Доступ запрещён", "error")
        return redirect(url_for("admin_login"))
    
    menu_items = load_menu()
    categories = load_menu_categories()
    
    return render_template("admin/menu_edit.html", 
                         menu_items=menu_items,
                         categories=categories)

@app.route("/admin/menu/add", methods=["POST"])
def add_menu_item():
    """Добавление новой кнопки в меню"""
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "error": "Доступ запрещён"}), 403
    
    try:
        admin_text = request.form.get("admin_text", "").strip()
        display_text = request.form.get("display_text", "").strip()
        question = request.form.get("question", "").strip().lower()
        category = request.form.get("category", "attractions")
        price_info = request.form.get("price_info", "")
        suggestion_topic = request.form.get("suggestion_topic", "default")
        
        if not admin_text or not display_text or not question:
            return jsonify({"success": False, "error": "Все поля обязательны"})
        
        menu_items = load_menu()
        
        # Проверка на дубликаты
        if any(item.get("admin_text") == admin_text for item in menu_items):
            return jsonify({"success": False, "error": "Кнопка с таким текстом для админки уже существует"})
        
        if any(item.get("question") == question for item in menu_items):
            return jsonify({"success": False, "error": "Кнопка с таким вопросом уже существует"})
        
        # Создаем новую кнопку
        new_item = {
            "admin_text": admin_text,
            "display_text": display_text,
            "question": question,
            "category": category,
            "price_info": price_info,
            "suggestion_topic": suggestion_topic
        }
        
        menu_items.append(new_item)
        save_menu(menu_items)
        
        logging.info(f"Администратор добавил кнопку в меню: {admin_text} -> {question} (категория: {category})")
        return jsonify({"success": True})
        
    except Exception as e:
        return jsonify({"success": False, "error": f"Ошибка сервера: {str(e)}"})

@app.route("/admin/menu/edit/<int:index>", methods=["GET"])
def edit_menu_item_form(index):
    """Отображение формы редактирования кнопки меню"""
    if not session.get("admin_logged_in"):
        flash("❌ Доступ запрещён", "error")
        return redirect(url_for("admin_login"))
    
    menu_items = load_menu()
    categories = load_menu_categories()
    
    if 0 <= index < len(menu_items):
        item_to_edit = menu_items[index]
        return render_template("admin/menu_edit.html", 
                             menu_items=menu_items,
                             categories=categories,
                             edit_item=item_to_edit,
                             edit_index=index)
    else:
        flash("❌ Неверный индекс кнопки", "error")
        return redirect(url_for("admin_menu"))

@app.route("/admin/menu/edit/<int:index>", methods=["POST"])
def edit_menu_item(index):
    """Обработка данных из формы редактирования кнопки меню"""
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "error": "Доступ запрещён"}), 403
    
    try:
        menu_items = load_menu()
        if not (0 <= index < len(menu_items)):
            return jsonify({"success": False, "error": "Неверный индекс кнопки"})

        admin_text = request.form.get("admin_text", "").strip()
        display_text = request.form.get("display_text", "").strip()
        question = request.form.get("question", "").strip().lower()
        category = request.form.get("category", "attractions")
        price_info = request.form.get("price_info", "")
        suggestion_topic = request.form.get("suggestion_topic", "default")

        if not admin_text or not display_text or not question:
            return jsonify({"success": False, "error": "Все поля обязательны"})

        # Проверка на дубликаты (кроме самого редактируемого элемента)
        for i, item in enumerate(menu_items):
            if i != index:
                if item.get("admin_text") == admin_text:
                    return jsonify({"success": False, "error": "Кнопка с таким текстом для админки уже существует"})
                if item.get("question") == question:
                    return jsonify({"success": False, "error": "Кнопка с таким вопросом уже существует"})

        # Обновляем элемент
        menu_items[index] = {
            "admin_text": admin_text,
            "display_text": display_text,
            "question": question,
            "category": category,
            "price_info": price_info,
            "suggestion_topic": suggestion_topic
        }
        
        save_menu(menu_items)
        logging.info(f"Администратор обновил кнопку в меню: {admin_text} -> {question} (категория: {category})")
        return jsonify({"success": True})
        
    except Exception as e:
        return jsonify({"success": False, "error": f"Ошибка сервера: {str(e)}"})

@app.route("/admin/menu/delete/<int:index>")
def delete_menu_item(index):
    """Удаление кнопки из меню"""
    if not session.get("admin_logged_in"):
        flash("❌ Доступ запрещён", "error")
        return redirect(url_for("admin_login"))
    
    try:
        menu_items = load_menu()
        if 0 <= index < len(menu_items):
            removed = menu_items.pop(index)
            save_menu(menu_items)
            flash(f"✅ Кнопка '{removed['admin_text']}' удалена", "success")
            logging.info(f"Администратор удалил кнопку из меню: {removed['admin_text']}")
        else:
            flash("❌ Неверный индекс кнопки", "error")
    except Exception as e:
        flash(f"❌ Ошибка при удалении: {str(e)}", "error")
    
    return redirect(url_for("admin_menu"))

@app.route('/menu-items')
@no_cache
def get_menu_items():
    """Возвращает меню для фронтенда"""
    menu_items = load_menu()
    return jsonify({"items": menu_items})

@app.route('/menu-items/<category>')
@no_cache
def get_menu_items_by_category(category):
    """Возвращает меню отфильтрованное по категории"""
    menu_items = load_menu()
    filtered_items = [item for item in menu_items if item.get("category") == category]
    return jsonify({"items": filtered_items})

@app.route("/admin/menu/categories/data")
def get_categories_data():
    """API для получения данных категорий"""
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Доступ запрещён"}), 403
    
    categories = load_menu_categories()
    return jsonify(categories)

@app.route("/admin/menu/categories")
def admin_menu_categories():
    """Страница управления темами (категориями) меню"""
    if not session.get("admin_logged_in"):
        flash("❌ Доступ запрещён", "error")
        return redirect(url_for("admin_login"))
    
    categories = load_menu_categories()
    return render_template("admin/menu_categories.html", 
                         categories=categories,
                         system_categories=SYSTEM_CATEGORIES)

@app.route("/admin/menu/categories", methods=["POST"])
def add_menu_category():
    """Добавление новой темы (категории)"""
    if not session.get("admin_logged_in"):
        flash("❌ Доступ запрещён", "error")
        return redirect(url_for("admin_login"))

    key = request.form.get("category_key", "").strip().lower()
    name = request.form.get("category_name", "").strip()

    if not key or not name:
        flash("❌ Оба поля обязательны для заполнения", "error")
        return redirect(url_for("admin_menu_categories"))

    if not re.match(r'^[a-z0-9_]+$', key):
         flash("❌ Ключ категории может содержать только латинские буквы в нижнем регистре, цифры и подчеркивание", "error")
         return redirect(url_for("admin_menu_categories"))

    categories = load_menu_categories()
    
    if key in categories.get("system_categories", {}) or key in categories.get("custom_categories", {}):
        flash("❌ Категория с таким ключом уже существует", "error")
        return redirect(url_for("admin_menu_categories"))

    # Обновляем пользовательские категории
    custom_categories = categories.get("custom_categories", {})
    custom_categories[key] = name
    categories["custom_categories"] = custom_categories
    
    save_menu_categories(categories)
    
    flash(f"✅ Категория '{name}' успешно добавлена", "success")
    logging.info(f"Администратор добавил категорию меню: {key} -> {name}")
    return redirect(url_for("admin_menu_categories"))

@app.route("/admin/menu/categories/delete/<string:key>")
def delete_menu_category(key):
    """Удаление темы (категории)"""
    if not session.get("admin_logged_in"):
        flash("❌ Доступ запрещён", "error")
        return redirect(url_for("admin_login"))
    
    if key in SYSTEM_CATEGORIES:
        flash("❌ Нельзя удалить системную категорию", "error")
        return redirect(url_for("admin_menu_categories"))

    categories = load_menu_categories()
    
    if key in categories.get("custom_categories", {}):
        # Проверка: нельзя удалить категорию, если есть кнопки с этой категорией
        menu_items = load_menu()
        if any(item.get("category") == key for item in menu_items):
            flash("❌ Нельзя удалить категорию, к которой привязаны кнопки меню", "error")
            return redirect(url_for("admin_menu_categories"))
        
        del categories["custom_categories"][key]
        save_menu_categories(categories)
        flash(f"✅ Категория '{key}' успешно удалена", "success")
        logging.info(f"Администратор удалил категорию меню: {key}")
    else:
        flash("❌ Категория не найдена", "error")
        
    return redirect(url_for("admin_menu_categories"))

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Страница входа в админку"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == os.getenv("ADMIN_USER", "admin") and password == os.getenv("ADMIN_PASS", "1"):
            session["admin_logged_in"] = True
            logging.info("Администратор вошёл в систему")
            return redirect(url_for("admin_dashboard"))
        flash("❌ Неверный логин или пароль", "error")
        logging.warning("Неудачная попытка входа в админку")
    return render_template("admin/login.html")

@app.route("/admin")
def admin_dashboard():
    """Главная админки"""
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    
    return render_template("admin/dashboard.html", bookings=BOOKINGS)

@app.route("/admin/knowledge", methods=["GET", "POST"])
def knowledge_edit():
    """Редактирование базы знаний"""
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    
    if request.method == "POST":
        action = request.form.get("action")
        question = request.form.get("question", "").strip().lower()
        answer = request.form.get("answer", "").strip()
        
        if action == "add":
            if question and answer:
                KNOWLEDGE_BASE[question] = answer
                save_knowledge_base()
                logging.info(f"Добавлен вопрос: '{question}'")
                flash("✅ Вопрос добавлен", "success")
            else:
                flash("❌ Все поля обязательны", "error")
        elif action == "edit":
            if question and answer and question in KNOWLEDGE_BASE:
                KNOWLEDGE_BASE[question] = answer
                save_knowledge_base()
                logging.info(f"Изменён вопрос: '{question}'")
                flash("✅ Ответ обновлён", "success")
            else:
                flash("❌ Неверные данные", "error")
        elif action == "delete":
            if question in KNOWLEDGE_BASE:
                del KNOWLEDGE_BASE[question]
                save_knowledge_base()
                logging.info(f"Удалён вопрос: '{question}'")
                flash("✅ Вопрос удалён", "success")
            else:
                flash("❌ Вопрос не найден", "error")
    
    load_knowledge_base()
    return render_template("admin/knowledge_edit.html", knowledge=KNOWLEDGE_BASE)

@app.route("/admin/logs")
def view_logs():
    """Просмотр истории диалогов"""
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    
    logs = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    logs = json.loads(content)
            logs = sorted(logs, key=lambda x: x["timestamp"], reverse=True)
        except Exception as e:
            logging.error(f"Ошибка чтения логов: {e}")
            flash("❌ Ошибка загрузки логов", "error")
    
    return render_template("admin/logs.html", logs=logs)

@app.route("/admin/edit_response", methods=["POST"])
def edit_response():
    """Редактирование ответа из логов"""
    if not session.get("admin_logged_in"):
        return jsonify({"status": "error", "message": "Доступ запрещён"}), 403
    
    question = request.form.get("question")
    new_answer = request.form.get("answer")
    
    if question and new_answer:
        KNOWLEDGE_BASE[question] = new_answer
        save_knowledge_base()
        logging.info(f"Изменён ответ через админку: '{question}'")
        return jsonify({"status": "ok"})
    
    return jsonify({"status": "error", "message": "Некорректные данные"}), 400

@app.route("/admin/export_logs")
def export_logs():
    """Экспорт логов диалогов"""
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    
    if os.path.exists(LOG_FILE):
        return send_from_directory(".", "bot_log.json", as_attachment=True)
    
    flash("❌ Файл логов не найден", "error")
    return redirect(url_for("view_logs"))

@app.route("/admin/logout")
def admin_logout():
    """Выход из админки"""
    session.pop("admin_logged_in", None)
    flash("Вы вышли из админки", "info")
    logging.info("Администратор вышел из системы")
    return redirect(url_for("index"))

@app.route("/static/<path:path>")
def send_static(path):
    """Раздача статики"""
    return send_from_directory("static", path)

@app.route("/booking", methods=["GET", "POST"])
def booking():
    """Страница бронирования"""
    if request.method == "POST":
        name = request.form.get("name")
        phone = request.form.get("phone")
        date = request.form.get("date")
        guests = request.form.get("guests")
        event_type = request.form.get("event_type")
        
        if name and phone and date and guests and event_type:
            new_booking = {
                "name": name,
                "phone": phone,
                "date": date,
                "guests": guests,
                "event_type": event_type,
                "timestamp": datetime.now().isoformat()
            }
            BOOKINGS.append(new_booking)
            save_bookings()
            logging.info(f"Новая бронь: {name}, {phone}")
            return render_template("booking.html", success="Спасибо! Мы свяжемся с вами.")
    
    return render_template("booking.html")

@app.route("/birthday_calc")
def birthday_calc():
    """Калькулятор дня рождения"""
    return render_template("birthday_calc.html")

@app.route("/clear-cache-now")
def clear_cache_now():
    """Срочная очистка кэша меню"""
    global MENU_CACHE
    MENU_CACHE = None
    load_menu()
    return "✅ Кэш меню очищен! Теперь обновите страницу чата."

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        print(f"❌ Ошибка определения IP: {e}")
        return "127.0.0.1"

def call_yandex_gpt(prompt, history=None):
    """Вызов Yandex GPT с повторными попытками"""
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Authorization": f"Api-Key {os.getenv('YANDEX_API_KEY')}",
        "x-folder-id": os.getenv("YANDEX_FOLDER_ID"),
        "Content-Type": "application/json"
    }
    
    system_prompt = """
    Ты - ассистент D-Space. Отвечай дружелюбно и информативно.
    Используй эмодзи для улучшения восприятия.
    Ты – дружелюбный консультант D-Space. Отвечай кратко, структурированно, с эмодзи.
    Если пользователь хочет заказать день рождения:
    Предложи пакеты: Стандарт (8000 ₽), Экстрим (12 000 ₽), VR-приключение (15 000 ₽).
    Предложи акции: +10% скидка при бронировании до 10 сентября.
    Уточни: количество гостей, тематику, место проведения.
    В конце предложи забронировать время или связаться по телефону.
    Не выдумывай цены – если не знаешь, скажи честно, но предложи помощь.
    """
    
    messages = [{"role": "system", "text": system_prompt}]
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
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Ошибка подключения (попытка {attempt + 1}): {str(e)}")
        time.sleep(1)
    
    return "❌ Не удалось получить ответ. Попробуйте позже."

def log_interaction(question, answer, source):
    """Логирует диалог в bot_log.json"""
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
        
        if len(logs) % 100 == 0:
            backup_path = os.path.join(BACKUPS_DIR, f"bot_log_{int(time.time())}.json")
            shutil.copy2(LOG_FILE, backup_path)
            print(f"🔄 Создана резервная копия: {backup_path}")
        
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=4)
        
        print("✅ Диалог сохранен в лог")
        logging.info("Диалог сохранен в лог")
    
    except Exception as e:
        print(f"❌ Ошибка сохранения лога: {e}")
        logging.error(f"Ошибка сохранения лога: {e}")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    print(f"🌐 Запуск сервера на http://{get_local_ip()}:{port}")
    print("💡 Для остановки сервера нажмите CTRL+C")
    app.run(host="0.0.0.0", port=port, debug=debug)