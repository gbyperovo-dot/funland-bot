from flask import Flask, request, render_template, redirect, url_for, flash, send_file, jsonify
import json
import os
import shutil
from datetime import datetime
from markdown import markdown
from werkzeug.utils import secure_filename
import logging
from collections import OrderedDict

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Более безопасный ключ
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
app.config['TEMPLATES_AUTO_RELOAD'] = True  # Автоперезагрузка шаблонов

# Настройка логгирования
logging.basicConfig(
    filename='knowledge_editor.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'  # Добавлено для корректного логирования
)

def load_data():
    """Загрузка данных с обработкой ошибок"""
    if not os.path.exists('knowledge_base.json'):
        return OrderedDict()
    try:
        with open('knowledge_base.json', 'r', encoding='utf-8') as f:
            return json.load(f, object_pairs_hook=OrderedDict)
    except json.JSONDecodeError as e:
        logging.error(f"Ошибка декодирования JSON: {str(e)}")
        return OrderedDict()
    except Exception as e:
        logging.error(f"Ошибка загрузки файла: {str(e)}")
        return OrderedDict()

def save_data(data):
    """Сохранение данных с созданием резервной копии"""
    try:
        # Создаем папку для резервных копий, если ее нет
        os.makedirs('backups', exist_ok=True)
        
        # Создаем резервную копию
        if os.path.exists('knowledge_base.json'):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join('backups', f'knowledge_backup_{timestamp}.json')
            shutil.copy2('knowledge_base.json', backup_path)
            logging.info(f"Создана резервная копия: {backup_path}")
        
        # Сохраняем новые данные
        with open('knowledge_base.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logging.error(f"Ошибка сохранения: {str(e)}")
        return False

@app.route('/')
def index():
    """Главная страница с поиском"""
    search_query = request.args.get('q', '').lower()
    data = load_data()
    
    if search_query:
        filtered_data = OrderedDict()
        for k, v in data.items():
            if search_query in k.lower() or search_query in v.lower():
                filtered_data[k] = v
        data = filtered_data
    
    return render_template('admin_panel.html',  # Изменено на admin_panel.html
                         questions=data,
                         search_query=search_query,
                         total_questions=len(data))

@app.route('/add', methods=['GET', 'POST'])
def add():
    """Добавление нового вопроса с валидацией"""
    if request.method == 'POST':
        question = request.form.get('question', '').strip().lower()
        answer = request.form.get('answer', '').strip()
        data = load_data()
        
        # Валидация
        if not question or not answer:
            flash('Вопрос и ответ не могут быть пустыми!', 'danger')
        elif len(question) < 3:
            flash('Вопрос должен содержать минимум 3 символа!', 'danger')
        elif question in data:
            flash('Такой вопрос уже существует!', 'danger')
        else:
            data[question] = answer
            if save_data(data):
                flash('Вопрос успешно добавлен!', 'success')
                return redirect(url_for('index'))
            flash('Ошибка при сохранении!', 'danger')
    
    return render_template('add.html')

@app.route('/edit/<question>', methods=['GET', 'POST'])
def edit(question):
    """Редактирование вопроса с проверкой существования"""
    data = load_data()
    
    if question not in data:
        flash('Вопрос не найден!', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        new_question = request.form.get('question', '').strip().lower()
        new_answer = request.form.get('answer', '').strip()
        
        if not new_question or not new_answer:
            flash('Вопрос и ответ не могут быть пустыми!', 'danger')
        else:
            # Если вопрос изменился, удаляем старую версию
            if new_question != question:
                del data[question]
            data[new_question] = new_answer
            
            if save_data(data):
                flash('Изменения сохранены!', 'success')
                return redirect(url_for('index'))
            flash('Ошибка при сохранении!', 'danger')
    
    return render_template('edit.html',
                         question=question,
                         answer=data[question])

@app.route('/delete/<question>')
def delete(question):
    """Удаление вопроса с подтверждением"""
    data = load_data()
    if question in data:
        del data[question]
        if save_data(data):
            flash('Вопрос удалён!', 'success')
            logging.info(f"Удален вопрос: {question}")
        else:
            flash('Ошибка при удалении!', 'danger')
    else:
        flash('Вопрос не найден!', 'danger')
    
    return redirect(url_for('index'))

@app.route('/import', methods=['GET', 'POST'])
def import_data():
    """Импорт данных из файла"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Файл не выбран', 'danger')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('Файл не выбран', 'danger')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            try:
                # Сохраняем временный файл
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(filepath)
                
                # Обрабатываем файл
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
                    flash('Ошибка при сохранении импортированных данных', 'danger')
                
            except Exception as e:
                flash(f'Ошибка при обработке файла: {str(e)}', 'danger')
                logging.error(f"Ошибка импорта: {str(e)}")
            
            finally:
                # Удаляем временный файл
                if os.path.exists(filepath):
                    os.remove(filepath)
            
            return redirect(url_for('index'))
    
    return render_template('import.html')

@app.route('/export')
def export():
    """Экспорт данных в JSON файл"""
    try:
        data = load_data()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"knowledge_export_{timestamp}.json"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Создаем папку, если ее нет
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logging.info(f"Экспортировано {len(data)} вопросов в {filename}")
        return send_file(filepath, as_attachment=True)
    
    except Exception as e:
        flash(f'Ошибка при экспорте: {str(e)}', 'danger')
        logging.error(f"Ошибка экспорта: {str(e)}")
        return redirect(url_for('index'))

def allowed_file(filename):
    """Проверка разрешенных расширений файлов"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'json', 'csv'}

@app.template_filter('markdown')
def markdown_filter(text):
    """Фильтр для преобразования Markdown в HTML"""
    return markdown(text) if text else ''

@app.errorhandler(404)
def page_not_found(e):
    """Обработка 404 ошибок"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    """Обработка 500 ошибок"""
    logging.error(f"500 Error: {str(e)}")
    return render_template('500.html'), 500

if __name__ == '__main__':
    # Создаем необходимые директории
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs('backups', exist_ok=True)
    
    # Запуск сервера
    app.run(
        host='0.0.0.0',
        port=5001,  # Изменен порт на 5001
        debug=True,
        use_reloader=True
    )