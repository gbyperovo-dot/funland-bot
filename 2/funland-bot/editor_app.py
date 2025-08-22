# editor_app.py
from flask import Flask, request, render_template, redirect, url_for, jsonify, flash
import json
import os
import shutil
from datetime import datetime
from markdown import markdown
from werkzeug.utils import secure_filename
import logging
from collections import OrderedDict

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Для flash-сообщений

# Конфигурация
JSON_PATH = "knowledge_base.json"
BACKUP_DIR = "backups"
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'csv', 'json'}

os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Настройка логгирования
logging.basicConfig(
    filename='knowledge_editor.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def load_data():
    """Загружает данные из JSON файла"""
    if not os.path.exists(JSON_PATH):
        return OrderedDict()
    
    try:
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f, object_pairs_hook=OrderedDict)
    except Exception as e:
        logging.error(f"Ошибка загрузки JSON: {str(e)}")
        return OrderedDict()

def save_data(data):
    """Сохраняет данные в JSON файл с созданием резервной копии"""
    try:
        # Создаем резервную копию
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, f"knowledge_backup_{timestamp}.json")
        if os.path.exists(JSON_PATH):
            shutil.copy2(JSON_PATH, backup_path)
            logging.info(f"Создана резервная копия: {backup_path}")
        
        # Сохраняем новые данные
        with open(JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        logging.error(f"Ошибка сохранения JSON: {str(e)}")
        return False

def allowed_file(filename):
    """Проверяет допустимость расширения файла"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Главная страница с поиском и списком вопросов"""
    search_query = request.args.get('q', '').lower()
    data = load_data()
    
    if search_query:
        filtered_data = OrderedDict()
        for k, v in data.items():
            if search_query in k.lower() or search_query in v.lower():
                filtered_data[k] = v
        data = filtered_data
    
    return render_template('editor.html', 
                         questions=data,
                         search_query=search_query,
                         total_questions=len(data))

@app.route('/edit/<question>', methods=['GET', 'POST'])
def edit_question(question):
    """Редактирование существующего вопроса"""
    data = load_data()
    
    if question not in data:
        flash('Вопрос не найден!', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        new_question = request.form['question'].strip().lower()
        new_answer = request.form['answer'].strip()
        
        # Валидация
        if not new_question or not new_answer:
            flash('Вопрос и ответ не могут быть пустыми!', 'error')
        elif len(new_question) < 3:
            flash('Вопрос слишком короткий (минимум 3 символа)!', 'error')
        else:
            # Удаляем старый вопрос, если он изменился
            if new_question != question:
                del data[question]
                logging.info(f"Вопрос переименован: '{question}' -> '{new_question}'")
            
            # Сохраняем изменения
            data[new_question] = new_answer
            if save_data(data):
                flash('Изменения сохранены успешно!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Ошибка при сохранении!', 'error')
    
    return render_template('edit.html', 
                         question=question, 
                         answer=data[question])

@app.route('/add', methods=['GET', 'POST'])
def add_question():
    """Добавление нового вопроса"""
    if request.method == 'POST':
        question = request.form['question'].strip().lower()
        answer = request.form['answer'].strip()
        data = load_data()
        
        # Валидация
        if not question or not answer:
            flash('Вопрос и ответ не могут быть пустыми!', 'error')
        elif len(question) < 3:
            flash('Вопрос слишком короткий (минимум 3 символа)!', 'error')
        elif question in data:
            flash('Такой вопрос уже существует!', 'error')
        else:
            data[question] = answer
            if save_data(data):
                flash('Вопрос добавлен успешно!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Ошибка при сохранении!', 'error')
    
    return render_template('add.html')

@app.route('/delete/<question>')
def delete_question(question):
    """Удаление вопроса"""
    data = load_data()
    if question in data:
        del data[question]
        if save_data(data):
            flash('Вопрос удалён успешно!', 'success')
            logging.info(f"Удалён вопрос: '{question}'")
        else:
            flash('Ошибка при удалении!', 'error')
    else:
        flash('Вопрос не найден!', 'error')
    
    return redirect(url_for('index'))

@app.route('/import', methods=['GET', 'POST'])
def import_data():
    """Импорт данных из файла"""
    if request.method == 'POST':
        # Проверяем, есть ли файл в запросе
        if 'file' not in request.files:
            flash('Файл не выбран!', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        
        # Проверяем имя файла
        if file.filename == '':
            flash('Файл не выбран!', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            
            try:
                new_data = OrderedDict()
                if filename.endswith('.json'):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        new_data = json.load(f, object_pairs_hook=OrderedDict)
                elif filename.endswith('.csv'):
                    import csv
                    with open(filepath, 'r', encoding='utf-8-sig') as f:
                        reader = csv.reader(f, delimiter=';')
                        next(reader)  # Пропускаем заголовок
                        for row in reader:
                            if len(row) >= 2:
                                question = row[0].strip().lower()
                                answer = row[1].replace('<br>', '\n').strip()
                                if question and answer:
                                    new_data[question] = answer
                
                # Объединяем с существующими данными
                data = load_data()
                data.update(new_data)
                
                if save_data(data):
                    flash(f'Успешно импортировано {len(new_data)} вопросов!', 'success')
                    logging.info(f"Импортировано {len(new_data)} вопросов из {filename}")
                else:
                    flash('Ошибка при сохранении импортированных данных!', 'error')
                
            except Exception as e:
                flash(f'Ошибка при обработке файла: {str(e)}', 'error')
                logging.error(f"Ошибка импорта: {str(e)}")
            
            # Удаляем временный файл
            os.remove(filepath)
            return redirect(url_for('index'))
    
    return render_template('import.html')

@app.route('/export')
def export_data():
    """Экспорт данных в JSON файл"""
    data = load_data()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"knowledge_export_{timestamp}.json"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logging.info(f"Экспортировано {len(data)} вопросов в {filename}")
        return jsonify({
            'status': 'success',
            'filename': filename,
            'count': len(data)
        })
    except Exception as e:
        logging.error(f"Ошибка экспорта: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/download/<filename>')
def download_file(filename):
    """Скачивание экспортированного файла"""
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    else:
        flash('Файл не найден!', 'error')
        return redirect(url_for('index'))

@app.template_filter('markdown')
def markdown_filter(text):
    """Фильтр для преобразования Markdown в HTML"""
    return markdown(text)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)