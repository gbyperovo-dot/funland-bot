# excel_to_json.py
import pandas as pd
import json
import os
import re

def clean_text(text):
    """Очистка текста от лишних пробелов и специальных символов"""
    if pd.isna(text) or text == 'None':
        return ""
    text = str(text).strip()
    # Заменяем множественные переносы строк на одинарные
    text = re.sub(r'\n+', '\n', text)
    # Удаляем лишние пробелы
    text = re.sub(r'[^\S\n]+', ' ', text)
    return text

def process_excel_to_json(file_path, output_file):
    try:
        # Чтение Excel файла
        df = pd.read_excel(
            file_path,
            sheet_name=0,
            engine='openpyxl',
            dtype=str,
            keep_default_na=False
        )

        # Поиск столбцов
        key_col, value_col = None, None
        for col in df.columns:
            col_lower = str(col).lower()
            if "вопрос" in col_lower or "key" in col_lower:
                key_col = col
            if "ответ" in col_lower or "value" in col_lower:
                value_col = col

        if not key_col or not value_col:
            available_cols = "\n".join(f"- {col}" for col in df.columns)
            raise ValueError(
                f"Не найдены нужные столбцы.\nДоступные столбцы:\n{available_cols}\n"
                f"Ищем столбцы, содержащие 'вопрос'/'key' и 'ответ'/'value'"
            )

        # Обработка данных
        knowledge_dict = {}
        current_key = None
        current_value = []

        for _, row in df.iterrows():
            key = clean_text(row[key_col])
            value = clean_text(row[value_col])

            if key:  # Новая запись
                if current_key and current_value:
                    full_answer = "\n".join(filter(None, current_value))
                    knowledge_dict[current_key.lower()] = full_answer
                current_key = key
                current_value = [value] if value else []
            elif value:  # Продолжение предыдущего ответа
                current_value.append(value)

        # Добавляем последнюю запись
        if current_key and current_value:
            full_answer = "\n".join(filter(None, current_value))
            knowledge_dict[current_key.lower()] = full_answer

        # Сохранение в JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(knowledge_dict, f, ensure_ascii=False, indent=4, sort_keys=True)

        print(f"✅ Успешно создан {output_file}")
        print(f"📊 Статистика:")
        print(f"- Всего вопросов: {len(knowledge_dict)}")
        print(f"- Пример первого вопроса: {next(iter(knowledge_dict))[:50]}...")

    except Exception as e:
        print(f"❌ Ошибка при обработке файла:")
        print(f"Тип ошибки: {type(e).__name__}")
        print(f"Сообщение: {str(e)}")
        if hasattr(e, 'args') and e.args:
            print(f"Детали: {e.args}")
        return False
    return True

if __name__ == "__main__":
    file_path = "knowledge_base.xlsx"
    output_file = "knowledge_base.json"
    
    if not os.path.exists(file_path):
        print(f"❌ Файл не найден: {file_path}")
        print("Убедитесь, что файл находится в правильной директории")
        exit(1)

    success = process_excel_to_json(file_path, output_file)
    if not success:
        print("\n💡 Советы по исправлению:")
        print("1. Проверьте названия столбцов в Excel-файле")
        print("2. Убедитесь, что нет объединенных ячеек")
        print("3. Проверьте, что файл не защищен паролем")
        print("4. Попробуйте открыть и сохранить файл вручную")
        exit(1)