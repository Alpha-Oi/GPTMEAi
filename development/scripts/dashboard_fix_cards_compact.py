from pathlib import Path

html_file = Path(r"C:\Development GPTMEAi\dashboard\index.html")
text = html_file.read_text(encoding="utf-8")

text = text.replace("max-width:900px;", "max-width:640px;")
text = text.replace(
    '<div id="out" style="margin-top:16px; white-space:normal; max-width:900px;"></div>',
    '<div id="out" style="margin-top:16px; white-space:normal; max-width:640px;"></div>'
)

text = text.replace(
    '<ul>${recent || "<li>-</li>"}</ul>',
    '<ul style="margin:8px 0 0 18px; padding:0;">${recent || "<li>-</li>"}</ul>'
)

text = text.replace(
    '<ul>${top || "<li>-</li>"}</ul>',
    '<ul style="margin:8px 0 0 18px; padding:0;">${top || "<li>-</li>"}</ul>'
)

text = text.replace(
    '<ul>${items || "<li>-</li>"}</ul>',
    '<ul style="margin:8px 0 0 18px; padding:0;">${items || "<li>-</li>"}</ul>'
)

html_file.write_text(text, encoding="utf-8")
print("dashboard cards compact fixed")