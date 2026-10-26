"""Dashboard sections for the Sumzee methodology: verdict, checks, model metrics,
actions and the feedback survey. Imported by build_dashboard.py."""
from __future__ import annotations

import html
import json

def esc(s):
    return html.escape(str(s if s is not None else ""))


TX = {
    "en": {
        "verdict": {"healthy": "Healthy", "attention": "Needs attention", "risk": "At risk", "insufficient": "Not enough data for a verdict"},
        "confidence": {"high": "high confidence", "medium": "medium confidence", "low": "low confidence"},
        "conf_line": "based on {a} of {b} key metrics",
        "models": {"projects": "project business", "retainers": "retainer business", "subscriptions": "subscription business", "launches": "launch / course business"},
        "model_line": "Read as a {m}",
        "model_mixed": " with a {m} part",
        "model_mismatch": " (you said {s}, the data looks like {d})",
        "checks_title": "What we checked and fixed",
        "checks_sub": "Before calculating anything, we went through your data the way an operations consultant would.",
        "metrics_title": "What matters for your business",
        "core_title": "Every business",
        "norm": "norm", "risk_at": "risk",
        "needs": "Needs",
        "actions_title": "What to do",
        "per_month": "/ month", "one_off": "one-off", "per_launch": "per launch",
        "profit_before": "Profit before owner pay", "profit_after": "After owner pay",
        "margin_word": "margin",
        "fb_title": "Did this get it right?",
        "fb_sub": "Two clicks help us make the analysis better. Only what you see in the box below is sent — no amounts, no client names.",
        "fb_q1": "The verdict feels…", "fb_yes": "Right", "fb_partly": "Partly right", "fb_no": "Wrong",
        "fb_q2": "Most useful metric", "fb_q3": "A metric that felt wrong", "fb_none": "—",
        "fb_q4": "Anything else? (optional)", "fb_send": "Send to Sumzee", "fb_copy": "Copy", "fb_preview": "What will be sent",
        "status": {"green": "good", "yellow": "watch", "red": "risk", "locked": "locked"},
        "check_status": {"ok": "OK", "fixed": "Fixed", "warn": "Check", "not_possible": "Not possible"},
        "months_unit": "mo",
    },
    "ru": {
        "verdict": {"healthy": "Бизнес здоров", "attention": "Требует внимания", "risk": "Есть риск", "insufficient": "Данных мало для вердикта"},
        "confidence": {"high": "высокая уверенность", "medium": "средняя уверенность", "low": "низкая уверенность"},
        "conf_line": "по {a} из {b} ключевых метрик",
        "models": {"projects": "проектный бизнес", "retainers": "бизнес на ретейнерах", "subscriptions": "подписочный бизнес", "launches": "бизнес на запусках и курсах"},
        "model_line": "Смотрим как на {m}",
        "model_mixed": " с частью «{m}»",
        "model_mismatch": " (вы указали: {s}, по данным похоже на: {d})",
        "checks_title": "Что мы проверили и исправили",
        "checks_sub": "Прежде чем считать, мы прошлись по данным так, как это сделал бы операционный консультант.",
        "metrics_title": "Что важно для вашего бизнеса",
        "core_title": "Для любого бизнеса",
        "norm": "норма", "risk_at": "риск",
        "needs": "Нужно",
        "actions_title": "Что сделать",
        "per_month": "/ мес.", "one_off": "разово", "per_launch": "за запуск",
        "profit_before": "Прибыль до выплат владельцу", "profit_after": "После выплат владельцу",
        "margin_word": "маржа",
        "fb_title": "Мы попали?",
        "fb_sub": "Пара кликов помогает нам делать анализ точнее. Отправляется только то, что вы видите в окне ниже, — без сумм и названий клиентов.",
        "fb_q1": "Вердикт кажется…", "fb_yes": "Верным", "fb_partly": "Частично верным", "fb_no": "Неверным",
        "fb_q2": "Самая полезная метрика", "fb_q3": "Метрика, которая показалась неверной", "fb_none": "—",
        "fb_q4": "Что-то ещё? (необязательно)", "fb_send": "Отправить Sumzee", "fb_copy": "Скопировать", "fb_preview": "Что будет отправлено",
        "status": {"green": "хорошо", "yellow": "внимание", "red": "риск", "locked": "нет данных"},
        "check_status": {"ok": "Ок", "fixed": "Исправлено", "warn": "Проверьте", "not_possible": "Нельзя проверить"},
        "months_unit": "мес.",
    },
}

