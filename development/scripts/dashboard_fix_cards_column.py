from pathlib import Path
import re

html_file = Path(r"C:\Development GPTMEAi\dashboard\index.html")
text = html_file.read_text(encoding="utf-8")

text = re.sub(
    r'<div id="out" style="[^"]*"></div>',
    '<div id="out" style="margin-top:16px; white-space:normal; max-width:560px; width:560px;"></div>',
    text,
    count=1
)

text = text.replace("max-width:640px;", "max-width:560px;width:560px;")

html_file.write_text(text, encoding="utf-8")
print("dashboard cards column fixed")