"""Sumzee methodology: business model, model-specific health metrics, verdict,
mandatory checks and candidate actions with a computed effect.

Thresholds live in ../thresholds.json so they can be tuned without code.
Everything here is computed; the agent only chooses and words it.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
MODELS = ("projects", "retainers", "subscriptions", "launches")


def load_thresholds():
    p = HERE.parent / "thresholds.json"
    return json.loads(p.read_text(encoding="utf-8"))


def r2(x):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return round(float(x), 2)


def mk(d):
    return f"{d.year:04d}-{d.month:02d}"


def fmt(v, lang="en", dec=0):
    if v is None:
        return "—"
    s = f"{abs(v):,.{dec}f}"
    if lang == "ru":
        s = s.replace(",", " ").replace(".", ",")
    return ("−" if v < 0 else "") + s


# ----------------------------------------------------------------- status ---

def status_of(value, rule):
    if value is None:
        return "locked"
    if "good_range" in rule:
        lo, hi = rule["good_range"]
        olo, ohi = rule.get("ok_range", rule["good_range"])
        if lo <= value <= hi:
            return "green"
        if olo <= value <= ohi:
            return "yellow"
        return "red"
    good, bad = rule["good"], rule["bad"]
    if rule.get("higher_is_better", True):
        if value >= good:
            return "green"
        if value < bad:
            return "red"
        return "yellow"
    if value <= good:
        return "green"
    if value > bad:
        return "red"
    return "yellow"


def metric(group, mid, value, unit, T, missing=None, note=None, detail=None):
    rule = T[group][mid]
    st = status_of(value, rule) if not missing or value is not None else "locked"
    if value is None:
        st = "locked"
    return {"id": mid, "group": group, "value": r2(value), "unit": unit, "status": st,
            "critical": bool(rule.get("critical")), "rule": {k: v for k, v in rule.items() if k != "critical"},
            "missing": (missing or []) if value is None else [], "note": note, "detail": detail}


# -------------------------------------------------------------- helpers -----

TEAM_WORDS = r"salar|payroll|wage|staff|team|freelanc|contractor|upwork|fiverr|зарплат|фот|оплата труда|фриланс|подрядчик|исполнител|сотрудник"
MARKETING_WORDS = r"marketing|ads|advert|google ads|facebook|meta ads|реклам|маркетинг|таргет|продвижен"
REFUND_WORDS = r"refund|chargeback|возврат"
MISSING_CHECK = {
    "taxes": r"tax|vat|irs|hmrc|налог|ндс|фнс|усн|страхов.*взнос|מס",
    "insurance": r"insur|страхов",
    "accounting": r"account|bookkeep|бухгалт|аудит",
    "bank_fees": r"bank fee|fee|commission|комисси|обслуживан",
}
LAUNCH_WORDS = r"getcourse|prodamus|launch|cohort|поток|запуск|курс|вебинар|интенсив"
SUB_WORDS = r"subscription|membership|recurring|abonnement|подписк|абонемент|stripe|paddle|chargebee"


def text_of(df):
    parts = []
    for c in ("category", "vendor", "description", "stream", "project"):
        if c in df.columns:
            parts.append(df[c].fillna("").astype(str))
    if not parts:
        return pd.Series("", index=df.index)
    out = parts[0]
    for p in parts[1:]:
        out = out + " " + p
    return out.str.lower()


def client_month_matrix(rev):
    r = rev.dropna(subset=["client", "date"])
    if r.empty:
        return None
    r = r.assign(_m=r["date"].map(mk))
    return r.pivot_table(index="client", columns="_m", values="amount", aggfunc="sum", fill_value=0)


# ------------------------------------------------------- model detection ----

def detect_model(R, rev, months, T):
    sig = {}
    total = float(rev["amount"].sum()) or 0.0
    mat = client_month_matrix(rev)
    rec_share = None
    n_clients = 0
    if mat is not None and len(months) >= 3:
        cols = [m for m in months if m in mat.columns]
        present = (mat[cols] > 0).sum(axis=1) if cols else pd.Series(dtype=float)
        n_clients = int(len(mat))
        recurring = present[present >= max(3, 0.75 * len(months))].index
        rec_share = float(mat.loc[recurring].values.sum()) / total * 100 if total else None
        sig["recurring_clients"] = int(len(recurring))
        sig["recurring_share_pct"] = r2(rec_share)
        sig["clients"] = n_clients
        avg_active = float((mat[cols] > 0).sum(axis=0).mean()) if cols else 0
        sig["avg_paying_clients_per_month"] = r2(avg_active)
    mrev = [m["revenue"] or 0 for m in R["monthly"]]
    spike_share = None
    if len(mrev) >= 4 and sum(mrev):
        med = sorted(mrev)[len(mrev) // 2]
        spikes = [v for v in mrev if med and v > 1.8 * med]
        spike_share = sum(spikes) / sum(mrev) * 100
        sig["spike_months"] = len(spikes)
        sig["spike_share_pct"] = r2(spike_share)
    txt = " ".join(text_of(rev).tolist())[:200000]
    sig["launch_words"] = bool(re.search(LAUNCH_WORDS, txt))
    sig["subscription_words"] = bool(re.search(SUB_WORDS, txt))
    sig["project_column"] = bool(rev["project"].notna().any())

    scores = {m: 0.0 for m in MODELS}
    if spike_share is not None and spike_share >= 45:
        scores["launches"] += 2
    if sig["launch_words"]:
        scores["launches"] += 1
    if rec_share is not None:
        many = (sig.get("avg_paying_clients_per_month") or 0) >= 25
        if rec_share >= 50 and many:
            scores["subscriptions"] += 2
        elif rec_share >= 50:
            scores["retainers"] += 2
        elif rec_share >= 30:
            scores["retainers"] += 1
            scores["projects"] += 1
        else:
            scores["projects"] += 2
    if sig["subscription_words"]:
        scores["subscriptions"] += 1
    if sig["project_column"] and (rec_share or 0) < 50:
        scores["projects"] += 1
    if max(scores.values()) == 0:
        scores["projects"] = 0.5  # the most common shape for small service businesses
    ranked = sorted(scores, key=lambda m: -scores[m])
    detected = ranked[0]
    secondary = None
    primary_share = T["model_detection"]["primary_share_pct"]
    if (detected in ("retainers", "projects") and rec_share is not None
            and 100 - primary_share < rec_share < primary_share):
        # neither recurring nor one-off revenue reaches the primary share → mixed
        detected = "retainers" if rec_share >= 50 else "projects"
        secondary = "projects" if detected == "retainers" else "retainers"
    return {"detected": detected, "secondary": secondary, "scores": scores, "signals": sig}


# ------------------------------------------------------------- metrics ------

def owner_block(R, mapping):
    biz = mapping.get("business", {}) or {}
    op = biz.get("owner_pay") or {}
    method = op.get("method", "unknown")
    draws = sum(e["amount"] or 0 for e in R.get("excluded", []) if e.get("owner"))
    months = R["meta"]["period"]["months"] or 0
    outside = float(op.get("monthly_outside_data") or 0) * months
    owner_total = draws + outside
    profit = R["kpis"]["profit"]
    rev = R["kpis"]["revenue"] or 0
    if profit is None:
        return {"method": method, "owner_pay_total": r2(owner_total), "profit_after_owner": None, "margin_after_owner_pct": None}
    if method == "salary" and not owner_total:
        after = profit  # owner is already in payroll
    else:
        after = profit - owner_total
    return {"method": method, "owner_pay_total": r2(owner_total), "owner_draws_in_data": r2(draws),
            "owner_pay_outside_data": r2(outside),
            "profit_after_owner": r2(after), "margin_after_owner_pct": r2(after / rev * 100) if rev else None,
            "known": method != "unknown" or owner_total > 0}


def core_metrics(R, recs, mapping, T, owner, unpaid_values):
    k = R["kpis"]
    months = R["meta"]["period"]["months"] or 0
    out = []
    # 1 margin after owner
    missing = []
    if not R["availability"]["expenses"]:
        missing = ["expenses"]
    elif not owner.get("known"):
        missing = ["how the owner is paid"]
    out.append(metric("core", "margin_after_owner_pct",
                      owner["margin_after_owner_pct"] if owner.get("known") else None, "%", T, missing))
    # 2 cash runway
    bal = k.get("cash_balance")
    if bal is None and (mapping.get("business", {}) or {}).get("cash_balance") is not None:
        bal = float(mapping["business"]["cash_balance"])
    outflow_m = ((k.get("expenses") or 0) + (owner.get("owner_draws_in_data") or 0)) / months if months else None
    runway = bal / outflow_m if bal is not None and outflow_m else None
    out.append(metric("core", "cash_runway_months", runway, "months", T,
                      ["current cash balance"] if bal is None else (["expenses"] if not outflow_m else [])))
    # 3 top client
    con = R.get("concentration")
    out.append(metric("core", "top_client_share_pct", con["top1_share_pct"] if con else None, "%", T,
                      ["client on each invoice / payment"], detail=con["top1_name"] if con else None))
    # 4 overdue / revenue
    rev = recs[recs["kind"] == "revenue"]
    ratio = None
    miss = []
    if unpaid_values and len(rev):
        last = rev["date"].max()
        st = rev["status"].fillna("").str.lower()
        unpaid = st.isin([u.lower() for u in unpaid_values])
        overdue = unpaid & (st.str.contains("overdue|просроч|late") | (rev["date"] <= last - pd.Timedelta(days=30)))
        amt = float(rev.loc[overdue, "amount"].sum())
        avg = k.get("avg_monthly_revenue")
        ratio = amt / avg if avg else None
        R["kpis"]["overdue_30d"] = r2(amt)
    else:
        miss = ["invoice payment status (paid / unpaid)"]
    out.append(metric("core", "overdue_to_revenue", ratio, "x", T, miss))
    # 5 team cost share
    exp = recs[recs["kind"] == "expense"]
    team_cats = [c.lower() for c in (mapping.get("team_categories") or [])]
    share = None
    if len(exp) and k.get("revenue"):
        key = exp["category"].fillna(exp["vendor"]).fillna("").astype(str).str.lower()
        if team_cats:
            is_team = key.isin(team_cats)
        else:
            is_team = key.str.contains(TEAM_WORDS) | text_of(exp).str.contains(TEAM_WORDS)
        team = float(exp.loc[is_team, "amount"].sum())
        labor = (R.get("hours") or {}).get("labor_cost") or 0
        if team or labor:
            share = (team + (labor if not team else 0)) / k["revenue"] * 100
    out.append(metric("core", "team_cost_share_pct", share, "%", T,
                      ["salaries and freelancers as separate cost categories"]))
    return out


def projects_metrics(R, recs, hrs, mapping, T):
    out = []
    biz = mapping.get("business", {}) or {}
    pp = [p for p in R.get("project_profitability") or [] if p.get("team_costs") is not None]
    if pp:
        rev = sum(p["revenue"] or 0 for p in pp)
        contrib = sum(p["contribution"] or 0 for p in pp)
        m = contrib / rev * 100 if rev else None
        loss = sum(1 for p in pp if (p["contribution"] or 0) < 0) / len(pp) * 100
    else:
        m = loss = None
    need = []
    if not R["availability"]["revenue_projects"]:
        need.append("project on each invoice")
    if not R["availability"]["team_hours"]:
        need.append("team hours per project")
    if not biz.get("hour_cost") and not R["availability"]["team_hours_costed"]:
        need.append("cost of one team hour")
    out.append(metric("projects", "project_margin_pct", m, "%", T, need))
    out.append(metric("projects", "loss_projects_share_pct", loss, "%", T, need))
    h = R.get("hours") or {}
    out.append(metric("projects", "utilization_pct", h.get("utilization_pct"), "%", T,
                      (["team hours (timesheet)"] if not h else []) + ["available hours per person per month"]))
    target = biz.get("target_hourly_rate")
    er = h.get("effective_rate_by_project") or []
    val = None
    if er and target:
        rv = sum(x["revenue"] or 0 for x in er)
        hh = sum(x["hours"] or 0 for x in er)
        val = rv / hh / float(target) * 100 if hh else None
    out.append(metric("projects", "effective_rate_vs_target_pct", val, "%", T,
                      (["team hours per project"] if not er else []) + (["target hourly rate"] if not target else [])))
    backlog = biz.get("backlog_amount")
    avg = R["kpis"].get("avg_monthly_revenue")
    out.append(metric("projects", "backlog_months", float(backlog) / avg if backlog and avg else None, "months", T,
                      ["signed but not yet delivered work, with amounts"]))
    return out


def retainers_metrics(R, recs, hrs, mapping, T, model_info):
    out = []
    biz = mapping.get("business", {}) or {}
    rev = recs[recs["kind"] == "revenue"]
    months = [m["month"] for m in R["monthly"]]
    rs = model_info["signals"].get("recurring_share_pct")
    out.append(metric("retainers", "recurring_share_pct", rs, "%", T, ["client name on each payment", "at least 3 months of data"]))
    gaps = R.get("client_gaps") or []
    missed = sum(len(g["missing_months"]) for g in gaps) if rev["client"].notna().any() and len(months) >= 4 else None
    out.append(metric("retainers", "missed_payments", missed, "count", T, ["client name on each payment"],
                      detail=[g["client"] for g in gaps] or None))
    churn = None
    mat = client_month_matrix(rev)
    if mat is not None and len(months) >= 9:
        first = [m for m in months[:3] if m in mat.columns]
        lastm = [m for m in months[-3:] if m in mat.columns]
        start = set(mat.index[(mat[first] > 0).any(axis=1)])
        end = set(mat.index[(mat[lastm] > 0).any(axis=1)])
        churn = len(start - end) / len(start) * 100 if start else None
    out.append(metric("retainers", "client_churn_12m_pct", churn, "%", T, ["12 months of payment history"],
                      note=f"{len(months)} months of data" if churn is not None and len(months) < 12 else None))
    over = None
    contracted = mapping.get("retainer_hours") or {}
    if hrs is not None and contracted and hrs["client"].notna().any():
        hm = hrs.dropna(subset=["client"]).groupby("client")["hours"].sum()
        nmonths = max(1, hrs["date"].dropna().map(mk).nunique())
        pairs = [(hm.get(c, 0) / nmonths, float(v)) for c, v in contracted.items() if v]
        act, plan = sum(a for a, _ in pairs), sum(b for _, b in pairs)
        over = (act / plan - 1) * 100 if plan else None
    out.append(metric("retainers", "overservice_pct", over, "%", T,
                      (["team hours per client"] if hrs is None else []) + ([] if contracted else ["hours included in each retainer"])))
    target = biz.get("target_hourly_rate")
    val = None
    if hrs is not None and target and rev["client"].notna().any():
        hcl = hrs.dropna(subset=["client"]) if hrs["client"].notna().any() else None
        if hcl is not None and len(hcl):
            rv = rev[rev["client"].isin(hcl["client"].unique())]["amount"].sum()
            val = rv / hcl["hours"].sum() / float(target) * 100 if hcl["hours"].sum() else None
    out.append(metric("retainers", "effective_rate_vs_target_pct", val, "%", T,
                      (["team hours per client"] if hrs is None else []) + ([] if target else ["target hourly rate"])))
    return out


def subscriptions_metrics(R, recs, mapping, T):
    out = []
    rev = recs[recs["kind"] == "revenue"]
    mon = [m for m in R["monthly"] if m["revenue"] is not None]
    g = None
    if len(mon) >= 4:
        vals = [m["revenue"] for m in mon[-4:]]
        rates = [(b / a - 1) * 100 for a, b in zip(vals, vals[1:]) if a]
        g = sum(rates) / len(rates) if rates else None
    out.append(metric("subscriptions", "mrr_growth_pct", g, "%", T, ["at least 4 months of revenue"]))
    mat = client_month_matrix(rev)
    churn = life = nrr = None
    months = [m["month"] for m in R["monthly"]]
    if mat is not None and len(months) >= 3:
        rates = []
        for a, b in zip(months[-4:], months[-3:]):
            if a in mat.columns and b in mat.columns:
                pa = set(mat.index[mat[a] > 0])
                pb = set(mat.index[mat[b] > 0])
                if pa:
                    rates.append(len(pa - pb) / len(pa) * 100)
        churn = sum(rates) / len(rates) if rates else None
        life = 100 / churn if churn else None
        if len(months) >= 13:
            a, b = months[-13], months[-1]
            base = mat.index[mat[a] > 0]
            nrr = mat.loc[base, b].sum() / mat.loc[base, a].sum() * 100 if mat.loc[base, a].sum() else None
    need_id = [] if mat is not None else ["customer id / email on each payment"]
    out.append(metric("subscriptions", "monthly_churn_pct", churn, "%", T, need_id or ["at least 3 months of data"]))
    out.append(metric("subscriptions", "revenue_retention_pct", nrr, "%", T, need_id + ["13 months of history"]))
    out.append(metric("subscriptions", "customer_lifetime_months", life, "months", T, need_id))
    payback = None
    exp = recs[recs["kind"] == "expense"]
    mkt = exp[text_of(exp).str.contains(MARKETING_WORDS)]
    if mat is not None and len(mkt) and len(months) >= 3 and R["kpis"].get("margin_pct"):
        firsts = mat.apply(lambda row: next((m for m in months if m in row.index and row[m] > 0), None), axis=1)
        new = firsts[firsts.isin(months[1:])].count()
        if new:
            cac = float(mkt["amount"].sum()) / new
            arpu = float(rev["amount"].sum()) / max(1, (mat > 0).values.sum())
            gm = R["kpis"]["margin_pct"] / 100
            payback = cac / (arpu * gm) if arpu and gm > 0 else None
    out.append(metric("subscriptions", "payback_months", payback, "months", T,
                      ["marketing spend as a separate category"] + need_id))
    return out


def spike_months(R):
    mrev = [(m["month"], m["revenue"] or 0) for m in R["monthly"]]
    if len(mrev) < 4:
        return []
    vals = sorted(v for _, v in mrev)
    med = vals[len(vals) // 2]
    return [mo for mo, v in mrev if med and v > 1.8 * med]


def launch_margin(R, recs):
    """Launch months = revenue spikes. Launch costs = spend above a normal month."""
    sp = spike_months(R)
    other = [m for m in R["monthly"] if m["month"] not in sp]
    if not sp or not other:
        return None, {}
    rev_sp = sum(m["revenue"] or 0 for m in R["monthly"] if m["month"] in sp)
    exp_sp = sum(m["expenses"] or 0 for m in R["monthly"] if m["month"] in sp)
    base_exp = sum(m["expenses"] or 0 for m in other) / len(other)
    extra = exp_sp - base_exp * len(sp)
    margin = (rev_sp - extra) / rev_sp * 100 if rev_sp else None
    return margin, {"launch_months": sp, "launches": len(sp), "avg_launch_revenue": r2(rev_sp / len(sp)),
                    "avg_launch_extra_costs": r2(extra / len(sp)), "avg_launch_profit": r2((rev_sp - extra) / len(sp)),
                    "normal_month_costs": r2(base_exp)}


def launches_metrics(R, recs, mapping, model_info, T):
    out = []
    rev = recs[recs["kind"] == "revenue"]
    exp = recs[recs["kind"] == "expense"]
    lm, ls = launch_margin(R, recs)
    R["launch_stats"] = ls
    out.append(metric("launches", "launch_margin_pct", lm, "%", T,
                      ["which payments and costs belong to which launch"],
                      note="estimated: costs above a normal month count as launch costs" if lm is not None else None))
    refunds = float(-rev.loc[rev["amount"] < 0, "amount"].sum())
    refunds += float(exp.loc[text_of(exp).str.contains(REFUND_WORDS), "amount"].sum())
    total = float(rev.loc[rev["amount"] > 0, "amount"].sum())
    has_refund_signal = refunds > 0 or bool(text_of(rev).str.contains(REFUND_WORDS).any())
    out.append(metric("launches", "refund_share_pct", refunds / total * 100 if total and has_refund_signal else None, "%", T,
                      ["refunds visible in the data"]))
    rep = None
    r = rev[rev["amount"] > 0].dropna(subset=["client"])
    if len(r):
        per = r.assign(_m=r["date"].map(lambda d: mk(d) if not pd.isna(d) else "")).groupby("client")["_m"].nunique()
        rep = (per >= 2).mean() * 100
    out.append(metric("launches", "repeat_buyers_pct", rep, "%", T, ["buyer id / email on each payment"]))
    mrev = [m["revenue"] or 0 for m in R["monthly"]]
    base = None
    if len(mrev) >= 4 and sum(mrev):
        med = sorted(mrev)[len(mrev) // 2]
        base = sum(v for v in mrev if not (med and v > 1.8 * med)) / sum(mrev) * 100
    out.append(metric("launches", "base_revenue_share_pct", base, "%", T, ["at least 4 months of revenue"]))
    bal = R["kpis"].get("cash_balance")
    cover = None
    spikes = [i for i, v in enumerate(mrev) if len(mrev) >= 4 and sorted(mrev)[len(mrev) // 2] and v > 1.8 * sorted(mrev)[len(mrev) // 2]]
    if bal is not None and len(spikes) >= 2 and R["kpis"].get("expenses"):
        gap = (spikes[-1] - spikes[0]) / (len(spikes) - 1)
        monthly_out = R["kpis"]["expenses"] / max(1, len(mrev))
        cover = bal / (monthly_out * gap) if gap else None
    out.append(metric("launches", "pause_coverage", cover, "x", T,
                      (["current cash balance"] if bal is None else []) + (["at least two launches in the data"] if len(spikes) < 2 else [])))
    return out


# -------------------------------------------------------------- verdict -----

def verdict_of(metrics):
    live = [m for m in metrics if m["status"] != "locked"]
    reds = [m for m in live if m["status"] == "red"]
    yel = [m for m in live if m["status"] == "yellow"]
    if any(m["critical"] for m in reds) or len(reds) >= 2:
        v = "risk"
    elif reds or len(yel) >= 2:
        v = "attention"
    else:
        v = "healthy"
    share = len(live) / len(metrics) if metrics else 0
    conf = "high" if share >= 0.7 else ("medium" if share >= 0.4 else "low")
    critical_live = [m for m in live if m["critical"]]
    if v == "healthy" and not critical_live and conf == "low":
        v = "insufficient"  # can't call a business healthy without seeing profit or cash
    return {"verdict": v, "confidence": conf, "metrics_computed": len(live), "metrics_total": len(metrics),
            "red": [m["id"] for m in reds], "yellow": [m["id"] for m in yel]}


# --------------------------------------------------------------- checks -----

def checks_of(R, recs, owner, T):
    out = []
    rc = R.get("reconciliation") or []
    if rc:
        bad = [x for x in rc if abs(x["difference"] or 0) > 1]
        out.append({"id": "reconciliation", "status": "warn" if bad else "ok",
                    "numbers": rc[0] if not bad else bad[0]})
    else:
        out.append({"id": "reconciliation", "status": "not_possible"})
    in_data = owner.get("owner_draws_in_data") or 0
    outside = owner.get("owner_pay_outside_data") or 0
    if in_data or outside:
        ost = "fixed"
    elif owner.get("method") == "salary":
        ost = "ok"
    else:
        ost = "warn"
    out.append({"id": "owner_pay", "status": ost,
                "numbers": {"method": owner.get("method"), "owner_pay_total": owner.get("owner_pay_total"),
                            "in_data": in_data, "outside_data": outside,
                            "profit_before": R["kpis"]["profit"], "profit_after": owner.get("profit_after_owner")}})
    ex = [e for e in R.get("excluded", []) if not e.get("owner")]
    out.append({"id": "non_expenses", "status": "fixed" if ex else "ok",
                "numbers": {"items": [{"reason": e["reason"], "amount": e["amount"], "rows": e["rows"]} for e in ex]}})
    exp = recs[recs["kind"] == "expense"]
    txt = " ".join(text_of(exp).tolist()) if len(exp) else ""
    missing = [k for k, rx in MISSING_CHECK.items() if not re.search(rx, txt)] if len(exp) else []
    out.append({"id": "missing_costs", "status": ("not_possible" if not len(exp) else ("warn" if missing else "ok")),
                "numbers": {"not_seen": missing}})
    st = R.get("sheet_totals") or []
    if st:
        diff = [x for x in st if x.get("difference") and abs(x["difference"]) > 1]
        out.append({"id": "sheet_totals", "status": "fixed", "numbers": {"items": st, "mismatch": bool(diff)}})
    pm = R["meta"].get("partial_month_excluded")
    if pm:
        out.append({"id": "partial_month", "status": "fixed", "numbers": {"month": pm}})
    m = R["kpis"].get("margin_pct")
    if m is not None:
        s = T["sanity"]
        out.append({"id": "sanity", "status": "ok" if s["margin_min_pct"] <= m <= s["margin_max_pct"] else "warn",
                    "numbers": {"margin_pct": m}})
    return out


# -------------------------------------------------------------- actions -----

def actions_of(R, metrics, owner):
    """Candidate actions with a computed monthly (or one-off) effect."""
    k = R["kpis"]
    avg_rev = k.get("avg_monthly_revenue") or 0
    months = R["meta"]["period"]["months"] or 1
    acts = []
    t = R.get("trends")
    for c in R.get("cost_breakdown") or []:
        if t and c.get("change_pct") is not None and c["change_pct"] - (t.get("revenue_change_pct") or 0) >= 10 and (c["share_pct"] or 0) >= 7:
            effect = (c.get("last_window_monthly") or 0) - (c.get("prev_window_monthly") or 0)
            if effect and effect > 0:
                acts.append({"id": f"cost_back:{c['name']}", "kind": "monthly", "effect": r2(effect),
                             "what": f"bring '{c['name']}' back to the level of the previous {t['window_months']} months"})
    byid = {m["id"]: m for m in metrics}
    tc = byid.get("team_cost_share_pct")
    if tc and tc["status"] in ("yellow", "red") and avg_rev:
        acts.append({"id": "team_cost_to_norm", "kind": "monthly",
                     "effect": r2((tc["value"] - tc["rule"]["good"]) / 100 * avg_rev),
                     "what": f"bring team costs from {tc['value']}% to {tc['rule']['good']}% of revenue (by prices or workload)"})
    if k.get("overdue_30d"):
        acts.append({"id": "collect_overdue", "kind": "one_off", "effect": k["overdue_30d"],
                     "what": "collect invoices unpaid for 30+ days"})
    elif k.get("outstanding"):
        acts.append({"id": "collect_unpaid", "kind": "one_off", "effect": k["outstanding"], "what": "collect unpaid invoices"})
    primary = (R.get("model") or {}).get("primary")
    gaps = R.get("client_gaps") or [] if primary in ("retainers", "projects") else []
    if gaps:
        amt = sum((g["typical_monthly"] or 0) * len(g["missing_months"]) for g in gaps)
        acts.append({"id": "chase_missed_retainers", "kind": "one_off", "effect": r2(amt),
                     "what": "check and chase missed retainer payments: " + ", ".join(f"{g['client']} ({', '.join(g['missing_months'])})" for g in gaps)})
    er = byid.get("effective_rate_vs_target_pct")
    if er and er["value"] is not None and er["value"] < 100:
        h = R.get("hours") or {}
        hrs_m = (h.get("total_hours") or 0) / max(1, h.get("months") or 1)
        target_gap = (1 - er["value"] / 100)
        acts.append({"id": "rate_to_target", "kind": "monthly", "effect": r2(target_gap * avg_rev),
                     "what": "reach the target hourly rate on current workload (pricing or scope)"})
    ch = byid.get("monthly_churn_pct")
    if ch and ch["value"] is not None and ch["status"] in ("yellow", "red"):
        sig = (R.get("model") or {}).get("signals", {})
        active = sig.get("avg_paying_clients_per_month") or 0
        arpu = avg_rev / active if active else 0
        keep = (ch["value"] - ch["rule"]["good"]) / 100 * active
        acts.append({"id": "churn_to_norm", "kind": "monthly", "effect": r2(keep * arpu),
                     "what": f"bring monthly churn from {ch['value']}% to {ch['rule']['good']}% (win-back, onboarding, annual plans) — added to monthly revenue every month"})
    rf = byid.get("refund_share_pct")
    launches = (R.get("launch_stats") or {})
    if rf and rf["value"] is not None and rf["status"] in ("yellow", "red") and launches.get("avg_launch_revenue"):
        acts.append({"id": "refunds_to_norm", "kind": "per_launch",
                     "effect": r2((rf["value"] - rf["rule"]["good"]) / 100 * launches["avg_launch_revenue"]),
                     "what": f"bring refunds from {rf['value']}% to {rf['rule']['good']}% of launch revenue"})
    if avg_rev:
        acts.append({"id": "price_plus_5", "kind": "monthly", "effect": r2(0.05 * avg_rev),
                     "what": "scenario: +5% on prices with the same clients and workload"})
    return acts


# ------------------------------------------------------------- evaluate -----

def evaluate(R, recs, hrs, mapping, unpaid_values):
    T = load_thresholds()
    rev = recs[recs["kind"] == "revenue"]
    months = [m["month"] for m in R["monthly"]]
    model = detect_model(R, rev, months, T)
    stated = (mapping.get("business", {}) or {}).get("model")
    if stated in MODELS:
        model["stated"] = stated
        model["mismatch"] = stated != model["detected"]
        model["primary"] = stated
    else:
        model["primary"] = model["detected"]
    if model.get("secondary") == model["primary"]:
        model["secondary"] = None
    owner = owner_block(R, mapping)
    metrics = core_metrics(R, recs, mapping, T, owner, unpaid_values)
    groups = [model["primary"]] + ([model["secondary"]] if model.get("secondary") else [])
    for g in groups:
        if g == "projects":
            metrics += projects_metrics(R, recs, hrs, mapping, T)
        elif g == "retainers":
            metrics += retainers_metrics(R, recs, hrs, mapping, T, model)
        elif g == "subscriptions":
            metrics += subscriptions_metrics(R, recs, mapping, T)
        elif g == "launches":
            metrics += launches_metrics(R, recs, mapping, model, T)
    seen, uniq = set(), []
    for m in metrics:
        key = (m["group"], m["id"])
        if key not in seen:
            seen.add(key)
            uniq.append(m)
    R["model"] = model
    R["owner"] = owner
    if model["primary"] in ("subscriptions", "launches"):
        R["facts"] = [f for f in R.get("facts", []) if not f["id"].startswith("client_gap") and f["id"] != "loss_months"
                      and not (model["primary"] == "launches" and f["id"] in ("trend", "growth_without_profit"))]
    R["metrics"] = uniq
    R["verdict"] = verdict_of(uniq)
    R["checks"] = checks_of(R, recs, owner, T)
    R["actions"] = actions_of(R, uniq, owner)
    return R