METRIC_LABELS = {
    "en": {
        "margin_after_owner_pct": "Margin after owner pay", "cash_runway_months": "Cash buffer (months of costs)",
        "top_client_share_pct": "Largest client's share", "overdue_to_revenue": "Overdue invoices vs monthly revenue",
        "team_cost_share_pct": "Team costs vs revenue",
        "project_margin_pct": "Project margin (after team time)", "loss_projects_share_pct": "Loss-making projects",
        "utilization_pct": "Team utilization", "effective_rate_vs_target_pct": "Real hourly rate vs target",
        "backlog_months": "Work booked ahead",
        "recurring_share_pct": "Recurring revenue share", "missed_payments": "Missed retainer payments",
        "client_churn_12m_pct": "Clients lost in 12 months", "overservice_pct": "Hours over the retainer",
        "mrr_growth_pct": "Monthly recurring revenue growth", "monthly_churn_pct": "Monthly churn",
        "revenue_retention_pct": "Revenue retention (12 mo)", "customer_lifetime_months": "Customer lifetime",
        "payback_months": "Acquisition payback",
        "launch_margin_pct": "Profit per launch", "refund_share_pct": "Refunds", "repeat_buyers_pct": "Repeat buyers",
        "base_revenue_share_pct": "Revenue between launches", "pause_coverage": "Cash for the next pause",
    },
    "ru": {
        "margin_after_owner_pct": "Маржа после выплат владельцу", "cash_runway_months": "Запас денег (мес. расходов)",
        "top_client_share_pct": "Доля крупнейшего клиента", "overdue_to_revenue": "Просроченные счета к месячной выручке",
        "team_cost_share_pct": "Команда в выручке",
        "project_margin_pct": "Маржа проектов (с учётом часов)", "loss_projects_share_pct": "Убыточные проекты",
        "utilization_pct": "Загрузка команды", "effective_rate_vs_target_pct": "Реальная ставка к целевой",
        "backlog_months": "Запас работы вперёд",
        "recurring_share_pct": "Доля стабильной выручки", "missed_payments": "Пропуски оплат ретейнеров",
        "client_churn_12m_pct": "Ушедшие клиенты за 12 мес.", "overservice_pct": "Переработка по ретейнерам",
        "mrr_growth_pct": "Рост выручки по подпискам", "monthly_churn_pct": "Отток в месяц",
        "revenue_retention_pct": "Удержание выручки за год", "customer_lifetime_months": "Срок жизни клиента",
        "payback_months": "Окупаемость привлечения",
        "launch_margin_pct": "Прибыль запуска", "refund_share_pct": "Возвраты", "repeat_buyers_pct": "Повторные покупатели",
        "base_revenue_share_pct": "Выручка между запусками", "pause_coverage": "Деньги на паузу между запусками",
    },
}

MISSING_RU = {
    "expenses": "расходы",
    "how the owner is paid": "как владелец платит себе",
    "current cash balance": "текущий остаток на счёте",
    "client on each invoice / payment": "клиент в каждом счёте или платеже",
    "invoice payment status (paid / unpaid)": "статус оплаты счетов",
    "salaries and freelancers as separate cost categories": "зарплаты и фрилансеры отдельными статьями",
    "project on each invoice": "проект в каждом счёте",
    "team hours per project": "часы команды по проектам",
    "cost of one team hour": "себестоимость часа команды",
    "team hours (timesheet)": "часы команды (таймшит)",
    "available hours per person per month": "доступные часы каждого в месяц",
    "target hourly rate": "целевая ставка в час",
    "signed but not yet delivered work, with amounts": "подписанные, но не выполненные работы с суммами",
    "client name on each payment": "клиент в каждом платеже",
    "at least 3 months of data": "данные хотя бы за 3 месяца",
    "12 months of payment history": "история оплат за 12 месяцев",
    "team hours per client": "часы команды по клиентам",
    "hours included in each retainer": "сколько часов входит в каждый ретейнер",
    "at least 4 months of revenue": "выручка хотя бы за 4 месяца",
    "customer id / email on each payment": "id или email клиента в каждом платеже",
    "13 months of history": "история за 13 месяцев",
    "marketing spend as a separate category": "расходы на маркетинг отдельной статьёй",
    "which payments and costs belong to which launch": "какие платежи и расходы к какому запуску",
    "refunds visible in the data": "возвраты в данных",
    "buyer id / email on each payment": "id или email покупателя в каждом платеже",
    "at least two launches in the data": "хотя бы два запуска в данных",
    "dates on transactions": "даты операций",
    "expense categories": "статьи расходов",
    "client name on each invoice / income row": "клиент в каждом счёте",
    "project-related costs (freelancers, tools) tagged by project": "расходы с привязкой к проектам",
    "client on each invoice": "клиент в каждом счёте",
    "costs linked to clients or projects": "расходы с привязкой к клиентам или проектам",
    "team time per client": "время команды по клиентам",
    "each person's available hours per month": "доступные часы каждого в месяц",
    "expected payment dates of open invoices": "ожидаемые даты оплаты открытых счетов",
    "unpaid invoices with due dates": "неоплаченные счета со сроками",
    "list of recurring monthly payments": "список регулярных платежей",
    "service / offer type on each invoice": "тип услуги в каждом счёте",
    "deal pipeline with expected value and close date (CRM)": "воронка сделок с суммами и датами (CRM)",
    "expenses (bank export, cost sheet or accounting export)": "расходы (выписка, таблица расходов или выгрузка из бухгалтерии)",
}

