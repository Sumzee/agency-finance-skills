#!/usr/bin/env python3
"""Step 3 — turn results.json + narrative.json into a single, self-contained
HTML dashboard (no external scripts; opens offline in any browser).

Usage:
    python build_dashboard.py results.json narrative.json --out profit-dashboard.html [--config ../config.json]
"""
from __future__ import annotations

import argparse
import html
import json
import math
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
import sys  # noqa: E402
sys.path.insert(0, str(HERE))
import sections  # noqa: E402

# ------------------------------------------------------------------ text ----

L = {
    "en": {
        "title": "Profit overview", "period": "Period", "revenue": "Revenue", "expenses": "Expenses",
        "profit": "Profit", "margin": "Margin", "vs_prev": "vs previous {n} mo", "unpaid": "Unpaid invoices",
        "overdue": "overdue", "over_time": "Month by month", "legend_rev": "Revenue", "legend_exp": "Expenses",
        "legend_profit": "Profit", "margin_row": "Margin", "money_goes": "Where the money goes",
        "money_comes": "Where the money comes from", "by_client": "Revenue by client", "by_project": "Revenue by project",
        "by_stream": "Revenue by type", "proj_profit": "Project profitability", "proj_profit_sub": "Contribution = revenue − costs linked to the project (before overheads)",
        "contribution": "Contribution", "team": "Team time", "hours": "hours", "billable": "billable", "utilization": "utilization",
        "insights": "What stands out", "more": "There’s more we could see",
        "more_sub": "These views are possible for your business — they just need a few more pieces of data.",
        "needs": "Needs", "want": "I want this", "cta_title": "Want to unlock these?",
        "cta_text": "We can help you set up the missing data and connect it to the way you already work — so these update on their own.",
        "cta_btn": "Set it up with Sumzee", "cta_email": "Email the brief", "copy": "Copy brief", "copied": "Copied",
        "brief": "Your brief (only this is shared — never your files)", "how": "How this was calculated",
        "sources": "Files used", "footer": "Made with Sumzee Profit Agent", "privacy": "Sumzee never receives your files — this analysis ran inside your own Claude conversation.",
        "others": "Other", "no_selection": "(no specific view selected)", "top3": "Top 3 clients",
        "per_hour": "revenue / hour", "cash": "Cash in the bank",
    },
    "ru": {
        "title": "Прибыль бизнеса", "period": "Период", "revenue": "Выручка", "expenses": "Расходы",
        "profit": "Прибыль", "margin": "Маржа", "vs_prev": "к предыдущим {n} мес.", "unpaid": "Неоплаченные счета",
        "overdue": "просрочено", "over_time": "По месяцам", "legend_rev": "Выручка", "legend_exp": "Расходы",
        "legend_profit": "Прибыль", "margin_row": "Маржа", "money_goes": "Куда уходят деньги",
        "money_comes": "Откуда приходят деньги", "by_client": "Выручка по клиентам", "by_project": "Выручка по проектам",
        "by_stream": "Выручка по направлениям", "proj_profit": "Прибыльность проектов", "proj_profit_sub": "Вклад = выручка − расходы, привязанные к проекту (без накладных)",
        "contribution": "Вклад", "team": "Время команды", "hours": "ч", "billable": "оплачиваемых", "utilization": "загрузка",
        "insights": "Что бросается в глаза", "more": "Что ещё можно было бы увидеть",
        "more_sub": "Эти срезы возможны для вашего бизнеса — просто для них нужно чуть больше данных.",
        "needs": "Нужно", "want": "Хочу это", "cta_title": "Хотите это разблокировать?",
        "cta_text": "Поможем настроить недостающие данные и встроить их в то, как вы уже работаете, — чтобы всё обновлялось само.",
        "cta_btn": "Настроить с Sumzee", "cta_email": "Отправить бриф", "copy": "Скопировать бриф", "copied": "Скопировано",
        "brief": "Ваш бриф (передаётся только он — не ваши файлы)", "how": "Как считали",
        "sources": "Использованные файлы", "footer": "Сделано в Sumzee Profit Agent", "privacy": "Sumzee не получает ваши файлы — анализ прошёл внутри вашего собственного чата с Claude.",
        "others": "Прочее", "no_selection": "(конкретный срез не выбран)", "top3": "Топ-3 клиента",
        "per_hour": "выручка / час", "cash": "На счёте",
    },
}

LOCKED_DEFAULTS = {
    "en": {
        "project_profitability": ("Profitability by project", "See which projects actually make money — not just which bring revenue."),
        "client_profitability": ("Client profitability", "See which clients bring profit, and which take more than they give."),
        "cash_forecast": ("3-month cash forecast", "Know how much cash you’ll have in the coming months — before it becomes a surprise."),
        "team_utilization": ("Team utilization vs. profit", "Understand whether a busier team actually means more profit."),
        "effective_hourly_rate": ("Real hourly rate by project", "What each project really pays per hour of your team’s time."),
        "revenue_by_service": ("Revenue by service", "Which of your offers actually carries the business."),
        "pipeline_forecast": ("Revenue forecast from pipeline", "What next quarter looks like, based on deals in progress."),
        "monthly_trends": ("Profit month by month", "See how profit and margin move over time."),
        "cost_breakdown": ("Where the money goes", "A clear breakdown of costs by category."),
        "revenue_by_client": ("Revenue by client", "Who your business really depends on."),
        "profit_and_margin": ("Real profit and margin", "What actually stays with you after all costs."),
    },
    "ru": {
        "project_profitability": ("Прибыльность по проектам", "Какие проекты реально зарабатывают, а не просто приносят выручку."),
        "client_profitability": ("Прибыльность клиентов", "Какие клиенты приносят прибыль, а какие забирают больше, чем дают."),
        "cash_forecast": ("Прогноз денег на 3 месяца", "Сколько денег будет в ближайшие месяцы — до того, как это станет сюрпризом."),
        "team_utilization": ("Загрузка команды и прибыль", "Правда ли, что загруженная команда = больше прибыли."),
        "effective_hourly_rate": ("Реальная ставка в час по проектам", "Сколько на самом деле платит каждый проект за час работы команды."),
        "revenue_by_service": ("Выручка по услугам", "Какое из ваших предложений на самом деле тянет бизнес."),
        "pipeline_forecast": ("Прогноз выручки по воронке", "Каким будет следующий квартал, исходя из сделок в работе."),
        "monthly_trends": ("Прибыль по месяцам", "Как меняются прибыль и маржа со временем."),
        "cost_breakdown": ("Куда уходят деньги", "Расходы по категориям."),
        "revenue_by_client": ("Выручка по клиентам", "От кого бизнес на самом деле зависит."),
        "profit_and_margin": ("Реальная прибыль и маржа", "Сколько на самом деле остаётся после всех расходов."),
    },
}

MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "ru": ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"],
}
SYMBOL = {"EUR": "€", "USD": "$", "GBP": "£", "ILS": "₪", "RUB": "₽", "UAH": "₴", "PLN": "zł", "KZT": "₸", "GEL": "₾", "TRY": "₺", "INR": "₹", "JPY": "¥"}


def esc(s):
    return html.escape(str(s if s is not None else ""))


class Fmt:
    def __init__(self, currency, lang):
        self.cur = currency
        self.sym = SYMBOL.get(currency, currency + " ")
        self.lang = lang
        self.after = lang == "ru" or currency in ("PLN",)

    def num(self, v, dec=0):
        if v is None:
            return "—"
        s = f"{abs(v):,.{dec}f}"
        if self.lang == "ru":
            s = s.replace(",", " ").replace(".", ",")
        return ("−" if v < 0 else "") + s

    def money(self, v, compact=False):
        if v is None:
            return "—"
        if compact or abs(v) >= 1_000_000:
            a = abs(v)
            if a >= 1_000_000:
                body = f"{a / 1_000_000:.{1 if compact else 2}f}".rstrip("0").rstrip(".") + (" млн" if self.lang == "ru" else "M")
            elif a >= 10_000:
                body = f"{a / 1000:.0f}" + (" тыс" if self.lang == "ru" else "k")
            elif a >= 1000:
                body = f"{a / 1000:.1f}".rstrip("0").rstrip(".") + (" тыс" if self.lang == "ru" else "k")
            else:
                body = f"{a:.0f}"
            if self.lang == "ru":
                body = body.replace(".", ",")
            sign = "−" if v < 0 else ""
        else:
            body, sign = self.num(abs(v)), ("−" if v < 0 else "")
        return f"{sign}{body} {self.sym}" if self.after else f"{sign}{self.sym}{body}"

    def pct(self, v, dec=1, signed=False):
        if v is None:
            return "—"
        s = f"{v:+.{dec}f}" if signed else f"{v:.{dec}f}"
        s = s.replace("-", "−")
        if self.lang == "ru":
            s = s.replace(".", ",")
        return s + "%"


def month_label(mk, lang, with_year=False):
    y, m = mk.split("-")
    s = MONTHS.get(lang, MONTHS["en"])[int(m) - 1]
    return f"{s} {y[2:]}" if with_year else s


# ---------------------------------------------------------------- charts ----

def nice_max(v):
    if v <= 0:
        return 1
    exp = 10 ** math.floor(math.log10(v))
    for m in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if m * exp >= v:
            return m * exp
    return 10 * exp


def monthly_chart(monthly, F, lang):
    W, H, pl, pr, pt, pb = 760, 300, 56, 16, 16, 34
    probe = [F.money(v, compact=True) for v in (max([x["revenue"] or 0 for x in monthly] + [1]), min([x["profit"] or 0 for x in monthly] + [0]))]
    pl = max(pl, 12 + 6.6 * max(len(p) for p in probe))
    n = len(monthly)
    vals = [x["revenue"] or 0 for x in monthly] + [x["expenses"] or 0 for x in monthly]
    profits = [x["profit"] or 0 for x in monthly]
    step = nice_max(max(vals + profits + [1]) / 4)
    top = step * math.ceil(max(vals + profits + [1]) / step)
    bot = min(0, min(profits + [0]))
    if bot < 0:
        bot = -step * math.ceil(-bot / step)
    ticks = int(round((top - bot) / step))
    rng = top - bot
    y = lambda v: pt + (top - v) / rng * (H - pt - pb)
    band = (W - pl - pr) / n
    bw = min(22, band * 0.3)
    out = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="monthly revenue, expenses and profit">']
    for i in range(ticks + 1):
        v = bot + step * i
        yy = y(v)
        out.append(f'<line x1="{pl}" x2="{W - pr}" y1="{yy:.1f}" y2="{yy:.1f}" class="grid{" zero" if abs(v) < 1e-9 else ""}"/>')
        out.append(f'<text x="{pl - 8}" y="{yy + 4:.1f}" class="ax" text-anchor="end">{esc(F.money(v, compact=True))}</text>')
    if bot < 0:
        out.append(f'<line x1="{pl}" x2="{W - pr}" y1="{y(0):.1f}" y2="{y(0):.1f}" class="grid zero"/>')
    pts = []
    show_year = len({m["month"][:4] for m in monthly}) > 1
    for i, m in enumerate(monthly):
        cx = pl + band * i + band / 2
        r, e = m["revenue"] or 0, m["expenses"] or 0
        out.append(f'<rect x="{cx - bw - 1.5:.1f}" y="{y(r):.1f}" width="{bw:.1f}" height="{max(0, y(0) - y(r)):.1f}" rx="3" class="b-rev"><title>{esc(F.money(r))}</title></rect>')
        out.append(f'<rect x="{cx + 1.5:.1f}" y="{y(e):.1f}" width="{bw:.1f}" height="{max(0, y(0) - y(e)):.1f}" rx="3" class="b-exp"><title>{esc(F.money(e))}</title></rect>')
        if n <= 14 or i % 2 == 0:
            out.append(f'<text x="{cx:.1f}" y="{H - 12}" class="ax" text-anchor="middle">{esc(month_label(m["month"], lang, show_year))}</text>')
        if m["profit"] is not None:
            pts.append((cx, y(m["profit"]), m["profit"]))
    if len(pts) > 1:
        d = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{yy:.1f}" for i, (x, yy, _) in enumerate(pts))
        out.append(f'<path d="{d}" class="l-profit"/>')
    for x, yy, v in pts:
        out.append(f'<circle cx="{x:.1f}" cy="{yy:.1f}" r="4" class="{"d-loss" if v < 0 else "d-profit"}"><title>{esc(F.money(v))}</title></circle>')
    out.append("</svg>")
    return "".join(out)


