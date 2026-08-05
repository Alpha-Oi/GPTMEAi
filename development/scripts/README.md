# Development Scripts

Сюда должны постепенно переноситься временные, одноразовые и сервисные скрипты, которые не относятся к официальному runtime проекта.

Официальными entrypoint-файлами пока считаются:

- [`run_ai_os.py`](/D:/Development%20GPTMEAi/run_ai_os.py)
- [`run_ai_os.ps1`](/D:/Development%20GPTMEAi/run_ai_os.ps1)
- [`scripts/api_server.py`](/D:/Development%20GPTMEAi/scripts/api_server.py)

## Предпочтение по служебной автоматизации

Для временных dev-операций по умолчанию лучше использовать Python-скрипты из этой папки, а не одноразовые PowerShell-команды.

Это особенно относится к:

- smoke-проверкам
- cleanup временных JSON/state-файлов
- служебным миграциям внутри workspace

Базовый cleanup helper:

- [`cleanup_tmp_artifacts.py`](/D:/Development%20GPTMEAi/development/scripts/cleanup_tmp_artifacts.py)

Базовый recovery smoke helper:

- [`smoke_recovery_workflow.py`](/D:/Development%20GPTMEAi/development/scripts/smoke_recovery_workflow.py)

Recovery remediation smoke helper:

- [`smoke_recovery_remediation.py`](/D:/Development%20GPTMEAi/development/scripts/smoke_recovery_remediation.py)

Recovery demo seed helper:

- [`seed_recovery_demo.py`](/D:/Development%20GPTMEAi/development/scripts/seed_recovery_demo.py)