MISSING_COST_NAMES = {
    "en": {"taxes": "taxes", "insurance": "insurance", "accounting": "accountant", "bank_fees": "bank fees"},
    "ru": {"taxes": "налоги", "insurance": "страховки", "accounting": "бухгалтер", "bank_fees": "банковские комиссии"},
}


def tr_missing(items, lang):
    if lang != "ru":
        return items
    return [MISSING_RU.get(x, x) for x in items]


import re as _re
_EMAIL = _re.compile(r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+)")


def mask(text):
    """Customer emails never appear on the page."""
    return _EMAIL.sub(lambda m: m.group(1) + "•••@" + m.group(2), str(text))


def fmt_metric(m, F, lang):
    v, u = m["value"], m["unit"]
    if v is None:
        return "—"
    if u == "%":
        return F.pct(v, 0)
    if u == "months":
        return f"{F.num(v, 1)} {TX[lang]['months_unit']}"
    if u == "x":
        return F.num(v, 1) + "×"
    return F.num(v)


def rule_text(m, F, lang):
    r = m["rule"]
    X = TX[lang]
    unit = {"%": "%", "months": f" {X['months_unit']}", "x": "×"}.get(m["unit"], "")
    def n(v):
        return F.num(v, 1 if isinstance(v, float) and not float(v).is_integer() else 0) + unit
    if "good_range" in r:
        lo, hi = r["good_range"]
        return f"{X['norm']} {n(lo)}–{n(hi)}"
    if r.get("higher_is_better", True):
        return f"{X['norm']} ≥ {n(r['good'])} · {X['risk_at']} < {n(r['bad'])}"
    return f"{X['norm']} ≤ {n(r['good'])} · {X['risk_at']} > {n(r['bad'])}"


def verdict_banner(R, N, lang):
    X = TX[lang]
    v = R.get("verdict")
    if not v:
        return ""
    mdl = R.get("model", {})
    ml = X["model_line"].format(m=X["models"].get(mdl.get("primary"), mdl.get("primary", "")))
    if mdl.get("secondary"):
        ml += X["model_mixed"].format(m=X["models"].get(mdl["secondary"], mdl["secondary"]))
    if mdl.get("mismatch"):
        ml += X["model_mismatch"].format(s=X["models"].get(mdl.get("stated"), ""), d=X["models"].get(mdl.get("detected"), ""))
    conf = f'{X["confidence"][v["confidence"]]} · {X["conf_line"].format(a=v["metrics_computed"], b=v["metrics_total"])}'
    text = N.get("verdict_text") or ""
    return (f'<div class="verdict v-{esc(v["verdict"])}"><div class="v-dot"></div><div><div class="v-title">{esc(X["verdict"][v["verdict"]])}</div>'
            f'{f"<p>{esc(text)}</p>" if text else ""}<div class="v-meta">{esc(ml)} · {esc(conf)}</div></div></div>')


