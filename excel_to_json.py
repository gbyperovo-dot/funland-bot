# excel_to_json.py
import pandas as pd
import json
import os

# Пути
file_path = "knowledge_base.xlsx"
sheet_name = 0  # Читаем первый лист

# Проверка существования файла
if not os.path.exists(file_path):
    print(f"❌ Файл не найден: {file_path}")
    print("Убедитесь, что файл лежит в папке c:\\funland-bot\\")
    exit()

try:
    # Читаем Excel (указываем engine!)
    df = pd.read_excel(file_path, sheet_name=sheet_name, engine='openpyxl')

    # Смотрим, какие столбцы есть
    print(f"✅ Доступные столбцы: {list(df.columns)}")

    # Нормализуем названия столбцов: убираем пробелы, делаем lowercase
    df.columns = [col.strip().replace(" ", "").upper() for col in df.columns]

    # Теперь ищем нужные столбцы по шаблону
    key_col = None
    value_col = None

    for col in df.columns:
        if "ВОПРОС" in col:
            key_col = col
        if "ОТВЕТ" in col:
            value_col = col

    if not key_col:
        print("❌ Не найден столбец с 'ВОПРОС'")
        print("Проверьте, что в Excel есть столбец с названием, содержащим 'ВОПРОС'")
        exit()
    if not value_col:
        print("❌ Не найден столбец с 'ОТВЕТ'")
        print("Проверьте, что в Excel есть столбец с названием, содержащим 'ОТВЕТ'")
        exit()

    # Переименовываем для удобства
    df.rename(columns={key_col: "key", value_col: "value"}, inplace=True)

    # Удаляем пустые строки
    df.dropna(subset=["key"], inplace=True)

    # Создаём словарь: вопрос → ответ
    knowledge_dict = {}
    for _, row in df.iterrows():
        question = str(row["key"]).strip().lower()
        answer = str(row["value"]).strip()
        if question and answer:
            knowledge_dict[question] = answer

    # Сохраняем в JSON
    with open("knowledge_base.json", "w", encoding="utf-8") as f:
        json.dump(knowledge_dict, f, ensure_ascii=False, indent=4)

    print(f"✅ Успешно конвертировано! Сохранено в knowledge_base.json")
    print(f"📦 Количество вопросов: {len(knowledge_dict)}")

except Exception as e:
    print(f"❌ Ошибка: {e}")
    if "bad magic number" in str(e):
        print("💡 Возможно, файл не .xlsx, а .xls. Сохраните как 'Книга Excel (*.xlsx)'")
    elif "openpyxl" in str(e):
        print("💡 Установите: pip install openpyxl")