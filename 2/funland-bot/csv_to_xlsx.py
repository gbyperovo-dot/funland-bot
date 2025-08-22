# csv_to_xlsx.py
import pandas as pd
import sys
import csv
from io import StringIO

def clean_text(text):
    """Очистка текста от лишних кавычек и замена <br> на переносы строк"""
    if pd.isna(text):
        return ""
    text = str(text).replace('""', '"').replace('"', '')
    return text.replace('<br>', '\n')

print("🔄 Шаг 1: CSV → XLSX")

try:
    # Читаем CSV файл с учетом разделителя ";"
    with open('knowledge.csv', 'r', encoding='utf-8-sig') as f:
        content = f.read()
        
        # Удаляем лишние кавычки и заменяем <br> на переносы строк
        cleaned_content = clean_text(content)
        
        # Используем csv.reader с правильным разделителем
        reader = csv.reader(StringIO(cleaned_content), delimiter=';')
        rows = list(reader)
    
    # Проверяем заголовки
    if len(rows[0]) != 2:
        print("❌ Ошибка: CSV должен содержать ровно 2 столбца")
        print(f"Найдено столбцов: {len(rows[0])}")
        sys.exit(1)
    
    # Создаем DataFrame
    df = pd.DataFrame(rows[1:], columns=rows[0])
    
    # Удаляем полностью пустые строки
    df = df.dropna(how='all')
    
    # Проверяем, что осталось 2 столбца
    if df.shape[1] != 2:
        print(f"❌ Ошибка: После обработки осталось {df.shape[1]} столбцов вместо 2")
        sys.exit(1)
    
    # Применяем очистку к каждому значению
    df = df.applymap(clean_text)
    
    # Сохраняем как XLSX
    with pd.ExcelWriter("knowledge_base.xlsx", engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Знания")
    
    print("✅ Успешно: knowledge.csv → knowledge_base.xlsx")
    print(f"📊 Обработано строк: {len(df)}")

except Exception as e:
    print(f"❌ Критическая ошибка: {str(e)}")
    sys.exit(1)