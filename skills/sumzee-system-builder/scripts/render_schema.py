#!/usr/bin/env python3
"""Render schema.json as one self-contained HTML page for the owner.

Usage: render_schema.py schema.json --out schema-page.html [--stage draft|built] [--base-url URL]

The page has: what you will be able to see · a map of the tables and links ·
every table with who fills it and its fields · proposed automations · notes.
Language follows business.language (ru / en).
"""
import argparse
import datetime
import html
import json
import os

from common import inverse_fields, load_json, tr

UI = {
    "ru": {
        "title": "Система учёта", "draft": "черновик шаблона", "built": "создана в Airtable",
        "proposal": "проект", "tables_n": "таблиц", "fields_n": "полей",
        "see": "Что вы сможете видеть", "see_sub": "Вопросы, на которые база ответит, как только в ней появятся данные.",
        "map": "Карта системы", "map_sub": "Блоки по смыслу и связи между таблицами. Стрелка ведёт от «многих» к «одному»: много оплат → один клиент. Наведите на таблицу, чтобы увидеть её связи.",
        "tables": "Таблицы", "who": "Кто вносит", "fields": "Поля", "computed": "считается само",
        "required": "обязательно", "links_to": "связана с", "auto": "Автоматизации, которые предлагаем",
        "auto_sub": "Коннектор создаёт их выключенными. Включите, когда проверите.",
        "notes": "Важно знать", "todo": "Что стоит доделать", "todo_sub": "Это то, что Sumzee делает под ключ.",
        "book": "Обсудить с Sumzee", "records": "записей в год", "from": "Источник",
        "open_base": "Открыть базу в Airtable", "made": "Схема собрана",
        "types": {"singleLineText": "текст", "multilineText": "длинный текст", "email": "email", "url": "ссылка",
                  "phoneNumber": "телефон", "number": "число", "percent": "процент", "currency": "деньги",
                  "date": "дата", "dateTime": "дата и время", "checkbox": "галочка", "singleSelect": "выбор из списка",
                  "multipleSelects": "несколько из списка", "autoNumber": "номер", "multipleAttachments": "файлы",
                  "singleCollaborator": "человек", "createdTime": "дата создания", "lookup": "подтягивается",
                  "rollup": "сумма по связи", "count": "количество", "formula": "формула"},
    },
    "en": {
        "title": "Operations system", "draft": "template draft", "built": "built in Airtable",
        "proposal": "proposal", "tables_n": "tables", "fields_n": "fields",
        "see": "What you will be able to see", "see_sub": "Questions the base answers as soon as data is in it.",
        "map": "System map", "map_sub": "Blocks by meaning and the links between tables. An arrow goes from 'many' to 'one': many payments → one client. Hover a table to see its links.",
        "tables": "Tables", "who": "Who fills it", "fields": "Fields", "computed": "computed",
        "required": "required", "links_to": "linked to", "auto": "Automations we suggest",
        "auto_sub": "The connector creates them switched off. Turn them on once you've checked them.",
        "notes": "Good to know", "todo": "Worth finishing", "todo_sub": "This is what Sumzee sets up for you.",
        "book": "Talk to Sumzee", "records": "records a year", "from": "Source",
        "open_base": "Open the base in Airtable", "made": "Schema built",
        "types": {"singleLineText": "text", "multilineText": "long text", "email": "email", "url": "link",
                  "phoneNumber": "phone", "number": "number", "percent": "percent", "currency": "money",
                  "date": "date", "dateTime": "date & time", "checkbox": "checkbox", "singleSelect": "single choice",
                  "multipleSelects": "multiple choice", "autoNumber": "number (auto)", "multipleAttachments": "files",
                  "singleCollaborator": "person", "createdTime": "created", "lookup": "pulled in",
                  "rollup": "total via link", "count": "count", "formula": "formula"},
    },
}

GROUP_COLORS = ["--g1", "--g2", "--g3", "--g4", "--g5", "--g6"]


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def layout(schema):
    """Positions of table cards in the SVG map: one column per group."""
    groups = [g for g in schema["groups"] if any(t["group"] == g["id"] for t in schema["tables"])]
    n = max(1, len(groups))
    W, pad, gap = 1000, 24, 56
    colw = (W - 2 * pad - gap * (n - 1)) / n
    cw, ch, vgap, top = min(colw, 210), 54, 26, 70
    pos, heads = {}, []
    maxy = 0
    for i, g in enumerate(groups):
        x0 = pad + i * (colw + gap)
        cx = x0 + (colw - cw) / 2
        heads.append((g, x0, colw, i))
        y = top
        for t in [t for t in schema["tables"] if t["group"] == g["id"]]:
            pos[t["name"]] = (cx, y, cw, ch, i)
            y += ch + vgap
        maxy = max(maxy, y)
    return W, maxy + 10, pos, heads