def check_text(c, F, lang):
    n = c.get("numbers") or {}
    ru = lang == "ru"
    cid, st = c["id"], c["status"]
    if cid == "reconciliation":
        if st == "not_possible":
            return ("Сверка с остатком на счёте — в данных нет остатка" if ru else "Bank balance reconciliation — no balance in the data")
        if st == "ok":
            return (f"Сверили с остатком на счёте: {F.money(n['opening'])} + движение {F.money(n['net_flow'])} = {F.money(n['closing'])}, ничего не потеряно"
                    if ru else f"Reconciled with the bank balance: {F.money(n['opening'])} + net flow {F.money(n['net_flow'])} = {F.money(n['closing'])} — nothing is missing")
        return (f"Остаток на счёте не сходится с операциями на {F.money(n['difference'])} — в выгрузке чего-то не хватает"
                if ru else f"Bank balance doesn't match the transactions by {F.money(n['difference'])} — something is missing from the export")
    if cid == "owner_pay":
        if st == "fixed":
            bits_ru, bits_en = [], []
            if n.get("in_data"):
                bits_ru.append(f"в данных — {F.money(n['in_data'])}")
                bits_en.append(f"{F.money(n['in_data'])} in the data")
            if n.get("outside_data"):
                bits_ru.append(f"вне этих файлов — {F.money(n['outside_data'])} по вашим словам")
                bits_en.append(f"{F.money(n['outside_data'])} outside these files, as you told us")
            return (f"Выплаты владельцу ({'; '.join(bits_ru)}) показываем отдельно: прибыль до и после них"
                    if ru else f"Owner pay ({'; '.join(bits_en)}) is shown separately: profit before and after it")
        if st == "ok":
            return ("Зарплата владельца уже в расходах" if ru else "Owner's pay is already in expenses")
        return ("Не знаем, как владелец платит себе — прибыль может быть завышена" if ru else "We don't know how the owner is paid — profit may look higher than it is")
    if cid == "non_expenses":
        items = n.get("items") or []
        if not items:
            return ("Переводов между своими счетами и отменённых счетов не нашли" if ru else "No own-account transfers or cancelled invoices found")
        parts = "; ".join(f"{i['reason']} — {F.money(i['amount'])}" for i in items if i.get("amount") is not None)
        return (f"Не посчитали как доход или расход: {parts}" if ru else f"Left out as not real income or costs: {parts}")
    if cid == "missing_costs":
        if st == "not_possible":
            return ("Статьи расходов проверить нельзя — расходов нет в данных" if ru else "Can't check cost categories — no expenses in the data")
        miss = [MISSING_COST_NAMES[lang if lang in MISSING_COST_NAMES else "en"].get(x, x) for x in n.get("not_seen") or []]
        if not miss:
            return ("Типичные статьи (налоги, страховки, бухгалтер, комиссии) на месте" if ru else "Typical costs (taxes, insurance, accountant, fees) are all there")
        return (f"Не нашли: {', '.join(miss)}. Если вы их платите с другого счёта, реальная прибыль ниже"
                if ru else f"Not in the data: {', '.join(miss)}. If you pay these from elsewhere, real profit is lower")
    if cid == "sheet_totals":
        its = n.get("items") or []
        diff = [i for i in its if i.get("difference")]
        if diff:
            d = diff[0]
            return (f"Строка «Итого» в таблице ({F.money(d['sheet_total'])}) расходится с пересчётом ({F.money(d['recomputed'])}) — формула в таблице неверна"
                    if ru else f"The sheet's own Total ({F.money(d['sheet_total'])}) doesn't match a recount ({F.money(d['recomputed'])}) — the sheet's formula is off")
        return ("Строки «Итого» в таблицах не посчитали второй раз" if ru else "The sheets' Total rows were not counted twice")
    if cid == "partial_month":
        return (f"{n['month']} ещё не закончился — не включали, чтобы не выглядел провалом" if ru else f"{n['month']} isn't complete — left out so it doesn't look like a drop")
    if cid == "sanity":
        if st == "ok":
            return (f"Маржа {F.pct(n['margin_pct'], 0)} в правдоподобных пределах" if ru else f"Margin of {F.pct(n['margin_pct'], 0)} is within a plausible range")
        return (f"Маржа {F.pct(n['margin_pct'], 0)} выглядит неправдоподобно — проверьте, все ли расходы в данных" if ru
                else f"A {F.pct(n['margin_pct'], 0)} margin looks implausible — check that all costs are in the data")
    return cid


