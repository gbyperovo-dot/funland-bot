from flask import Flask, request, render_template, redirect, url_for, flash, send_file
import json
import os
import shutil
from datetime import datetime
from markdown import markdown
from werkzeug.utils import secure_filename
import logging
from collections import OrderedDict

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Настройка логгирования
logging.basicConfig(
    filename='knowledge_editor.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def load_data():
    if not os.path.exists('knowledge_base.json'):
        return OrderedDict()
    try:
        with open('knowledge_base.json', 'r', encoding='utf-8') as f:
            return json.load(f, object_pairs_hook=OrderedDict)
    except Exception as e:
        logging.error(f"Ошибка загрузки JSON: {str(e)}")
        return OrderedDict()

def save_data(data):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"backups/knowledge_backup_{timestamp}.json"
        os.makedirs('backups', exist_ok=True)
        if os.path.exists('knowledge_base.json'):
            shutil.copy2('knowledge_base.json', backup_path)
        
        with open('knowledge_base.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logging.error(f"Ошибка сохранения: {str(e)}")
        return False

@app.route('/')
def index():
    search_query = request.args.get('q', '').lower()
    data = load_data()
    
    if search_query:
        filtered_data = OrderedDict()
        for k, v in data.items():
            if search_query in k.lower() or search_query in v.lower():
                filtered_data[k] = v
        data = filtered_data
    
    return render_template('index.html', 
                         questions=data,
                         search_query=search_query,
                         total_questions=len(data))

@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        question = request.form['question'].strip().lower()
        answer = request.form['answer'].strip()
        data = load_data()
        
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
            else:
                flash('Ошибка при сохранении!', 'danger')
    
    return render_template('add.html')

@app.route('/edit/<question>', methods=['GET', 'POST'])
def edit(question):
    data = load_data()
    
    if question not in data:
        flash('Вопрос не найден!', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        new_question = request.form['question'].strip().lower()
        new_answer = request.form['answer'].strip()
        
        if not new_question or not new_answer:
            flash('Вопрос и ответ не могут быть пустыми!', 'danger')
        else:
            if new_question != question:
                del data[question]
            data[new_question] = new_answer
            if save_data(data):
                flash('Изменения сохранены!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Ошибка при сохранении!', 'danger')
    
    return render_template('edit.html', 
                         question=question, 
                         answer=data[question])

@app.route('/delete/<question>')
def delete(question):
    data = load_data()
    if question in data:
        del data[question]
        if save_data(data):
            flash('Вопрос удалён!', 'success')
        else:
            flash('Ошибка при удалении!', 'danger')
    else:
        flash('Вопрос не найден!', 'danger')
    
    return redirect(url_for('index'))

@app.route('/import', methods=['GET', 'POST'])
def import_data():
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
                        next(reader)
                        for row in reader:
                            if len(row) >= 2:
                                question = row[0].strip().lower()
                                answer = row[1].replace('<br>', '\n').strip()
                                if question and answer:
                                    new_data[question] = answer
                
                data = load_data()
                data.update(new_data)
                
                if save_data(data):
                    flash(f'Импортировано {len(new_data)} вопросов!', 'success')
                else:
                    flash('Ошибка при сохранении импортированных данных', 'danger')
                
            except Exception as e:
                flash(f'Ошибка при обработке файла: {str(e)}', 'danger')
            
            os.remove(filepath)
            return redirect(url_for('index'))
    
    return render_template('import.html')

@app.route('/export')
def export():
    data = load_data()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"knowledge_export_{timestamp}.json"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return send_file(filepath, as_attachment=True)
    except Exception as e:
        flash(f'Ошибка при экспорте: {str(e)}', 'danger')
        return redirect(url_for('index'))

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'json', 'csv'}

@app.template_filter('markdown')
def markdown_filter(text):
    return markdown(text)

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)