def hbars(items, F, value_key, label_key="name", share_key="share_pct", top=7, lang="en", other_label="Other", fmt=None):
    fmt = fmt or F.money
    items = list(items)
    if len(items) > top:
        rest = items[top - 1:]
        items = items[:top - 1] + [{label_key: other_label, value_key: sum(x[value_key] or 0 for x in rest),
                                    share_key: sum(x.get(share_key) or 0 for x in rest) if share_key else None, "_other": True}]
    mx = max([abs(x[value_key] or 0) for x in items] + [1])
    rows = []
    for x in items:
        v = x[value_key] or 0
        w = abs(v) / mx * 100
        share = x.get(share_key) if share_key else None
        cls = "neg" if v < 0 else ("other" if x.get("_other") else "")
        rows.append(
            f'<div class="hb {cls}"><div class="hb-l" title="{esc(x[label_key])}">{esc(x[label_key])}</div>'
            f'<div class="hb-t"><div class="hb-f" style="width:{w:.1f}%"></div></div>'
            f'<div class="hb-v">{esc(fmt(v))}{f"<span>{esc(F.pct(share, 0))}</span>" if share is not None else ""}</div></div>')
    return '<div class="hbars">' + "".join(rows) + "</div>"


def ghost_chart(kind, seed):
    rnd = random.Random(seed)
    W, H = 300, 120
    s = [f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" class="ghost" aria-hidden="true"><g filter="url(#blur)">']
    if kind in ("cash_forecast", "pipeline_forecast", "monthly_trends"):
        pts, v = [], 70
        for i in range(10):
            v = max(15, min(105, v + rnd.uniform(-18, 16)))
            pts.append((10 + i * 31, v))
        d = " ".join(f"{'M' if i == 0 else 'L'}{x:.0f},{y:.0f}" for i, (x, y) in enumerate(pts))
        s.append(f'<path d="{d} L{pts[-1][0]:.0f},{H} L10,{H} Z" class="g-area"/><path d="{d}" class="g-line"/>')
    elif kind in ("team_utilization",):
        for i in range(14):
            s.append(f'<circle cx="{rnd.uniform(20, 280):.0f}" cy="{rnd.uniform(15, 105):.0f}" r="{rnd.uniform(5, 11):.0f}" class="g-dot"/>')
    elif kind in ("revenue_by_service", "revenue_by_client"):
        a0 = 0
        for i, share in enumerate([0.38, 0.24, 0.18, 0.12, 0.08]):
            a1 = a0 + share * 2 * math.pi
            x0, y0 = 150 + 48 * math.cos(a0), 60 + 48 * math.sin(a0)
            x1, y1 = 150 + 48 * math.cos(a1), 60 + 48 * math.sin(a1)
            s.append(f'<path d="M150,60 L{x0:.1f},{y0:.1f} A48,48 0 {1 if share > 0.5 else 0},1 {x1:.1f},{y1:.1f} Z" class="g-seg s{i}"/>')
            a0 = a1
    else:
        for i in range(6):
            w = rnd.uniform(60, 260)
            s.append(f'<rect x="10" y="{8 + i * 18}" width="{w:.0f}" height="11" rx="3" class="g-bar {"neg" if rnd.random() < 0.2 else ""}"/>')
    s.append("</g></svg>")
    return "".join(s)


LOCK_SVG = '<svg viewBox="0 0 24 24" class="lock" aria-hidden="true"><rect x="5" y="10.5" width="14" height="10" rx="2.2"/><path d="M8 10.5V7.8a4 4 0 0 1 8 0v2.7" fill="none"/></svg>'


# ------------------------------------------------------------------ brief ---

def brief_base(R, N, lang, shown_missing=None):
    b = R["meta"].get("business", {})
    a = R["availability"]
    k = R["kpis"]
    F = Fmt(R["meta"]["currency"], "en")
    avg = k.get("avg_monthly_revenue")
    def bracket(v):
        if not v:
            return "n/a"
        lo = nice_max(v * 0.8) / 2 if v < 1000 else round(v * 0.8, -3 if v < 100000 else -4)
        hi = round(v * 1.2, -3 if v < 100000 else -4)
        return f"~{F.money(lo, True)}–{F.money(hi, True)} / month"
    have = [n for n, ok in [("revenue", a["revenue"]), ("expenses", a["expenses"]), ("dates", a["dates"]),
                            ("clients", a["revenue_clients"]), ("projects", a["revenue_projects"]),
                            ("expense categories", a["expense_categories"]), ("team hours", a["team_hours"]),
                            ("invoice status", a["invoice_status"])] if ok]
    missing = shown_missing or sorted({m for o in R["opportunities"]["locked"][:3] for m in o["missing"]})
    lines = [
        "Sumzee Profit Agent — brief",
        f"Business: {b.get('name') or '—'} · {b.get('type') or '—'}",
        f"Team: {b.get('team_size') or '—'} · Revenue model: {b.get('revenue_model') or '—'}",
        f"Revenue size: {bracket(avg)}" + (f" · Margin: {k['margin_pct']}%" if k.get("margin_pct") is not None else " · Margin: unknown (no cost data)"),
        f"Period analysed: {R['meta']['period']['start']} – {R['meta']['period']['end']}",
        (f"Data today: {b.get('data_location')} · " if b.get("data_location") else "") + f"Has: {', '.join(have) or '—'}",
        f"Missing: {', '.join(missing) or '—'}",
        f"Dashboard built: {', '.join(R['opportunities']['unlocked']) or '—'}",
    ]
    if R.get("verdict"):
        v = R["verdict"]
        lines.insert(4, f"Model: {R['model']['primary']} · Verdict: {v['verdict']} ({v['confidence']} confidence) · "
                        f"red: {', '.join(v['red']) or '—'} · yellow: {', '.join(v['yellow']) or '—'}")
    if N.get("brief_note"):
        lines.append(f"Owner's goal: {N['brief_note']}")
    return "\n".join(lines)


# ------------------------------------------------------------------ page ----

CSS = """
:root{--bg:#f6f3ee;--card:#fffdfa;--ink:#1d1b18;--muted:#6f6a62;--line:#e6e0d6;--rev:#1f4b43;--exp:#d9cfc0;--profit:#d8643a;
--good:#2f7a5b;--warn:#b5582a;--neutral:#5a6b7a;--accent:#1f4b43;--accent-ink:#fff;--ghost:#cfc6b8;--chip:#efe9df;--neg:#c2462b}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#161513;--card:#1f1d1a;--ink:#f1ece4;--muted:#a39d93;--line:#34302a;
--rev:#7cc3a8;--exp:#4a443b;--profit:#f08a5d;--good:#7cc3a8;--warn:#f0a07a;--neutral:#9fb3c4;--accent:#7cc3a8;--accent-ink:#10201b;--ghost:#4a443b;--chip:#2a2723;--neg:#f07a5d}}
:root[data-theme=dark]{--bg:#161513;--card:#1f1d1a;--ink:#f1ece4;--muted:#a39d93;--line:#34302a;--rev:#7cc3a8;--exp:#4a443b;--profit:#f08a5d;
--good:#7cc3a8;--warn:#f0a07a;--neutral:#9fb3c4;--accent:#7cc3a8;--accent-ink:#10201b;--ghost:#4a443b;--chip:#2a2723;--neg:#f07a5d}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif;font-variant-numeric:tabular-nums}
.wrap{max-width:1080px;margin:0 auto;padding:28px 16px 64px}
.top{display:flex;justify-content:space-between;align-items:center;gap:12px;color:var(--muted);font-size:13px}
.brand{font-weight:700;letter-spacing:.02em;color:var(--ink)}.brand b{color:var(--profit)}
h1{font:600 clamp(26px,4vw,40px)/1.15 Georgia,"Iowan Old Style","Times New Roman",serif;margin:18px 0 6px;letter-spacing:-.01em}
.headline{font-size:clamp(16px,2vw,19px);color:var(--muted);max-width:760px;margin:0 0 22px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px}
.kpi .k{font-size:13px;color:var(--muted)}.kpi .v{font:600 clamp(22px,3vw,32px)/1.2 Georgia,serif;margin-top:4px;white-space:nowrap}
.kpi .d{font-size:12.5px;color:var(--muted);margin-top:4px}.kpi .d .up{color:var(--good)}.kpi .d .down{color:var(--warn)}
.kpi.main{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}.kpi.main .k,.kpi.main .d,.kpi.main .d span{color:inherit;opacity:.85}
.pill{display:inline-flex;gap:6px;align-items:center;margin-top:12px;font-size:13px;background:var(--chip);border-radius:99px;padding:5px 12px;color:var(--muted)}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px;margin-top:16px}
.card h2{font-size:16px;margin:0 0 4px}.card .sub{color:var(--muted);font-size:13px;margin:0 0 12px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}.grid2 .card{margin-top:0}.row{margin-top:16px}
.legend{display:flex;gap:16px;font-size:12.5px;color:var(--muted);margin-bottom:6px;flex-wrap:wrap}.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.chartbox{overflow-x:auto}.chart{width:100%;min-width:540px;height:auto;display:block}.grid{stroke:var(--line);stroke-width:1}.grid.zero{stroke:var(--muted);stroke-opacity:.5}
.ax{fill:var(--muted);font-size:11px}.b-rev{fill:var(--rev)}.b-exp{fill:var(--exp)}.l-profit{fill:none;stroke:var(--profit);stroke-width:2.5;stroke-linejoin:round}
.d-profit{fill:var(--card);stroke:var(--profit);stroke-width:2.5}.d-loss{fill:var(--neg);stroke:var(--neg)}
.mrow{display:flex;gap:4px;margin-top:8px;overflow-x:auto}.mrow div{flex:1;min-width:46px;text-align:center;font-size:12px;color:var(--muted);background:var(--chip);border-radius:8px;padding:4px 2px}
.mrow div b{display:block;color:var(--ink);font-weight:600}.mrow div.neg b{color:var(--neg)}
.hbars{display:flex;flex-direction:column;gap:9px}.hb{display:grid;grid-template-columns:minmax(90px,34%) 1fr auto;gap:10px;align-items:center;font-size:13.5px}
.hb-l{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.hb-t{background:var(--chip);border-radius:6px;height:12px;overflow:hidden}
.hb-f{height:100%;background:var(--rev);border-radius:6px}.hb.neg .hb-f{background:var(--neg)}.hb.other .hb-f{background:var(--ghost)}
.hb-v{white-space:nowrap;text-align:right}.hb-v span{color:var(--muted);margin-left:8px;font-size:12px;display:inline-block;min-width:34px}
.cost .hb-f{background:var(--profit);opacity:.85}
table{width:100%;border-collapse:collapse;font-size:13.5px}th{text-align:left;color:var(--muted);font-weight:500;font-size:12.5px;padding:6px 8px;border-bottom:1px solid var(--line)}
td{padding:8px;border-bottom:1px solid var(--line)}td.n,th.n{text-align:right;white-space:nowrap}td.neg{color:var(--neg)}
.tbl{overflow-x:auto}
.ins{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
.in{border:1px solid var(--line);border-left:4px solid var(--neutral);border-radius:12px;padding:14px 16px;background:var(--card)}
.in.positive{border-left-color:var(--good)}.in.warning{border-left-color:var(--warn)}.in h3{font-size:15px;margin:0 0 4px}.in p{margin:0;color:var(--muted);font-size:14px}
.more{margin-top:28px;border-radius:20px;padding:24px;background:linear-gradient(180deg,var(--card),var(--bg));border:1px dashed var(--ghost)}
.more h2{font:600 clamp(20px,2.6vw,26px)/1.2 Georgia,serif;margin:0 0 4px}.more>.sub{color:var(--muted);margin:0 0 18px}
.locks{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}
@media (min-width:761px){.locks.four{grid-template-columns:1fr 1fr}}
.lk{position:relative;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;display:flex;flex-direction:column;gap:8px;transition:border-color .15s,box-shadow .15s}
.lk.on{border-color:var(--accent);box-shadow:0 0 0 2px var(--accent) inset}
.ghostbox{position:relative;border-radius:10px;background:var(--chip);overflow:hidden}.ghost{width:100%;height:112px;display:block;opacity:.9}
.g-bar,.g-seg,.g-dot,.g-area{fill:var(--ghost)}.g-bar.neg{fill:var(--profit);opacity:.5}.g-line{fill:none;stroke:var(--muted);stroke-width:3}.g-area{opacity:.6}
.g-seg.s1{opacity:.8}.g-seg.s2{opacity:.6}.g-seg.s3{opacity:.45}.g-seg.s4{opacity:.3}
.lock{position:absolute;left:50%;top:50%;width:34px;height:34px;margin:-17px 0 0 -17px;padding:7px;border-radius:50%;background:var(--card);stroke:var(--ink);fill:none;stroke-width:1.8;box-shadow:0 2px 10px rgba(0,0,0,.12)}
.lock rect{fill:var(--ink);stroke:none}
.lk h3{margin:4px 0 0;font-size:15.5px}.lk p{margin:0;color:var(--muted);font-size:13.5px}
.chips{display:flex;flex-wrap:wrap;gap:6px}.chips span{font-size:12px;background:var(--chip);border-radius:99px;padding:3px 9px}
.chips b{font-size:12px;color:var(--muted);font-weight:500;margin-right:2px;align-self:center}
.lk label{display:flex;gap:8px;align-items:center;font-size:13.5px;cursor:pointer;margin-top:auto;padding-top:4px}.lk input{accent-color:var(--accent);width:16px;height:16px}
.cta{margin-top:18px;display:grid;grid-template-columns:1.2fr 1fr;gap:18px;align-items:start;background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px}
.cta h3{margin:0 0 6px;font-size:18px}.cta p{margin:0 0 14px;color:var(--muted)}
.btns{display:flex;flex-wrap:wrap;gap:8px}.btn{appearance:none;border:1px solid var(--accent);background:var(--accent);color:var(--accent-ink);border-radius:10px;padding:10px 16px;font:600 14px/1 inherit;cursor:pointer;text-decoration:none;display:inline-block}
.btn.sec{background:transparent;color:var(--ink);border-color:var(--line)}
pre.brief{white-space:pre-wrap;font:12.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--chip);border-radius:10px;padding:12px;margin:6px 0 0;max-height:260px;overflow:auto}
.small{font-size:12.5px;color:var(--muted)}details summary{cursor:pointer;color:var(--muted);font-size:13.5px}details ul{margin:8px 0 0;padding-left:18px;color:var(--muted);font-size:13px}
footer{margin-top:36px;color:var(--muted);font-size:12.5px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
@media (max-width:760px){.kpis{grid-template-columns:1fr 1fr}.grid2,.cta{grid-template-columns:1fr}.hb{grid-template-columns:minmax(80px,38%) 1fr auto}}
@media print{.btns,.lk label{display:none}body{background:#fff}}
"""

JS = """
(function(){
  var base = JSON.parse(document.getElementById('brief-base').textContent);
  var pre = document.getElementById('brief');
  var cfg = JSON.parse(document.getElementById('cfg').textContent);
  function selected(){ return Array.prototype.slice.call(document.querySelectorAll('.lk input:checked')).map(function(i){return i.getAttribute('data-title')}); }
  function text(){ var s = selected(); return base + '\\nWants to unlock: ' + (s.length ? s.join('; ') : cfg.none); }
  function update(){
    document.querySelectorAll('.lk').forEach(function(c){ c.classList.toggle('on', c.querySelector('input').checked); });
    var t = text(); pre.textContent = t;
    var mail = document.getElementById('mail');
    if (mail) mail.href = 'mailto:' + cfg.email + '?subject=' + encodeURIComponent(cfg.subject) + '&body=' + encodeURIComponent(t);
    var book = document.getElementById('book');
    if (book && cfg.booking) { var u = cfg.booking + (cfg.booking.indexOf('?') < 0 ? '?' : '&') + 'notes=' + encodeURIComponent(t.slice(0, 1500)); book.href = u; }
  }
  document.querySelectorAll('.lk input').forEach(function(i){ i.addEventListener('change', update); });
  var cp = document.getElementById('copy');
  if (cp) cp.addEventListener('click', function(){
    var t = text();
    var done = function(){ cp.textContent = cfg.copied; setTimeout(function(){ cp.textContent = cfg.copy; }, 1600); };
    if (navigator.clipboard) navigator.clipboard.writeText(t).then(done, function(){ fallback(t); done(); }); else { fallback(t); done(); }
  });
  function fallback(t){ var a = document.createElement('textarea'); a.value = t; document.body.appendChild(a); a.select(); try{document.execCommand('copy')}catch(e){} a.remove(); }
  update();
})();
"""


def build(R, N, cfg):
    lang = N.get("language") or R["meta"].get("language") or "en"
    T = {**L["en"], **L.get(lang, {}), **(N.get("labels") or {})}
    F = Fmt(R["meta"]["currency"], lang)
    k, t, a = R["kpis"], R["trends"], R["availability"]
    b = R["meta"].get("business", {})
    per = R["meta"]["period"]
    period_txt = ""
    if per["start"]:
        if per["start"][:4] == per["end"][:4]:
            period_txt = f"{month_label(per['start'], lang)} – {month_label(per['end'], lang)} {per['end'][:4]}"
        else:
            period_txt = f"{month_label(per['start'], lang)} {per['start'][:4]} – {month_label(per['end'], lang)} {per['end'][:4]}"

    primary = (R.get("model") or {}).get("primary")

    def delta(v, good_when_up=True, pp=False):
        if v is None or not t or primary == "launches":  # 3-vs-3 months is meaningless for launch cycles
            return ""
        cls = "up" if (v >= 0) == good_when_up else "down"
        arrow = "▲" if v >= 0 else "▼"
        val = (F.num(abs(v), 1) + (" п.п." if lang == "ru" else " pp")) if pp else F.pct(abs(v), 1)
        return f'<span class="{cls}">{arrow} {val}</span> {esc(T["vs_prev"].format(n=t["window_months"]))}'

    ow = R.get("owner") or {}
    X = sections.TX.get(lang, sections.TX["en"])
    if ow.get("owner_pay_total"):
        kp = [
            ("", T["revenue"], F.money(k["revenue"]), delta(t and t["revenue_change_pct"])),
            ("", T["expenses"], F.money(k["expenses"]), delta(t and t["expenses_change_pct"], good_when_up=False)),
            ("", X["profit_before"], F.money(k["profit"]), f'{esc(X["margin_word"])} {esc(F.pct(k["margin_pct"]))}'),
            ("main", X["profit_after"], F.money(ow.get("profit_after_owner")), f'{esc(X["margin_word"])} {esc(F.pct(ow.get("margin_after_owner_pct")))}'),
        ]
    else:
        kp = [
            ("", T["revenue"], F.money(k["revenue"]), delta(t and t["revenue_change_pct"])),
            ("", T["expenses"], F.money(k["expenses"]), delta(t and t["expenses_change_pct"], good_when_up=False)),
            ("main", T["profit"], F.money(k["profit"]), delta(t and t["profit_change_pct"])),
            ("", T["margin"], F.pct(k["margin_pct"]), delta(t and t["margin_change_pp"], pp=True)),
        ]
    parts = []
    parts.append(f'<div class="top"><div class="brand">sum<b>zee</b> · Profit Agent</div><div>{esc(b.get("name") or "")}{" · " if b.get("name") and period_txt else ""}{esc(period_txt)}</div></div>')
    parts.append(f'<h1>{esc(N.get("title") or T["title"])}</h1>')
    if N.get("headline"):
        parts.append(f'<p class="headline">{esc(N["headline"])}</p>')
    parts.append(sections.verdict_banner(R, N, lang if lang in sections.TX else "en"))
    parts.append('<div class="kpis">' + "".join(
        f'<div class="kpi {c}"><div class="k">{esc(lbl)}</div><div class="v">{esc(v)}</div><div class="d">{d}</div></div>' for c, lbl, v, d in kp) + "</div>")
    if k.get("cash_balance") is not None:
        cd = f' ({esc(k["cash_balance_date"])})' if k.get("cash_balance_date") else ""
        parts.append(f'<div class="pill">{esc(T["cash"])}{cd}: <b>{esc(F.money(k["cash_balance"]))}</b></div> ')
    if k.get("outstanding"):
        ov = f' · {esc(F.money(k["overdue"]))} {esc(T["overdue"])}' if k.get("overdue") else ""
        parts.append(f'<div class="pill">{esc(T["unpaid"])}: <b>{esc(F.money(k["outstanding"]))}</b>{ov}</div>')

    SL = lang if lang in sections.TX else "en"
    parts.append(sections.actions_card(R, N, F, SL))
    parts.append(sections.metrics_grid(R, F, SL))
    parts.append(sections.checks_card(R, N, F, SL))

    # insights: they are the "aha"
    ins = N.get("insights") or []
    if ins:
        parts.append(f'<div class="card"><h2>{esc(T["insights"])}</h2><p class="sub"></p><div class="ins">' + "".join(
            f'<div class="in {esc(i.get("tone", "neutral"))}"><h3>{esc(i.get("title", ""))}</h3><p>{esc(i.get("text", ""))}</p></div>' for i in ins[:5]) + "</div></div>")

    if len(R["monthly"]) >= 2:
        has_p = any(m["profit"] is not None for m in R["monthly"])
        mrow = "".join(f'<div class="{"neg" if (m["margin"] or 0) < 0 else ""}">{esc(month_label(m["month"], lang))}<b>{esc(F.pct(m["margin"], 0))}</b></div>' for m in R["monthly"])
        legend = f'<span><i style="background:var(--rev)"></i>{esc(T["legend_rev"])}</span>'
        if has_p:
            legend += (f'<span><i style="background:var(--exp)"></i>{esc(T["legend_exp"])}</span>'
                       f'<span><i style="background:var(--profit);border-radius:50%"></i>{esc(T["legend_profit"])}</span>')
        margin_block = f'<div class="small" style="margin-top:10px">{esc(T["margin_row"])}</div><div class="mrow">{mrow}</div>' if has_p and primary != "launches" else ""
        parts.append(
            f'<div class="card"><h2>{esc(T["over_time"])}</h2><div class="legend">{legend}</div>'
            f'<div class="chartbox">{monthly_chart(R["monthly"], F, lang)}</div>{margin_block}</div>')

    left = right = ""
    if R["cost_breakdown"]:
        left = f'<div class="card cost"><h2>{esc(T["money_goes"])}</h2><p class="sub">{esc(F.money(k["expenses"]))}</p>{hbars(R["cost_breakdown"], F, "amount", lang=lang, other_label=T["others"])}</div>'
    src = None
    if R["revenue_by_client"] and primary not in ("subscriptions", "launches"):
        src = ("by_client", [{**c, "name": sections.mask(c["name"])} for c in R["revenue_by_client"]])
    elif len(R["revenue_by_stream"]) > 1:
        src = ("by_stream", R["revenue_by_stream"])
    elif R["revenue_by_project"]:
        src = ("by_project", R["revenue_by_project"])
    if src:
        sub = ""
        con = R.get("concentration")
        if src[0] == "by_client" and con and con["clients"] > 3:
            sub = f'{T["top3"]}: {F.pct(con["top3_share_pct"], 0)}'
        right = f'<div class="card"><h2>{esc(T[src[0]])}</h2><p class="sub">{esc(sub or F.money(k["revenue"]))}</p>{hbars(src[1], F, "revenue", lang=lang, other_label=T["others"])}</div>'
    if left and right:
        parts.append(f'<div class="grid2 row">{left}{right}</div>')
    elif left or right:
        parts.append(left or right)
    if src and src[0] == "by_client" and len(R["revenue_by_stream"]) > 1:
        parts.append(f'<div class="card"><h2>{esc(T["by_stream"])}</h2>{hbars(R["revenue_by_stream"], F, "revenue", lang=lang, other_label=T["others"])}</div>')

    pp = R.get("project_profitability") or []
    if pp:
        team = any(p.get("team_costs") is not None for p in pp)
        rows = "".join(
            f'<tr><td>{esc(p["name"])}</td><td class="n">{esc(F.money(p["revenue"]))}</td><td class="n">{esc(F.money(p["direct_costs"]))}</td>'
            + (f'<td class="n">{esc(F.money(p["team_costs"]))}</td>' if team else "")
            + f'<td class="n {"neg" if (p["contribution"] or 0) < 0 else ""}">{esc(F.money(p["contribution"]))}</td><td class="n">{esc(F.pct(p["margin_pct"], 0))}</td></tr>'
            for p in pp[:12])
        head = (f'<tr><th></th><th class="n">{esc(T["revenue"])}</th><th class="n">{"Direct costs" if lang != "ru" else "Прямые расходы"}</th>'
                + (f'<th class="n">{"Team time" if lang != "ru" else "Время команды"}</th>' if team else "")
                + f'<th class="n">{esc(T["contribution"])}</th><th class="n">{esc(T["margin"])}</th></tr>')
        parts.append(f'<div class="card"><h2>{esc(T["proj_profit"])}</h2><p class="sub">{esc(T["proj_profit_sub"])}</p><div class="tbl"><table>{head}{rows}</table></div></div>')

    h = R.get("hours")
    if h:
        bits = [f'{F.num(h["total_hours"])} {T["hours"]}', f'{F.pct(h["billable_share_pct"], 0)} {T["billable"]}']
        if h.get("utilization_pct") is not None:
            bits.append(f'{F.pct(h["utilization_pct"], 0)} {T["utilization"]}')
        body = ""
        if h.get("by_person"):
            body = hbars(h["by_person"], F, "hours", share_key=None, lang=lang, other_label=T["others"],
                         fmt=lambda v: f'{F.num(v)} {T["hours"]}')
        er = h.get("effective_rate_by_project") or []
        if er:
            body += '<div class="tbl" style="margin-top:14px"><table>' + "".join(
                f'<tr><td>{esc(x["name"])}</td><td class="n">{esc(F.money(x["revenue_per_hour"]))} <span class="small">{esc(T["per_hour"])}</span></td></tr>' for x in er[:8]) + "</table></div>"
        parts.append(f'<div class="card"><h2>{esc(T["team"])}</h2><p class="sub">{esc(" · ".join(bits))}</p>{body}</div>')

    # ---- locked opportunities
    locked_src = N.get("locked") or []
    by_id = {o["id"]: o for o in R["opportunities"]["locked"]}
    if not locked_src:
        locked_src = [{"id": o["id"]} for o in R["opportunities"]["locked"][:3]]
    defaults = LOCKED_DEFAULTS.get(lang, LOCKED_DEFAULTS["en"])
    cards, shown_missing = [], []
    for i, lk in enumerate(locked_src[:4]):
        oid = lk.get("id", f"custom{i}")
        title, text = defaults.get(oid, ("", ""))
        mt = next((m for m in R.get("metrics") or [] if m["id"] == oid), None)
        if mt and not title:
            title = sections.METRIC_LABELS.get(SL, sections.METRIC_LABELS["en"]).get(oid, oid)
        title = lk.get("title") or title or oid
        text = lk.get("text") or text
        missing = lk.get("missing") or by_id.get(oid, {}).get("missing", []) or (mt or {}).get("missing", [])
        if not lk.get("missing"):
            missing = sections.tr_missing(missing, SL)
        chips = "".join(f"<span>{esc(m)}</span>" for m in missing)
        shown_missing += [m for m in missing if m not in shown_missing]
        cards.append(
            f'<div class="lk"><div class="ghostbox">{ghost_chart(oid, i + 3)}{LOCK_SVG}</div><h3>{esc(title)}</h3><p>{esc(text)}</p>'
            + (f'<div class="chips"><b>{esc(T["needs"])}:</b>{chips}</div>' if chips else "")
            + f'<label><input type="checkbox" data-title="{esc(title)}"> {esc(T["want"])}</label></div>')
    brief = brief_base(R, N, lang, shown_missing)
    booking = cfg.get("booking_url") or ""
    email = cfg.get("contact_email") or ""
    btns = []
    if booking:
        btns.append(f'<a class="btn" id="book" href="{esc(booking)}" target="_blank" rel="noopener">{esc(T["cta_btn"])}</a>')
    if email:
        btns.append(f'<a class="btn {"sec" if booking else ""}" id="mail" href="mailto:{esc(email)}">{esc(T["cta_email"])}</a>')
    btns.append(f'<button class="btn sec" id="copy" type="button">{esc(T["copy"])}</button>')
    if cards:
        parts.append(
            f'<section class="more"><h2>{esc(N.get("more_title") or T["more"])}</h2><p class="sub">{esc(N.get("more_text") or T["more_sub"])}</p>'
            f'<div class="locks{" four" if len(cards) == 4 else ""}">{"".join(cards)}</div>'
            f'<div class="cta"><div><h3>{esc(T["cta_title"])}</h3><p>{esc(N.get("cta_text") or T["cta_text"])}</p><div class="btns">{"".join(btns)}</div></div>'
            f'<div><div class="small">{esc(T["brief"])}</div><pre class="brief" id="brief"></pre></div></div></section>')

    parts.append(sections.feedback_card(R, SL, cfg))
    if N.get("replace_script_notes"):
        notes = list(N.get("data_notes") or [])
    else:
        notes = list(N.get("data_notes") or []) + [n for n in R.get("data_notes", []) if n not in (N.get("data_notes") or [])]
    srcs = [s["source"] for s in R["meta"]["sources"]]
    parts.append(f'<div class="card"><details><summary>{esc(T["how"])}</summary><ul>'
                 + "".join(f"<li>{esc(n)}</li>" for n in notes)
                 + f'<li>{esc(T["sources"])}: {esc(", ".join(srcs))}</li></ul></details></div>')
    parts.append(f'<footer><span>{esc(T["footer"])} v{esc(cfg.get("version", "0.1"))}</span><span>{esc(T["privacy"])}</span></footer>')

    jcfg = {"email": email, "booking": booking, "subject": cfg.get("email_subject", "Sumzee setup — Profit Agent brief"),
            "copy": T["copy"], "copied": T["copied"], "none": T["no_selection"]}
    blur = '<svg width="0" height="0" style="position:absolute"><filter id="blur"><feGaussianBlur stdDeviation="2.6"/></filter></svg>'
    title = f'{N.get("title") or T["title"]} — {b.get("name") or "Sumzee"}'
    cfg_json = json.dumps(jcfg, ensure_ascii=False).replace("</", "<\\/")
    brief_json = json.dumps(brief, ensure_ascii=False).replace("</", "<\\/")
    return (f'<!doctype html><html lang="{esc(lang)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)}</title><style>{CSS}{sections.CSS}</style></head><body>{blur}<div class="wrap">{"".join(parts)}</div>'
            f'<script type="application/json" id="brief-base">{brief_json}</script>'
            f'<script type="application/json" id="cfg">{cfg_json}</script>'
            f'<script>{JS}{sections.JS}</script></body></html>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("narrative")
    ap.add_argument("--out", default="profit-dashboard.html")
    ap.add_argument("--config", default=str(HERE.parent / "config.json"))
    args = ap.parse_args()
    R = json.loads(Path(args.results).read_text(encoding="utf-8"))
    N = json.loads(Path(args.narrative).read_text(encoding="utf-8")) if Path(args.narrative).exists() else {}
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8")) if Path(args.config).exists() else {}
    Path(args.out).write_text(build(R, N, cfg), encoding="utf-8")
    print(json.dumps({"saved": args.out}))


if __name__ == "__main__":
    main()
