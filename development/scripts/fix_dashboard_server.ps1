# --------------------------------------------
# Скрипт: fix_dashboard_server.ps1
# Назначение: [КОРОТКОЕ ОПИСАНИЕ ФАЙЛА, УКАЖИ ЧТО ДЕЛАЕТ]
# Автор: Crown Aliy
# Дата создания/обновления: 2026-03-12 18:37:08
# --------------------------------------------
# Путь к Flask API
$api = "C:\Development GPTMEAi\scripts\api_gui_integration.py"

# Создаем резервную копию текущего API
Copy-Item $api "$api.bak" -Force

# Новый контент для api_gui_integration.py
$api_content = @"
from flask import Flask, request, jsonify
from flask_cors import CORS
from scripts.full_db_integration import agent  # <-- используем существующий объект агента

app = Flask(__name__)
CORS(app)  # включаем CORS один раз

@app.route('/add_fact', methods=['POST'])
def add_fact():
    try:
        data = request.json
        # Используем существующий метод add_fact объекта agent
        agent.add_fact(data)
        return jsonify({"memory_count": len(agent.retrieval.vectors), "status": "fact added"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_memory', methods=['GET'])
def get_memory():
    try:
        # Возвращаем список фактов
        facts = [{"id": f["id"], "content": f["content"], "importance": f.get("importance",0)} for f in agent.retrieval.vectors]
        return jsonify(facts)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(port=5000)
"@

# Перезаписываем api_gui_integration.py
$api_content | Set-Content $api -Encoding UTF8

# Завершаем процессы на порту 5000, если есть
$p = Get-NetTCPConnection -LocalPort 5000 -State Listen | ForEach-Object { $_.OwningProcess }
if ($p) { Stop-Process -Id $p -Force }

# Запуск Flask сервера в новом процессе
Start-Process -NoNewWindow python -ArgumentList "`"$api`""

Write-Output "Flask server с исправленным API запущен на http://127.0.0.1:5000"