ICONS = {"ok": "✓", "fixed": "✎", "warn": "!", "not_possible": "–"}


def checks_card(R, N, F, lang):
    X = TX[lang]
    cs = R.get("checks") or []
    if not cs:
        return ""
    over = {c.get("id"): c.get("text") for c in (N.get("checks") or []) if c.get("id")}
    order = {"fixed": 0, "warn": 1, "ok": 2, "not_possible": 3}
    rows = []
    for c in sorted(cs, key=lambda c: order.get(c["status"], 9)):
        txt = over.get(c["id"]) or check_text(c, F, lang)
        rows.append(f'<li class="ck {esc(c["status"])}"><span class="ck-i">{ICONS.get(c["status"], "")}</span>'
                    f'<span class="ck-t">{esc(txt)}</span><span class="ck-s">{esc(X["check_status"][c["status"]])}</span></li>')
    return f'<div class="card"><h2>{esc(X["checks_title"])}</h2><p class="sub">{esc(X["checks_sub"])}</p><ul class="checks">{"".join(rows)}</ul></div>'


def metrics_grid(R, F, lang):
    X = TX[lang]
    ms = R.get("metrics") or []
    if not ms:
        return ""
    labels = METRIC_LABELS.get(lang, METRIC_LABELS["en"])
    groups = []
    order = ["core"] + [g for g in (R.get("model", {}).get("primary"), R.get("model", {}).get("secondary")) if g]
    for g in order:
        items = [m for m in ms if m["group"] == g]
        if not items:
            continue
        title = X["core_title"] if g == "core" else X["models"].get(g, g).capitalize()
        cards = []
        for m in items:
            lab = labels.get(m["id"], m["id"])
            if m["status"] == "locked":
                need = ", ".join(tr_missing(m["missing"], lang))
                cards.append(f'<div class="mc locked"><div class="mc-l">{esc(lab)}</div><div class="mc-v">🔒</div>'
                             f'<div class="mc-r">{esc(X["needs"])}: {esc(need)}</div></div>')
            else:
                det = m.get("detail")
                det = ", ".join(det) if isinstance(det, list) else det
                det = mask(det) if det else det
                cards.append(f'<div class="mc {esc(m["status"])}"><div class="mc-l">{esc(lab)}</div>'
                             f'<div class="mc-v">{esc(fmt_metric(m, F, lang))} <span class="mc-s">{esc(X["status"][m["status"]])}</span></div>'
                             f'<div class="mc-r">{esc(rule_text(m, F, lang))}{(" · " + esc(det)) if det else ""}</div></div>')
        groups.append(f'<div class="mg"><div class="mg-t">{esc(title)}</div><div class="mgrid">{"".join(cards)}</div></div>')
    return f'<div class="card"><h2>{esc(X["metrics_title"])}</h2>{"".join(groups)}</div>'


ACTION_RU = {
    "team_cost_to_norm": "Снизить долю команды в выручке до нормы — через цены или загрузку",
    "collect_overdue": "Собрать счета, неоплаченные дольше 30 дней",
    "collect_unpaid": "Собрать неоплаченные счета",
    "chase_missed_retainers": "Проверить и собрать пропущенные оплаты ретейнеров",
    "rate_to_target": "Выйти на целевую ставку в час при текущей загрузке",
    "price_plus_5": "Сценарий: +5% к ценам при тех же клиентах и загрузке",
}


def action_title(a, lang):
    if lang != "ru":
        return a["what"]
    if a["id"].startswith("cost_back:"):
        return f"Вернуть «{a['id'].split(':', 1)[1]}» к уровню предыдущих месяцев"
    return ACTION_RU.get(a["id"], a["what"])


def actions_card(R, N, F, lang):
    X = TX[lang]
    acts = N.get("actions")
    if not acts:
        comp = [a for a in (R.get("actions") or []) if a["id"] != "price_plus_5"][:3]
        acts = [{"title": action_title(a, lang), "effect": a["effect"], "kind": a["kind"]} for a in comp]
    if not acts:
        return ""
    rows = []
    for a in acts[:3]:
        eff = a.get("effect_text")
        if not eff and a.get("effect") is not None:
            kind = a.get("kind", "monthly")
            eff = f'+{F.money(a["effect"])} {X["per_month"] if kind == "monthly" else (X["per_launch"] if kind == "per_launch" else X["one_off"])}'
        rows.append(f'<li><div><b>{esc(a.get("title", ""))}</b>{("<p>" + esc(a.get("text")) + "</p>") if a.get("text") else ""}</div>'
                    f'<div class="act-e">{esc(eff or "")}</div></li>')
    return f'<div class="card"><h2>{esc(X["actions_title"])}</h2><ol class="acts">{"".join(rows)}</ol></div>'


