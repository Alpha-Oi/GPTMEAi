from pathlib import Path

html_file = Path(r"C:\Development GPTMEAi\dashboard\index.html")
text = html_file.read_text(encoding="utf-8")

text = text.replace(
    '<div id="out" style="margin-top:16px; white-space:normal;"></div>',
    '<div id="out" style="margin-top:16px; white-space:normal; max-width:900px;"></div>'
)

text = text.replace(
    'border:1px solid #475569;padding:12px;border-radius:8px;margin-bottom:12px;',
    'border:1px solid #475569;padding:12px;border-radius:8px;margin-bottom:12px;max-width:900px;'
)

text = text.replace(
    'border:1px solid #475569;padding:12px;border-radius:8px;',
    'border:1px solid #475569;padding:12px;border-radius:8px;max-width:900px;'
)

html_file.write_text(text, encoding="utf-8")
print("dashboard cards width fixed")