#!/usr/bin/env python3
# csv_to_json.py
import csv
import json
import re
import os
import shutil
from collections import OrderedDict
from datetime import datetime

def create_backup(file_path):
    """Создаёт резервную копию файла с timestamp"""
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{backup_dir}/{os.path.basename(file_path)}_{timestamp}.bak"
    shutil.copy2(file_path, backup_name)
    return backup_name

def clean_text(text):
    """Очистка текста с сохранением форматирования"""
    if not text or text == 'None':
        return ""
    # Заменяем <br> на переносы строк
    text = text.replace('<br>', '\n')
    # Удаляем лишние кавычки
    text = re.sub(r'"+', '"', text)
    # Схлопываем множественные переносы строк
    text = re.sub(r'\n+', '\n', text)
    return text.strip()

def validate_entry(question, answer):
    """Проверка валидности вопроса и ответа"""
    if len(question) < 3:
        raise ValueError(f"Слишком короткий вопрос: '{question}'")
    if not answer.strip():
        raise ValueError(f"Пустой ответ для вопроса: '{question}'")
    if ';' in question:
        raise ValueError(f"Вопрос содержит запрещённый символ ';': '{question}'")

def parse_csv_to_dict(csv_path):
    """Парсинг CSV в словарь с объединением многострочных ответов"""
    knowledge = OrderedDict()
    current_key = None
    current_value = []
    line_num = 1  # Для отображения номера строки при ошибках
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f, delimiter=';')
        
        # Пропускаем заголовок
        try:
            header = next(reader)
            line_num += 1
            if len(header) < 2 or header[0].lower() not in ['question', 'вопрос']:
                raise ValueError("CSV должен содержать заголовки: Question;Answer")
        except StopIteration:
            raise ValueError("CSV файл пустой")

        for row in reader:
            line_num += 1
            if len(row) < 2:
                continue
                
            key = clean_text(row[0])
            value = clean_text(row[1])

            try:
                if key:  # Новый вопрос
                    if current_key:  # Сохраняем предыдущий
                        validate_entry(current_key, '\n'.join(current_value))
                        knowledge[current_key] = '\n'.join(current_value)
                    current_key = key.lower()
                    current_value = [value] if value else []
                elif value:  # Продолжение ответа
                    current_value.append(value)
            except ValueError as e:
                print(f"⚠️ Строка {line_num}: {str(e)}")
                continue
    
    # Добавляем последнюю запись
    if current_key:
        try:
            validate_entry(current_key, '\n'.join(current_value))
            knowledge[current_key] = '\n'.join(current_value)
        except ValueError as e:
            print(f"⚠️ Последняя запись: {str(e)}")
    
    return knowledge

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Конвертер CSV в JSON базы знаний')
    parser.add_argument('--csv', default='knowledge_edit.csv', help='Путь к CSV файлу')
    parser.add_argument('--json', default='knowledge_base.json', help='Путь для сохранения JSON')
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"❌ Файл не найден: {args.csv}")
        exit(1)

    try:
        # Загружаем существующий JSON, если он есть
        existing_data = OrderedDict()
        if os.path.exists(args.json):
            with open(args.json, 'r', encoding='utf-8') as f:
                existing_data = json.load(f, object_pairs_hook=OrderedDict)
            backup = create_backup(args.json)
            print(f"🔐 Создана резервная копия JSON: {backup}")

        print(f"🔍 Чтение CSV файла {args.csv}...")
        new_data = parse_csv_to_dict(args.csv)
        
        # Объединяем данные (новые данные перезаписывают существующие)
        merged_data = OrderedDict()
        merged_data.update(existing_data)
        merged_data.update(new_data)
        
        print("💾 Сохранение в JSON...")
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(merged_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Успешно! Обновлён файл: {args.json}")
        print("\n📊 Статистика:")
        print(f"- Всего вопросов: {len(merged_data)}")
        print(f"- Новых/обновлённых: {len(new_data)}")
        print(f"- Удалённых: {len(existing_data) - len(set(existing_data) - set(new_data))}")
        
        # Проверка дубликатов (регистронезависимых)
        from collections import Counter
        duplicates = [q for q, cnt in Counter(k.lower() for k in merged_data.keys()).items() if cnt > 1]
        if duplicates:
            print("\n⚠️ Внимание: найдены дубликаты (разный регистр):")
            for d in duplicates[:3]:
                print(f"  - {d}")
            if len(duplicates) > 3:
                print(f"  ... и ещё {len(duplicates)-3}")

    except Exception as e:
        print(f"\n❌ Ошибка: {type(e).__name__}")
        print(f"Сообщение: {str(e)}")
        print("\n💡 Проверьте:")
        print("1. Формат CSV (должен быть разделитель ';')")
        print("2. Наличие заголовков Question;Answer")
        print("3. Что нет пустых строк в вопросах")
        exit(1)

if __name__ == "__main__":
    main()