def feedback_card(R, lang, cfg):
    X = TX[lang]
    ms = R.get("metrics") or []
    labels = METRIC_LABELS.get(lang, METRIC_LABELS["en"])
    opts = "".join(f'<option value="{esc(m["id"])}">{esc(labels.get(m["id"], m["id"]))}</option>' for m in ms if m["status"] != "locked")
    base = {
        "tool": "Sumzee Profit Agent", "version": cfg.get("version", "0.2"),
        "model": (R.get("model") or {}).get("primary"), "model_detected": (R.get("model") or {}).get("detected"),
        "verdict": (R.get("verdict") or {}).get("verdict"), "confidence": (R.get("verdict") or {}).get("confidence"),
        "metrics": {m["id"]: m["status"] for m in ms},
        "checks": {c["id"]: c["status"] for c in (R.get("checks") or [])},
        "months_of_data": R["meta"]["period"]["months"],
        "language": lang,
    }
    fb_cfg = {"email": cfg.get("feedback_email") or cfg.get("contact_email") or "",
              "subject": "Sumzee Profit Agent — feedback", "copy": X["fb_copy"]}
    btn = f'<a class="btn" id="fb-send" href="#">{esc(X["fb_send"])}</a>' if fb_cfg["email"] else ""
    return (f'<div class="card fb"><h2>{esc(X["fb_title"])}</h2><p class="sub">{esc(X["fb_sub"])}</p>'
            f'<div class="fb-q"><div class="fb-l">{esc(X["fb_q1"])}</div><div class="seg">'
            f'<label><input type="radio" name="fb-v" value="yes">{esc(X["fb_yes"])}</label>'
            f'<label><input type="radio" name="fb-v" value="partly">{esc(X["fb_partly"])}</label>'
            f'<label><input type="radio" name="fb-v" value="no">{esc(X["fb_no"])}</label></div></div>'
            f'<div class="fb-row"><label class="fb-q"><span class="fb-l">{esc(X["fb_q2"])}</span><select id="fb-useful"><option value="">{esc(X["fb_none"])}</option>{opts}</select></label>'
            f'<label class="fb-q"><span class="fb-l">{esc(X["fb_q3"])}</span><select id="fb-wrong"><option value="">{esc(X["fb_none"])}</option>{opts}</select></label></div>'
            f'<label class="fb-q"><span class="fb-l">{esc(X["fb_q4"])}</span><textarea id="fb-c" rows="2" maxlength="600"></textarea></label>'
            f'<details><summary>{esc(X["fb_preview"])}</summary><pre class="brief" id="fb-prev"></pre></details>'
            f'<div class="btns" style="margin-top:10px">{btn}<button class="btn sec" id="fb-copy" type="button">{esc(X["fb_copy"])}</button></div>'
            f'<script type="application/json" id="fb-base">{json.dumps(base, ensure_ascii=False).replace("</", "<" + chr(92) + "/")}</script>'
            f'<script type="application/json" id="fb-cfg">{json.dumps(fb_cfg, ensure_ascii=False).replace("</", "<" + chr(92) + "/")}</script></div>')


