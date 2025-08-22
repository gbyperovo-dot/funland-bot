# split_to_excel.py
import pandas as pd

# Исходный текст (можно загрузить из .txt)
data = """
привет|👋 Привет! Рад вас видеть в FunLand! 😊
меню|🏠 Главное меню
vr|🎮 VR-зоны
батуты|🏀 Батутный центр
нерф|🔫 Нерф-арена
"""

# Разделяем строки и парсим
rows = []
for line in data.strip().split('\n'):
    if '|' in line:
        key, value = line.split('|', 1)  # 1 — только первое разделение
        rows.append({"key (вопрос)": key.strip(), "value (ответ)": value.strip()})

# Сохраняем в Excel
df = pd.DataFrame(rows)
df.to_excel("knowledge_base.xlsx", index=False)
print("✅ Готово! Файл сохранён как knowledge_base.xlsx")