def svg_map(schema, lang):
    W, H, pos, heads = layout(schema)
    tables = {t["name"]: t for t in schema["tables"]}
    parts = [f'<svg viewBox="0 0 {W} {H:.0f}" role="img" aria-label="{esc(UI[lang]["map"])}" class="map">',
             '<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
             'orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="arrowhead"/></marker></defs>']
    for g, x0, colw, i in heads:
        color = GROUP_COLORS[i % len(GROUP_COLORS)]
        parts.append(f'<rect x="{x0:.1f}" y="16" width="{colw:.1f}" height="{H - 24:.0f}" rx="12" '
                     f'class="lane" style="--c:var({color})"/>')
        parts.append(f'<text x="{x0 + colw / 2:.1f}" y="44" class="lane-title" style="--c:var({color})">'
                     f'{esc(g["label"])}</text>')
    edges = []
    ncols = len(heads)
    cols = {i: (x0, colw) for g, x0, colw, i in heads}
    # every column has the same row grid, so the gaps between rows are free corridors
    ys = sorted({p[1] for p in pos.values()})
    ch = next(iter(pos.values()))[3] if pos else 54
    vgap = (ys[1] - ys[0] - ch) if len(ys) > 1 else 26
    corridors = [ys[0] - vgap / 2] + [y + ch + vgap / 2 for y in ys]
    lane_use, corr_use = {}, {}

    def lane_x(col, side):
        """x of the gutter just left (-1) or right (+1) of a column, offset per edge."""
        x0, cw_ = cols[col]
        key = (col, side)
        k = lane_use.get(key, 0)
        lane_use[key] = k + 1
        base = x0 - 14 if side < 0 else x0 + cw_ + 14
        return base + side * 6 * k

    def corridor_y(y_from, y_to):
        mid = (y_from + y_to) / 2
        c = min(corridors, key=lambda c: abs(c - mid))
        k = corr_use.get(c, 0)
        corr_use[c] = k + 1
        return c + (k % 3 - 1) * 5

    def poly(points):
        return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in points)

    for t in schema["tables"]:
        for f in t["fields"]:
            if f.get("type") != "link" or t["name"] not in pos or f["to"] not in pos:
                continue
            ax, ay, aw, ah, ai = pos[t["name"]]
            bx, by, bw, bh, bi = pos[f["to"]]
            y1, y2 = ay + ah / 2, by + bh / 2
            if ai == bi:
                side = 1 if ai < ncols - 1 else -1
                x1 = ax + aw if side > 0 else ax
                x2 = bx + bw + 2 if side > 0 else bx - 2
                gx = lane_x(ai, side)
                d = poly([(x1, y1), (gx, y1), (gx, y2), (x2, y2)])
            elif abs(ai - bi) == 1:
                x1, x2 = (ax + aw, bx - 2) if ai < bi else (ax, bx + bw + 2)
                mx = (x1 + x2) / 2
                d = f"M{x1:.1f} {y1:.1f} C{mx:.1f} {y1:.1f} {mx:.1f} {y2:.1f} {x2:.1f} {y2:.1f}"
            else:
                right = ai < bi
                x1 = ax + aw if right else ax
                x2 = bx - 2 if right else bx + bw + 2
                g1 = lane_x(ai, 1 if right else -1)
                g2 = lane_x(bi, -1 if right else 1)
                cy = corridor_y(y1, y2)
                d = poly([(x1, y1), (g1, y1), (g1, cy), (g2, cy), (g2, y2), (x2, y2)])
            title = f'{tables[t["name"]]["label"]} → {tables[f["to"]]["label"]}'
            edges.append(f'<path d="{d}" class="edge" data-a="{esc(t["name"])}" data-b="{esc(f["to"])}" '
                         f'marker-end="url(#arr)"><title>{esc(title)}</title></path>')
    parts.append('<g class="edges">' + "".join(edges) + "</g>")
    for t in schema["tables"]:
        if t["name"] not in pos:
            continue
        x, y, w, h, i = pos[t["name"]]
        color = GROUP_COLORS[i % len(GROUP_COLORS)]
        label = t.get("label") or t["name"]
        sub = t["name"] if t["name"] != label else f'{len(t["fields"])} {UI[lang]["fields_n"]}'
        parts.append(
            f'<g class="node" data-t="{esc(t["name"])}" tabindex="0" style="--c:var({color})">'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h}" rx="10"/>'
            f'<text x="{x + w / 2:.1f}" y="{y + 23:.1f}" class="n1">{esc(label)}</text>'
            f'<text x="{x + w / 2:.1f}" y="{y + 41:.1f}" class="n2">{esc(sub)}</text></g>')
    parts.append("</svg>")
    return "".join(parts)


