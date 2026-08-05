from pathlib import Path

html_file = Path(r"C:\Development GPTMEAi\dashboard\index.html")
text = html_file.read_text(encoding="utf-8")

text = text.replace('join("\\\\n")', 'join("\\n")')
text = text.replace('].join("\\\\n");', '].join("\\n");')

html_file.write_text(text, encoding="utf-8")
print("dashboard newlines fixed")