CSS = """
.verdict{display:flex;gap:14px;align-items:flex-start;border-radius:16px;padding:16px 18px;margin:0 0 16px;border:1px solid var(--line);background:var(--card)}
.v-dot{width:14px;height:14px;border-radius:50%;margin-top:6px;flex:none;background:var(--muted)}
.v-healthy .v-dot{background:var(--good)}.v-attention .v-dot{background:#d9a21b}.v-risk .v-dot{background:var(--neg)}
.v-healthy{border-left:5px solid var(--good)}.v-attention{border-left:5px solid #d9a21b}.v-risk{border-left:5px solid var(--neg)}.v-insufficient{border-left:5px solid var(--muted)}
.v-title{font:600 20px/1.25 Georgia,serif}.verdict p{margin:4px 0 0;color:var(--ink)}.v-meta{font-size:12.5px;color:var(--muted);margin-top:6px}
.checks{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}
.ck{display:grid;grid-template-columns:26px 1fr auto;gap:10px;align-items:start;font-size:14px}
.ck-i{width:22px;height:22px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;background:var(--chip);color:var(--muted)}
.ck.ok .ck-i{background:rgba(47,122,91,.15);color:var(--good)}.ck.fixed .ck-i{background:rgba(31,75,67,.12);color:var(--accent)}.ck.warn .ck-i{background:rgba(217,162,27,.18);color:#a8790b}
.ck-s{font-size:12px;color:var(--muted);white-space:nowrap}.ck.not_possible .ck-t{color:var(--muted)}
.mg{margin-top:14px}.mg-t{font-size:12.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-bottom:8px}
.mgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px}
.mc{border:1px solid var(--line);border-radius:12px;padding:12px 14px;border-top:4px solid var(--ghost)}
.mc.green{border-top-color:var(--good)}.mc.yellow{border-top-color:#d9a21b}.mc.red{border-top-color:var(--neg)}
.mc.locked{background:var(--chip);border-style:dashed}.mc-l{font-size:13px;color:var(--muted)}
.mc-v{font:600 22px/1.3 Georgia,serif;margin-top:2px}.mc-s{font:500 12px/1 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif;margin-left:6px;padding:3px 7px;border-radius:99px;background:var(--chip);vertical-align:3px}
.mc.green .mc-s{color:var(--good)}.mc.yellow .mc-s{color:#a8790b}.mc.red .mc-s{color:var(--neg)}.mc-r{font-size:12px;color:var(--muted);margin-top:4px}
.acts{margin:0;padding-left:20px;display:flex;flex-direction:column;gap:10px}.acts li{display:flex;justify-content:space-between;gap:14px}
.acts p{margin:2px 0 0;color:var(--muted);font-size:14px}.act-e{font-weight:600;white-space:nowrap;color:var(--good)}
.fb .seg{display:flex;flex-wrap:wrap;gap:8px}.fb .seg label{border:1px solid var(--line);border-radius:99px;padding:6px 12px;cursor:pointer;font-size:14px}
.fb .seg input{margin-right:6px;accent-color:var(--accent)}.fb-q{display:block;margin-top:12px}.fb-l{display:block;font-size:13px;color:var(--muted);margin-bottom:6px}
.fb-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}.fb select,.fb textarea{width:100%;font:inherit;padding:8px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
@media (max-width:760px){.fb-row{grid-template-columns:1fr}.acts li{flex-direction:column;gap:2px}}
@media (prefers-color-scheme:dark){.ck.warn .ck-i,.mc.yellow .mc-s{color:#e8b94a}}
"""

JS = """
(function(){
  var baseEl = document.getElementById('fb-base'); if (!baseEl) return;
  var base = JSON.parse(baseEl.textContent), cfg = JSON.parse(document.getElementById('fb-cfg').textContent);
  var prev = document.getElementById('fb-prev');
  function val(){
    var v = document.querySelector('input[name="fb-v"]:checked');
    var o = JSON.parse(JSON.stringify(base));
    o.verdict_feels = v ? v.value : null;
    o.most_useful = document.getElementById('fb-useful').value || null;
    o.felt_wrong = document.getElementById('fb-wrong').value || null;
    o.comment = document.getElementById('fb-c').value || null;
    return JSON.stringify(o, null, 1);
  }
  function up(){
    var t = val(); prev.textContent = t;
    var s = document.getElementById('fb-send');
    if (s && cfg.email) s.href = 'mailto:' + cfg.email + '?subject=' + encodeURIComponent(cfg.subject) + '&body=' + encodeURIComponent(t);
  }
  document.querySelectorAll('.fb input, .fb select, .fb textarea').forEach(function(e){ e.addEventListener('input', up); e.addEventListener('change', up); });
  var cp = document.getElementById('fb-copy');
  cp.addEventListener('click', function(){
    var t = val();
    var ok = function(){ var o = cp.textContent; cp.textContent = '✓'; setTimeout(function(){ cp.textContent = o; }, 1400); };
    if (navigator.clipboard) navigator.clipboard.writeText(t).then(ok, ok); else ok();
  });
  up();
})();
"""