def field_row(f, tables, lang):
    u = UI[lang]
    ft = f.get("type")
    if ft == "link":
        tlabel = tables.get(f["to"], {}).get("label", f["to"])
        kind = f"→ {esc(tlabel)}"
        cls = "link"
    else:
        kind = esc(u["types"].get(ft, ft))
        cls = "calc" if ft in ("lookup", "rollup", "count", "formula", "createdTime") else ""
    badges = ""
    if f.get("required"):
        badges += f'<span class="badge req">{u["required"]}</span>'
    if cls == "calc":
        badges += f'<span class="badge calc">{u["computed"]}</span>'
    choices = ""
    if f.get("choices"):
        choices = '<div class="choices">' + " · ".join(esc(c) for c in f["choices"]) + "</div>"
    desc = f'<div class="fdesc">{esc(f.get("description"))}</div>' if f.get("description") else ""
    return (f'<li><div class="frow"><span class="fname">{esc(f["name"])}</span>'
            f'<span class="ftype {cls}">{kind}</span>{badges}</div>{desc}{choices}</li>')


def render(schema, stage="draft", base_url=""):
    b = schema.get("business", {})
    lang = b.get("language", "ru") if b.get("language") in UI else "en"
    u = UI[lang]
    tables = {t["name"]: t for t in schema["tables"]}
    inv = inverse_fields(schema)
    n_fields = sum(len(t["fields"]) for t in schema["tables"])
    name = b.get("name") or ""
    title = f'{u["title"]}{" — " + name if name else ""}'
    status = u["built"] if stage == "built" else (u["draft"] if b.get("template_status") == "draft" else u["proposal"])

    q_html = []
    for q in schema.get("questions", []):
        chips = "".join(f'<span class="chip">{esc(tables[t]["label"])}</span>' for t in q.get("tables", []) if t in tables)
        q_html.append(f'<div class="q"><div class="qt">{esc(q["text"])}</div><div class="chips">{chips}</div></div>')

    groups_html = []
    for gi, g in enumerate(schema["groups"]):
        ts = [t for t in schema["tables"] if t["group"] == g["id"]]
        if not ts:
            continue
        cards = []
        for t in ts:
            links = sorted({tables[f["to"]]["label"] for f in t["fields"] if f.get("type") == "link" and f["to"] in tables}
                           | {tables[i["from_table"]]["label"] for i in inv.get(t["name"], []) if i["from_table"] in tables})
            rec = f'<span class="muted"> · ~{t["estimated_records"]} {u["records"]}</span>' if t.get("estimated_records") else ""
            fields = "".join(field_row(f, tables, lang) for f in t["fields"])
            cards.append(
                f'<article class="tcard" id="t-{esc(t["name"])}" style="--c:var({GROUP_COLORS[gi % len(GROUP_COLORS)]})">'
                f'<header><h3>{esc(t.get("label") or t["name"])}</h3>'
                f'<span class="tech">{esc(t["name"])}</span></header>'
                f'<p>{esc(t.get("description"))}</p>'
                f'<p class="who"><b>{u["who"]}:</b> {esc(t.get("entered_by"))}{rec}</p>'
                + (f'<p class="links"><b>{u["links_to"]}:</b> {esc(", ".join(links))}</p>' if links else "")
                + f'<details><summary>{u["fields"]} · {len(t["fields"])}</summary><ul class="fields">{fields}</ul></details>'
                f'</article>')
        groups_html.append(f'<section class="group"><h3 class="gtitle" style="--c:var({GROUP_COLORS[gi % len(GROUP_COLORS)]})">'
                           f'{esc(g["label"])}</h3><div class="tgrid">{"".join(cards)}</div></section>')

    auto_html = ""
    if schema.get("automations"):
        items = "".join(f'<li><b>{esc(a.get("label"))}</b><br><span class="muted">{esc(a.get("why"))}</span></li>'
                        for a in schema["automations"])
        auto_html = f'<section><h2>{u["auto"]}</h2><p class="sub">{u["auto_sub"]}</p><ul class="plain">{items}</ul></section>'

    notes = schema.get("notes_for_team", []) if b.get("mode") == "sumzee" else \
        [n for n in schema.get("notes_for_team", []) if "1 000" in str(n) or "1,000" in str(n)]
    notes_html = ""
    if notes:
        notes_html = f'<section><h2>{u["notes"]}</h2><ul class="plain">' + "".join(f"<li>{esc(n)}</li>" for n in notes) + "</ul></section>"

    todo_html = ""
    if stage == "built" and schema.get("todo_for_sumzee") and b.get("mode") != "sumzee":
        book = schema.get("booking_url", "")
        items = "".join(f"<li>{esc(t)}</li>" for t in schema["todo_for_sumzee"])
        btn = f'<a class="btn" href="{esc(book)}" target="_blank" rel="noopener">{u["book"]}</a>' if book else ""
        todo_html = f'<section class="todo"><h2>{u["todo"]}</h2><p class="sub">{u["todo_sub"]}</p><ul class="plain">{items}</ul>{btn}</section>'

    open_btn = f'<a class="btn ghost" href="{esc(base_url)}" target="_blank" rel="noopener">{u["open_base"]}</a>' if base_url else ""
    today = datetime.date.today().strftime("%d.%m.%Y" if lang == "ru" else "%d %b %Y")

    return TEMPLATE.format(
        lang=lang, title=esc(title), css=CSS, js=JS, status=esc(status),
        stats=f'{len(tables)} {u["tables_n"]} · {n_fields} {u["fields_n"]}',
        see=u["see"], see_sub=u["see_sub"], questions="".join(q_html),
        map=u["map"], map_sub=u["map_sub"], svg=svg_map(schema, lang),
        tables_h=u["tables"], groups="".join(groups_html),
        auto=auto_html, notes=notes_html, todo=todo_html, open_btn=open_btn,
        footer=f'{u["made"]} {today} · Sumzee',
    )


