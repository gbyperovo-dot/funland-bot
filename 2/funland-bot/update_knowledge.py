# update_knowledge.py
import subprocess
import sys

def run(command):
    result = subprocess.run(command, shell=True, text=True, capture_output=True)
    print(result.stdout)
    if result.stderr:
        print("❌ Ошибка:", result.stderr)
    if result.returncode != 0:
        print("❌ Выполнение остановлено.")
        sys.exit(1)

print("🔄 Шаг 1: CSV → XLSX")
run("python csv_to_xlsx.py")

print("🔄 Шаг 2: XLSX → JSON")
run("python excel_to_json.py")

print("✅ Готово! База знаний обновлена.")