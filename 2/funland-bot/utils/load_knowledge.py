# utils/load_knowledge.py
import os
import json

def load_knowledge_base(file_path="knowledge_base.json"):
    """
    Загружает базу знаний из JSON-файла
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл базы знаний не найден: {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        kb = json.load(f)
    
    print(f"✅ Загружено {len(kb)} ответов из {file_path}")
    return kb