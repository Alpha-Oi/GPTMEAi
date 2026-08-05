from pathlib import Path

p = Path(r"C:\Development GPTMEAi\dashboard\index.html")
t = p.read_text(encoding="utf-8")

t = t.replace(
    '.card{border:1px solid #475569;border-radius:10px;padding:12px;margin:0 0 12px;background:#0b1220;max-width:760px}',
    '.card{border:1px solid #334155;border-radius:10px;padding:10px 12px;margin:0 0 10px;background:#0b1220;max-width:760px}'
)

t = t.replace(
    '.small{opacity:.8;font-size:12px}',
    '.small{opacity:.7;font-size:11px;line-height:1.35;margin-top:2px}'
)

t = t.replace(
    '<div><b>[${esc(x.id)}]</b> ${esc(x.text)}</div>',
    '<div style="font-size:16px;line-height:1.35;font-weight:600;margin-bottom:4px;"><span style="opacity:.8">[${esc(x.id)}]</span> ${esc(x.text)}</div>'
)

t = t.replace(
    '<div class="small">importance: ${esc(x.importance)}</div>',
    '<div class="small">importance: ${esc(x.importance)}</div>'
)

t = t.replace(
    '<div class="small">tags: ${x.tags.length ? x.tags.map(esc).join(", ") : "-"}</div>',
    '<div class="small">tags: ${x.tags.length ? x.tags.map(esc).join(" · ") : "-"}</div>'
)

t = t.replace(
    '<div class="small">created_at: ${esc(x.created_at)}</div>',
    '<div class="small">created_at: ${esc(x.created_at)}</div>'
)

p.write_text(t, encoding="utf-8")
print("dashboard cards tuned")