TEMPLATE = """<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{css}</style></head>
<body><main>
<header class="top"><div class="eyebrow">Sumzee · <span class="status">{status}</span></div>
<h1>{title}</h1><p class="stats">{stats}</p>{open_btn}</header>
<section><h2>{see}</h2><p class="sub">{see_sub}</p><div class="qgrid">{questions}</div></section>
<section><h2>{map}</h2><p class="sub">{map_sub}</p><div class="mapwrap">{svg}</div></section>
<section><h2>{tables_h}</h2>{groups}</section>
{auto}{notes}{todo}
<footer>{footer}</footer>
</main><script>{js}</script></body></html>"""

CSS = """
:root{--bg:#f7f6f2;--card:#fff;--ink:#1d1d1b;--muted:#6b6a64;--line:#e4e1d8;--accent:#2f5bea;
--g1:#2f5bea;--g2:#0f9d76;--g3:#c2410c;--g4:#8b3fd9;--g5:#b4235a;--g6:#0e7490;--edge:#a9a69c;--edge-on:#1d1d1b}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#151514;--card:#1f1f1d;--ink:#f1efe8;
--muted:#a3a197;--line:#34332f;--accent:#7b9bff;--g1:#7b9bff;--g2:#3ccf9f;--g3:#f08a4b;--g4:#b98af0;--g5:#ef6f9d;--g6:#4cc3dc;
--edge:#5c5a53;--edge-on:#f1efe8}}
:root[data-theme="dark"]{--bg:#151514;--card:#1f1f1d;--ink:#f1efe8;--muted:#a3a197;--line:#34332f;--accent:#7b9bff;
--g1:#7b9bff;--g2:#3ccf9f;--g3:#f08a4b;--g4:#b98af0;--g5:#ef6f9d;--g6:#4cc3dc;--edge:#5c5a53;--edge-on:#f1efe8}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink)}
body{font:15px/1.5 Manrope,system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1080px;margin:0 auto;padding:40px 16px 64px}
h1{font-size:34px;line-height:1.15;margin:6px 0 4px;letter-spacing:-.02em}
h2{font-size:21px;margin:0 0 4px;letter-spacing:-.01em}h3{margin:0;font-size:16px}
section{margin-top:44px}.sub{color:var(--muted);margin:0 0 16px}.muted{color:var(--muted)}
.eyebrow{font-size:13px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
.status{color:var(--accent)}.stats{color:var(--muted);margin:0}
.btn{display:inline-block;margin-top:16px;padding:10px 16px;border-radius:10px;background:var(--accent);color:#fff;
text-decoration:none;font-weight:600}.btn.ghost{background:transparent;color:var(--accent);border:1.5px solid var(--accent)}
.qgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.q{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px}
.qt{font-weight:600;font-size:16px;line-height:1.35}.chips{margin-top:10px;display:flex;flex-wrap:wrap;gap:6px}
.chip{font-size:12px;padding:2px 8px;border-radius:99px;background:color-mix(in srgb,var(--accent) 12%,transparent);color:var(--ink)}
.mapwrap{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:8px;overflow-x:auto}
.map{display:block;width:100%;min-width:640px;height:auto}
.lane{fill:color-mix(in srgb,var(--c) 6%,transparent);stroke:color-mix(in srgb,var(--c) 25%,transparent)}
.lane-title{fill:var(--c);font-weight:700;font-size:15px;text-anchor:middle}
.node rect{fill:var(--card);stroke:var(--c);stroke-width:1.5}.node{cursor:pointer;outline:none}
.node .n1{fill:var(--ink);font-weight:700;font-size:14px;text-anchor:middle}
.node .n2{fill:var(--muted);font-size:11.5px;text-anchor:middle}
.edge{fill:none;stroke:var(--edge);stroke-width:1.4;stroke-linejoin:round;transition:stroke .15s,opacity .15s}.arrowhead{fill:var(--edge)}
.map.focus .edge{opacity:.12}.map.focus .edge.on{opacity:1;stroke:var(--edge-on);stroke-width:2}
.map.focus .node{opacity:.35}.map.focus .node.on{opacity:1}.map.focus .node.on rect{stroke-width:2.5}
.group{margin-top:22px}.gtitle{color:var(--c);font-size:14px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px}
.tgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.tcard{background:var(--card);border:1px solid var(--line);border-top:3px solid var(--c);border-radius:14px;padding:16px}
.tcard header{display:flex;align-items:baseline;justify-content:space-between;gap:8px}
.tech{font-size:12px;color:var(--muted);font-family:ui-monospace,Menlo,monospace}
.tcard p{margin:8px 0 0}.who,.links{font-size:14px}
details{margin-top:12px;border-top:1px solid var(--line);padding-top:8px}summary{cursor:pointer;font-weight:600;font-size:14px}
.fields{list-style:none;padding:0;margin:8px 0 0}.fields li{padding:7px 0;border-bottom:1px dashed var(--line)}
.frow{display:flex;flex-wrap:wrap;align-items:center;gap:6px}.fname{font-weight:600;font-size:14px}
.ftype{font-size:12px;color:var(--muted)}.ftype.link{color:var(--accent);font-weight:600}
.badge{font-size:11px;padding:1px 7px;border-radius:99px;border:1px solid var(--line);color:var(--muted)}
.badge.req{border-color:color-mix(in srgb,var(--g3) 50%,transparent);color:var(--g3)}
.fdesc{font-size:13px;color:var(--muted);margin-top:2px}.choices{font-size:12px;color:var(--muted);margin-top:2px}
.plain{padding-left:18px}.plain li{margin:6px 0}
.todo{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px}
footer{margin-top:56px;color:var(--muted);font-size:13px}
@media (max-width:600px){h1{font-size:27px}main{padding-top:24px}}
"""

