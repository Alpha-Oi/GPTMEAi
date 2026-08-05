# 2026-04-28 - Venv site-packages corruption inventory

## Что диагностировано

- project `venv` Python: `3.14.3`
- project runtime imports previously checked as ok: `ai_os.runtime`, `scripts.api_server`
- `pip` import and `python -m pip` are broken
- broken `pip` error points to corrupted injected header in `venv\Lib\site-packages\pip\__init__.py`
- damage appears broader than `pip`: third-party `site-packages` may also contain corrupted injected headers
- inventory was collected from `*.dist-info` metadata without running `pip`

## Known dist-info inventory

- `bidict 0.23.1`
- `blinker 1.9.0`
- `certifi 2026.2.25`
- `charset-normalizer 3.4.5`
- `click 8.3.1`
- `colorama 0.4.6`
- `dnspython 2.8.0`
- `eventlet 0.40.4`
- `Flask 3.1.3`
- `flask-cors 6.0.2`
- `Flask-SocketIO 5.6.1`
- `greenlet 3.3.2`
- `h11 0.16.0`
- `idna 3.11`
- `itsdangerous 2.2.0`
- `Jinja2 3.1.6`
- `MarkupSafe 3.0.3`
- `pip 26.0.1`
- `psutil 7.2.2`
- `python-engineio 4.13.1`
- `python-socketio 5.16.1`
- `PyYAML 6.0.3`
- `requests 2.32.5`
- `simple-websocket 1.1.0`
- `urllib3 2.6.3`
- `Werkzeug 3.1.6`
- `wsproto 1.3.2`

## Repair posture

- targeted pip-only repair is not recommended because broader `site-packages` damage may remain
- recommended future repair direction: side-by-side clean replacement `venv`, verified before replacing the current `venv`
- `AGENTS.md` now protects `venv/` and `venv/Lib/site-packages/` as no-edit zones
