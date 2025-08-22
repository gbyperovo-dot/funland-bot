@echo off
cd C:\funland-bot
python excel_to_json.py
python web_app.py
echo "Скрипт завершён, но окно оставлено открытым."
cmd /k