JS = """
(function(){var m=document.querySelector('.map');if(!m)return;
function on(t){m.classList.add('focus');var keep={};keep[t]=1;
m.querySelectorAll('.edge').forEach(function(e){var a=e.dataset.a,b=e.dataset.b,hit=a===t||b===t;
e.classList.toggle('on',hit);if(hit){keep[a]=1;keep[b]=1;}});
m.querySelectorAll('.node').forEach(function(n){n.classList.toggle('on',!!keep[n.dataset.t]);});}
function off(){m.classList.remove('focus');}
m.querySelectorAll('.node').forEach(function(n){n.addEventListener('mouseenter',function(){on(n.dataset.t)});
n.addEventListener('focus',function(){on(n.dataset.t)});n.addEventListener('mouseleave',off);n.addEventListener('blur',off);
n.addEventListener('click',function(){var el=document.getElementById('t-'+n.dataset.t);if(el){el.scrollIntoView({behavior:'smooth',block:'start'});
var d=el.querySelector('details');if(d)d.open=true;}});});})();
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("schema")
    ap.add_argument("--out", required=True)
    ap.add_argument("--stage", default="draft", choices=["draft", "built"])
    ap.add_argument("--base-url", default="")
    a = ap.parse_args()
    schema = load_json(a.schema)
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
    if os.path.exists(cfg_path) and not schema.get("booking_url"):
        schema["booking_url"] = load_json(cfg_path).get("booking_url", "")
    out = render(schema, a.stage, a.base_url)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"wrote {a.out} ({len(out) // 1024} KB)")


if __name__ == "__main__":
    main()
