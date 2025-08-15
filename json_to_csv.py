#!/usr/bin/env python3
# json_to_csv.py
import json
import csv
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

def json_to_csv(json_path, csv_path):
    """Конвертирует JSON в CSV для удобного редактирования"""
    try:
        # Создаём резервную копию CSV, если он существует
        if os.path.exists(csv_path):
            backup = create_backup(csv_path)
            print(f"🔐 Создана резервная копия CSV: {backup}")

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f, object_pairs_hook=OrderedDict)
        
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(["Question", "Answer"])  # Заголовки
            for question, answer in data.items():
                # Экранируем переносы строк для CSV
                answer_cleaned = answer.replace('\n', '<br>')
                writer.writerow([question, answer_cleaned])
        
        print(f"✅ JSON успешно конвертирован в {csv_path}")
        print("\n💡 Инструкция по редактированию:")
        print("- Сохраняйте формат: Вопрос;Ответ")
        print("- Для переносов строк используйте <br>")
        print("- Не удаляйте первую строку с заголовками")
        print("- После редактирования запустите csv_to_json.py")
        
        return True

    except Exception as e:
        print(f"❌ Ошибка конвертации: {type(e).__name__}")
        print(f"Сообщение: {str(e)}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Конвертер JSON в CSV для редактирования')
    parser.add_argument('--json', default='knowledge_base.json', help='Путь к JSON файлу')
    parser.add_argument('--csv', default='knowledge_edit.csv', help='Путь для сохранения CSV')
    args = parser.parse_args()

    if not os.path.exists(args.json):
        print(f"❌ Файл не найден: {args.json}")
        exit(1)

    success = json_to_csv(args.json, args.csv)
    if not success:
        exit(1)