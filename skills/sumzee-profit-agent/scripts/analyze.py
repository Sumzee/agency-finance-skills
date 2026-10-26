#!/usr/bin/env python3
"""Step 2 — calculate everything the data allows, deterministically.

Usage:
    python analyze.py mapping.json --out results.json

mapping.json is written by the agent after looking at inspect_files.py output
(format: references/mapping_format.md). The model never does the arithmetic:
this script reads the files, applies the mapping and computes totals, monthly
trends, breakdowns, profitability, data availability, factual observations
and the list of "locked" analyses the data does not support yet.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (amounts, canonical_labels, clean_label, is_total_row,  # noqa: E402
                    load_source_table, month_key, parse_dates, parse_month_label)
from methodology import evaluate  # noqa: E402

REC_COLS = ["kind", "date", "amount", "client", "project", "category", "vendor",
            "stream", "status", "due_date", "description", "granularity", "source"]


def r2(x):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return round(float(x), 2)


def pct(a, b):
    if b in (0, None) or a is None:
        return None
    return round((a - b) / abs(b) * 100, 1)


def _match(series: pd.Series, values) -> pd.Series:
    vals = {str(v).strip().lower() for v in values}
    return series.map(lambda x: (clean_label(x) or "").lower() in vals)


class Notes:
    def __init__(self):
        self.items = []

    def add(self, text):
        if text not in self.items:
            self.items.append(text)


# ------------------------------------------------------------ load sources ---

EXCLUDED = []
BALANCES = []
TOTAL_CHECKS = []
RECONCILIATIONS = []


def _slice_amount(df, src):
    cols = src.get("columns", {}) or {}
    for key in ("amount", "amount_out", "amount_in"):
        c = cols.get(key)
        if c and c in df.columns:
            v = amounts(df[c]).abs().sum()
            if key == "amount_out" and cols.get("amount_in") in df.columns:
                v += amounts(df[cols["amount_in"]]).abs().sum()
            return float(v)
    return None


def _record_exclusion(df_slice, src, label, reason, owner=False):
    amt = _slice_amount(df_slice, src)
    EXCLUDED.append({"source": label, "reason": reason, "rows": int(len(df_slice)), "amount": r2(amt), "owner": bool(owner)})
    return amt


def apply_filters(df, src, notes, label):
    for rule in src.get("exclude_if", []) or []:
        col = rule["column"]
        if col not in df.columns:
            notes.add(f"{label}: filter column '{col}' not found — filter skipped")
            continue
        m = _match(df[col], rule["values"])
        if m.any():
            reason = f"{col} is {', '.join(map(str, rule['values']))}"
            amt = _record_exclusion(df[m], src, label, reason, rule.get("owner"))
            notes.add(f"{label}: left out {int(m.sum())} rows where {reason}" + (f" (total {amt:,.2f})" if amt else ""))
        df = df[~m]
    for rule in src.get("include_if", []) or []:
        col = rule["column"]
        if col not in df.columns:
            continue
        m = _match(df[col], rule["values"])
        if (~m).any():
            notes.add(f"{label}: used only rows where {col} is {', '.join(map(str, rule['values']))} ({int((~m).sum())} other rows left out)")
        df = df[m]
    return df


def apply_rules(df, src, notes, label):
    """Text rules for tables without clean columns (typical bank exports):
    {"column": "Description", "contains": ["PAYROLL", "SALARY"], "set": {"category": "Salaries"}}
    {"column": "Description", "contains": ["OWNER DRAW"], "exclude": true}"""
    sets = []
    for rule in src.get("rules", []) or []:
        c = rule["column"]
        if c not in df.columns:
            notes.add(f"{label}: rule column '{c}' not found — rule skipped")
            continue
        words = [str(w).lower() for w in rule.get("contains", []) if str(w).strip()]
        if not words:
            continue
        text = df[c].map(lambda v: (clean_label(v) or "").lower())
        m = text.map(lambda t: any(w in t for w in words))
        if rule.get("exclude"):
            if m.any():
                reason = rule.get("reason") or f"contains {', '.join(rule['contains'])}"
                amt = _record_exclusion(df[m], src, label, reason, rule.get("owner"))
                notes.add(f"{label}: left out {int(m.sum())} rows containing {', '.join(rule['contains'])}"
                          + (f" — {rule['reason']}" if rule.get("reason") else "") + (f" (total {amt:,.2f})" if amt else ""))
            df = df[~m]
            sets = [(mm[~m], st) for mm, st in sets]
        elif rule.get("set"):
            sets.append((m, rule["set"]))
    return df, sets


def _signed_flow(df, src):
    """Money in minus money out per row, before any filtering (None if unknown)."""
    cols = src.get("columns", {}) or {}
    mult = float(src.get("amount_multiplier", 1) or 1)
    if cols.get("amount_in") or cols.get("amount_out"):
        a_in = amounts(df[cols["amount_in"]]).fillna(0).abs() if cols.get("amount_in") in df.columns else 0
        a_out = amounts(df[cols["amount_out"]]).fillna(0).abs() if cols.get("amount_out") in df.columns else 0
        return (a_in - a_out) * mult
    if cols.get("amount") in df.columns and src.get("role") == "ledger":
        return amounts(df[cols["amount"]]).fillna(0) * mult
    return None


def check_sheet_totals(df, total_mask, src, label):
    """Compare a sheet's own 'Total' row with the sum we recompute from its rows."""
    cols = src.get("columns", {}) or {}
    c = cols.get("amount") or cols.get("amount_in")
    if not c or c not in df.columns:
        return
    body = amounts(df.loc[~total_mask, c]).abs().sum()
    totals = amounts(df.loc[total_mask, c]).dropna()
    item = {"source": label, "rows": int(total_mask.sum()), "recomputed": r2(body),
            "sheet_total": r2(abs(totals.iloc[-1])) if len(totals) else None}
    if item["sheet_total"] is not None and body:
        item["difference"] = r2(item["sheet_total"] - body)
    TOTAL_CHECKS.append(item)


def check_reconciliation(df, src, label):
    """Opening balance + all money in − all money out should equal the closing balance."""
    cols = src.get("columns", {}) or {}
    if not (cols.get("balance") in df.columns and cols.get("date")):
        return
    flow = _signed_flow(df, src)
    if flow is None:
        return
    t = pd.DataFrame({"date": parse_dates(df[cols["date"]]), "bal": amounts(df[cols["balance"]]), "flow": flow})
    t = t.dropna(subset=["date", "bal"])
    if len(t) < 2:
        return
    t = t.sort_values("date", kind="stable")
    opening = float(t["bal"].iloc[0] - t["flow"].iloc[0])
    closing = float(t["bal"].iloc[-1])
    moved = float(flow.sum())
    RECONCILIATIONS.append({"source": label, "opening": r2(opening), "closing": r2(closing),
                            "net_flow": r2(moved), "difference": r2(closing - opening - moved)})


def col(df, cols, key):
    name = (cols or {}).get(key)
    if not name:
        return None
    if name not in df.columns:
        raise KeyError(f"Column '{name}' (for {key}) not found. Available: {list(df.columns)}")
    return df[name]


def long_records(df, src, notes, label, base_kind=None):
    cols = src.get("columns", {})
    mult = float(src.get("amount_multiplier", 1) or 1)
    total_mask = df.apply(is_total_row, axis=1)
    if total_mask.any():
        notes.add(f"{label}: ignored {int(total_mask.sum())} total/subtotal row(s)")
        check_sheet_totals(df, total_mask, src, label)
        df = df[~total_mask]
    check_reconciliation(df, src, label)
    if cols.get("balance") and cols["balance"] in df.columns and cols.get("date"):
        # balance is read before any filtering: it is the bank's own running total
        bal = pd.DataFrame({"date": parse_dates(df[cols["date"]]), "balance": amounts(df[cols["balance"]])}).dropna()
        if len(bal):
            last = bal.sort_values("date", kind="stable").iloc[-1]
            BALANCES.append({"date": str(pd.Timestamp(last["date"]).date()), "balance": r2(last["balance"]), "source": label})
    df = apply_filters(df, src, notes, label)
    df, rule_sets = apply_rules(df, src, notes, label)
    n0 = len(df)

    out = pd.DataFrame(index=df.index)
    out["date"] = parse_dates(col(df, cols, "date")) if cols.get("date") else pd.NaT
    for key in ("client", "project", "category", "vendor", "stream", "status", "description"):
        s = col(df, cols, key)
        out[key] = canonical_labels(s, src.get(f"{key}_map")) if s is not None else None
    out["due_date"] = parse_dates(col(df, cols, "due_date")) if cols.get("due_date") else pd.NaT
    out["granularity"] = "transaction"
    out["source"] = label
    for m, st in reversed(rule_sets):  # earlier rules win
        m = m.reindex(out.index, fill_value=False)
        for key, val in st.items():
            if key in out.columns:
                out.loc[m, key] = val

    role = src["role"]
    if role == "ledger" and (cols.get("amount_in") or cols.get("amount_out")):
        a_in = amounts(col(df, cols, "amount_in")).fillna(0).abs() * mult if cols.get("amount_in") else 0
        a_out = amounts(col(df, cols, "amount_out")).fillna(0).abs() * mult if cols.get("amount_out") else 0
        rev = out.copy(); rev["kind"] = "revenue"; rev["amount"] = a_in
        exp = out.copy(); exp["kind"] = "expense"; exp["amount"] = a_out
        recs = pd.concat([rev[rev["amount"] != 0], exp[exp["amount"] != 0]])
    else:
        amt = amounts(col(df, cols, "amount")) * mult
        bad = amt.isna()
        if bad.any():
            notes.add(f"{label}: skipped {int(bad.sum())} rows without a readable amount")
        out["amount"] = amt
        out = out[~bad]
        df = df[~bad]
        if role == "revenue":
            if (out["amount"] < 0).mean() > 0.5:
                out["amount"] = -out["amount"]
            out["kind"] = "revenue"
            recs = out
        elif role == "expenses":
            if (out["amount"] < 0).mean() > 0.5:
                out["amount"] = -out["amount"]
            out["kind"] = "expense"
            recs = out
        elif role == "ledger":
            lg = src.get("ledger", {})
            rf = lg.get("refund_if")
            is_refund = _match(df[rf["column"]], rf["values"]) if rf and rf.get("column") in df.columns else pd.Series(False, index=df.index)
            if lg.get("sign") == "positive_is_revenue":
                out["kind"] = out["amount"].map(lambda v: "revenue" if v > 0 else "expense")
                out["amount"] = out["amount"].abs()
                recs = out
            else:
                rv = lg.get("revenue_if")
                ex = lg.get("expense_if")
                if not rv:
                    raise ValueError(f"{label}: ledger needs ledger.revenue_if, ledger.sign or amount_in/amount_out")
                is_rev = _match(df[rv["column"]], rv["values"])
                is_exp = _match(df[ex["column"]], ex["values"]) if ex else ~is_rev
                other = ~(is_rev | is_exp)
                if other.any():
                    vals = df.loc[other, rv["column"]].map(clean_label).value_counts().head(5).to_dict()
                    notes.add(f"{label}: {int(other.sum())} rows are neither revenue nor expense and were left out ({vals})")
                out["kind"] = None
                out.loc[is_rev, "kind"] = "revenue"
                out.loc[is_exp & ~is_rev, "kind"] = "expense"
                out["amount"] = out["amount"].abs()
                recs = out[out["kind"].notna()]
            if is_refund.any():
                # refunds reduce revenue rather than counting as a cost
                idx = is_refund[is_refund].index.intersection(out.index)
                out.loc[idx, "kind"] = "revenue"
                out.loc[idx, "amount"] = -out.loc[idx, "amount"].abs()
                recs = out[out["kind"].notna()]
                notes.add(f"{label}: {len(idx)} refunds counted as negative revenue")
        else:
            raise ValueError(f"unknown role {role}")
    if cols.get("date"):
        nod = recs["date"].isna()
        if nod.any():
            notes.add(f"{label}: {int(nod.sum())} rows have no readable date (counted in totals, not in monthly charts)")
    return recs[REC_COLS] if len(recs) else pd.DataFrame(columns=REC_COLS), n0


def wide_records(df, src, notes, label, default_year):
    wide = src.get("wide", {})
    label_col = wide.get("label_column") or df.columns[0]
    mult = float(src.get("amount_multiplier", 1) or 1)
    month_cols = {}
    for c in df.columns:
        ts = parse_month_label(c, default_year=default_year)
        if ts is not None:
            month_cols[c] = ts
    if not month_cols:
        raise ValueError(f"{label}: no month columns recognised")
    rev_rows = wide.get("revenue_rows", [])
    exp_rows = wide.get("expense_rows", [])
    if isinstance(exp_rows, list):
        exp_rows = {r: r for r in exp_rows}
    labels = df[label_col].map(clean_label)
    known = {str(x).lower() for x in list(rev_rows) + list(exp_rows)}
    unused = [l for l in labels.dropna().unique() if l.lower() not in known and not re.match(r"^(total|итого|всего|net|чист)", l.lower())]
    if unused:
        notes.add(f"{label}: rows not used in the calculation: {', '.join(unused[:8])}")
    recs = []
    for idx, lab in labels.items():
        if not lab:
            continue
        low = lab.lower()
        kind = None
        if low in {r.lower() for r in rev_rows}:
            kind, cat = "revenue", lab
        else:
            for k, v in exp_rows.items():
                if k.lower() == low:
                    kind, cat = "expense", v
        if not kind:
            continue
        for c, ts in month_cols.items():
            v = amounts(pd.Series([df.at[idx, c]])).iloc[0]
            if v is None or (isinstance(v, float) and math.isnan(v)) or v == 0:
                continue
            v = v * mult
            recs.append({"kind": kind, "date": ts, "amount": abs(v) if kind == "expense" else v,
                         "client": None, "project": None,
                         "category": cat if kind == "expense" else None,
                         "vendor": None, "stream": cat if kind == "revenue" else None,
                         "status": None, "due_date": pd.NaT, "description": None,
                         "granularity": "month", "source": label})
    return pd.DataFrame(recs, columns=REC_COLS), len(df)


def hours_records(df, src, notes, label):
    cols = src.get("columns", {})
    df = apply_filters(df, src, notes, label)
    out = pd.DataFrame(index=df.index)
    out["date"] = parse_dates(col(df, cols, "date")) if cols.get("date") else pd.NaT
    for key in ("person", "project", "client"):
        s = col(df, cols, key)
        out[key] = canonical_labels(s, src.get(f"{key}_map")) if s is not None else None
    out["hours"] = amounts(col(df, cols, "hours"))
    rates = {str(k).lower(): float(v) for k, v in (src.get("cost_rates") or {}).items()}
    default_rate = src.get("default_cost_rate")
    if cols.get("cost_rate"):
        out["rate"] = amounts(col(df, cols, "cost_rate"))
    else:
        out["rate"] = out["person"].map(lambda p: rates.get((p or "").lower(), default_rate))
    out["rate"] = pd.to_numeric(out["rate"], errors="coerce")
    out["cost"] = out["hours"] * out["rate"]
    nb = [str(x).lower() for x in (src.get("non_billable_projects") or [])]
    out["billable"] = out["project"].map(lambda p: (p or "").lower() not in nb)
    out = out[out["hours"].notna()]
    out["source"] = label
    return out


# ------------------------------------------------------------- analysis ------

def month_range(start, end):
    months = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return months


def detect_partial_month(recs: pd.DataFrame):
    tx = recs[(recs["granularity"] == "transaction") & recs["date"].notna()]
    if tx.empty:
        return None
    months = tx["date"].map(month_key)
    counts = months.value_counts().sort_index()
    if len(counts) < 3:
        return None
    last = counts.index[-1]
    last_max_day = tx.loc[months == last, "date"].max().day
    typical = counts.iloc[:-1].median()
    if last_max_day <= 20 and counts.iloc[-1] < 0.6 * typical:
        return {"month": last, "last_day_with_data": int(last_max_day)}
    return None


def group_sum(df, key, top=None):
    g = df.dropna(subset=[key]).groupby(key)["amount"].sum().sort_values(ascending=False)
    if top:
        g = g.head(top)
    return g


def analyze(mapping: dict, base_dir: Path) -> dict:
    notes = Notes()
    EXCLUDED.clear()
    BALANCES.clear()
    TOTAL_CHECKS.clear()
    RECONCILIATIONS.clear()
    lang = mapping.get("language", "en")
    period = mapping.get("period") or {}
    default_year = period.get("year") or datetime.now().year
    all_recs, hours = [], []
    sources_used = []
    for i, src in enumerate(mapping["sources"]):
        label = f"{Path(src['file']).name}" + (f" / {src['sheet']}" if src.get("sheet") else "")
        df, header_row = load_source_table(base_dir, src["file"], src.get("sheet"), src.get("header_row"))
        role = src["role"]
        if role == "hours":
            biz = mapping.get("business", {}) or {}
            if not src.get("default_cost_rate") and not (src.get("columns") or {}).get("cost_rate") and biz.get("hour_cost"):
                src = {**src, "default_cost_rate": biz["hour_cost"]}
            h = hours_records(df, src, notes, label)
            hours.append(h)
            sources_used.append({"source": label, "role": role, "rows_used": int(len(h))})
            continue
        if role == "wide_pnl":
            recs, n0 = wide_records(df, src, notes, label, default_year)
        else:
            recs, n0 = long_records(df, src, notes, label)
        all_recs.append(recs)
        sources_used.append({"source": label, "role": role, "rows_read": int(n0), "records_used": int(len(recs))})

    recs = pd.concat(all_recs, ignore_index=True) if all_recs else pd.DataFrame(columns=REC_COLS)
    recs["amount"] = recs["amount"].astype(float)
    recs["date"] = pd.to_datetime(recs["date"], errors="coerce")
    hrs = pd.concat(hours, ignore_index=True) if hours else None

    # ---- period
    if period.get("start"):
        s = pd.Timestamp(period["start"])
        cut = recs["date"].notna() & (recs["date"] < s)
        recs = recs[~cut]
    if period.get("end"):
        e = pd.Timestamp(period["end"])
        cut = recs["date"].notna() & (recs["date"] > e)
        recs = recs[~cut]
    partial = detect_partial_month(recs)
    if partial and mapping.get("partial_month", "exclude") == "exclude":
        pm = partial["month"]
        drop = recs["date"].notna() & (recs["date"].map(lambda d: month_key(d) if not pd.isna(d) else "") == pm)
        recs = recs[~drop]
        if hrs is not None:
            hrs = hrs[~(hrs["date"].notna() & (hrs["date"].map(lambda d: month_key(d) if not pd.isna(d) else "") == pm))]
        notes.add(f"{pm} is incomplete (data only up to day {partial['last_day_with_data']}) — left out so it doesn't look like a drop")

    # duplicates
    dupe_cols = ["kind", "date", "amount", "client", "vendor", "project"]
    tx = recs[recs["granularity"] == "transaction"]
    dups = tx[tx.duplicated(subset=dupe_cols, keep=False) & tx["date"].notna()]
    if len(dups):
        notes.add(f"{len(dups)} rows look like possible duplicates (same date, amount and counterparty) — they are counted, worth a check")

    currency = mapping.get("currency") or "EUR"
    rev = recs[recs["kind"] == "revenue"]
    exp = recs[recs["kind"] == "expense"]

    # outstanding / revenue basis
    unpaid_values = set()
    for src in mapping["sources"]:
        for v in src.get("unpaid_values", []) or []:
            unpaid_values.add(str(v).lower())
    rev_unpaid_mask = rev["status"].map(lambda s: (s or "").lower() in unpaid_values) if unpaid_values else pd.Series(False, index=rev.index)
    outstanding = float(rev.loc[rev_unpaid_mask, "amount"].sum()) if unpaid_values else None
    overdue = None
    if unpaid_values:
        ov = rev_unpaid_mask & rev["status"].map(lambda s: bool(re.search(r"overdue|просроч|late", (s or "").lower())))
        overdue = float(rev.loc[ov, "amount"].sum())
    if mapping.get("revenue_basis") == "paid" and unpaid_values:
        rev = rev[~rev_unpaid_mask]
        notes.add("Revenue counts only paid invoices (cash basis)")
    elif unpaid_values:
        notes.add("Revenue counts all issued invoices, including ones not paid yet")

    total_rev = float(rev["amount"].sum())
    total_exp = float(exp["amount"].sum())
    profit = total_rev - total_exp if len(exp) else None
    margin = profit / total_rev * 100 if total_rev and profit is not None else None
    if not len(exp):
        notes.add("No expense data found — profit and margin can't be calculated yet")

    dated = recs[recs["date"].notna()]
    months = month_range(dated["date"].min(), dated["date"].max()) if len(dated) else []
    monthly = []
    for mk in months:
        r = float(rev.loc[rev["date"].map(lambda d: not pd.isna(d) and month_key(d) == mk), "amount"].sum())
        e = float(exp.loc[exp["date"].map(lambda d: not pd.isna(d) and month_key(d) == mk), "amount"].sum())
        has_e = bool(len(exp))
        monthly.append({"month": mk, "revenue": r2(r), "expenses": r2(e) if has_e else None, "profit": r2(r - e) if has_e else None,
                        "margin": r2((r - e) / r * 100) if r and has_e else None})

    # ---- trends
    trends = None
    n = len(monthly)
    w = 3 if n >= 6 else (2 if n >= 4 else 0)
    if w:
        last, prev = monthly[-w:], monthly[-2 * w:-w]
        def s(rows, k): return sum(x[k] or 0 for x in rows)
        lr, pr_ = s(last, "revenue"), s(prev, "revenue")
        le, pe = s(last, "expenses"), s(prev, "expenses")
        lm = (lr - le) / lr * 100 if lr and len(exp) else None
        pm_ = (pr_ - pe) / pr_ * 100 if pr_ and len(exp) else None
        trends = {"window_months": w, "last_window": [x["month"] for x in last], "previous_window": [x["month"] for x in prev],
                  "revenue_change_pct": pct(lr, pr_), "expenses_change_pct": pct(le, pe),
                  "profit_change_pct": pct(lr - le, pr_ - pe) if (pr_ - pe) > 0 and len(exp) else None,
                  "margin_last_pct": r2(lm), "margin_previous_pct": r2(pm_),
                  "margin_change_pp": r2(lm - pm_) if lm is not None and pm_ is not None else None}

    # ---- breakdowns
    cat_key = "category" if exp["category"].notna().any() else ("vendor" if exp["vendor"].notna().any() else None)
    cost_breakdown = []
    if cat_key:
        g = exp.assign(_k=exp[cat_key].fillna("Uncategorised" if lang != "ru" else "Без категории")).groupby("_k")["amount"].sum().sort_values(ascending=False)
        for k, v in g.items():
            item = {"name": k, "amount": r2(v), "share_pct": r2(v / total_exp * 100) if total_exp else None}
            if trends:
                lastm, prevm = set(trends["last_window"]), set(trends["previous_window"])
                sub = exp[exp[cat_key].fillna("Uncategorised" if lang != "ru" else "Без категории") == k]
                sm = sub["date"].map(lambda d: month_key(d) if not pd.isna(d) else "")
                lw, pw = float(sub.loc[sm.isin(lastm), "amount"].sum()), float(sub.loc[sm.isin(prevm), "amount"].sum())
                item["change_pct"] = pct(lw, pw)
                item["last_window_monthly"] = r2(lw / len(lastm))
                item["prev_window_monthly"] = r2(pw / len(prevm))
            cost_breakdown.append(item)

    def share_list(key, top=12):
        g = group_sum(rev, key)
        return [{"name": k, "revenue": r2(v), "share_pct": r2(v / total_rev * 100) if total_rev else None} for k, v in g.head(top).items()], len(g)

    rev_by_client, n_clients = share_list("client") if rev["client"].notna().any() else ([], 0)
    rev_by_project, n_projects = share_list("project") if rev["project"].notna().any() else ([], 0)
    rev_by_stream, _ = share_list("stream") if rev["stream"].notna().any() else ([], 0)
    concentration = None
    if rev_by_client:
        concentration = {"clients": n_clients, "top1_name": rev_by_client[0]["name"], "top1_share_pct": rev_by_client[0]["share_pct"],
                         "top3_share_pct": r2(sum(x["share_pct"] or 0 for x in rev_by_client[:3]))}

    # ---- project / client profitability
    exp_proj = exp[exp["project"].notna()]
    linked_share = float(exp_proj["amount"].sum()) / total_exp * 100 if total_exp else 0
    proj_client = {}
    if rev["project"].notna().any() and rev["client"].notna().any():
        pc = rev.dropna(subset=["project", "client"]).groupby("project")["client"].agg(lambda s: s.value_counts().index[0])
        proj_client = pc.to_dict()
    labor_by_project = {}
    hours_info = None
    if hrs is not None and len(hrs):
        costed = hrs["cost"].notna().any()
        if costed:
            labor_by_project = hrs.dropna(subset=["project"]).groupby("project")["cost"].sum().to_dict()
        total_h = float(hrs["hours"].sum())
        bill_h = float(hrs.loc[hrs["billable"], "hours"].sum())
        hm = hrs["date"].map(lambda d: month_key(d) if not pd.isna(d) else None)
        people = hrs["person"].nunique() if hrs["person"].notna().any() else None
        cap = mapping.get("monthly_capacity_hours_per_person")
        hours_info = {
            "total_hours": r2(total_h), "billable_hours": r2(bill_h),
            "billable_share_pct": r2(bill_h / total_h * 100) if total_h else None,
            "people": int(people) if people else None,
            "months": int(hm.nunique()),
            "by_person": [{"name": k, "hours": r2(v), "billable_hours": r2(hrs.loc[(hrs["person"] == k) & hrs["billable"], "hours"].sum())}
                          for k, v in hrs.groupby("person")["hours"].sum().sort_values(ascending=False).items()] if people else [],
            "by_project": [{"name": k, "hours": r2(v)} for k, v in hrs.groupby("project")["hours"].sum().sort_values(ascending=False).items()] if hrs["project"].notna().any() else [],
            "costed": bool(costed),
            "labor_cost": r2(hrs["cost"].sum()) if costed else None,
        }
        if cap and people and hm.nunique():
            capacity = cap * people * hm.nunique()
            hours_info["utilization_pct"] = r2(bill_h / capacity * 100)
            hours_info["capacity_hours"] = r2(capacity)
        # effective rate per project where names match revenue projects
        if rev["project"].notna().any() and hrs["project"].notna().any():
            rp = rev.groupby("project")["amount"].sum()
            hp = hrs.groupby("project")["hours"].sum()
            common = [p for p in rp.index if p in hp.index and hp[p] > 0]
            hours_info["effective_rate_by_project"] = sorted(
                [{"name": p, "revenue": r2(rp[p]), "hours": r2(hp[p]), "revenue_per_hour": r2(rp[p] / hp[p])} for p in common],
                key=lambda x: -(x["revenue_per_hour"] or 0))

    project_profit = []
    has_proj_costs = (linked_share >= 40 or bool(labor_by_project)) and rev["project"].notna().any()
    if has_proj_costs:
        rp = rev.groupby("project")["amount"].sum()
        dc = exp_proj.groupby("project")["amount"].sum()
        for p, r in rp.sort_values(ascending=False).items():
            d = float(dc.get(p, 0.0))
            l = float(labor_by_project.get(p, 0.0))
            pr = r - d - l
            project_profit.append({"name": p, "client": proj_client.get(p), "revenue": r2(r), "direct_costs": r2(d),
                                   "team_costs": r2(l) if labor_by_project else None,
                                   "contribution": r2(pr), "margin_pct": r2(pr / r * 100) if r else None})
        orphan = [p for p in dc.index if p not in rp.index]
        if orphan:
            notes.add(f"Costs linked to projects with no revenue in the files: {', '.join(orphan[:5])}")
    client_profit = []
    if project_profit and proj_client:
        cp = {}
        for p in project_profit:
            c = p["client"] or "?"
            x = cp.setdefault(c, {"revenue": 0, "costs": 0})
            x["revenue"] += p["revenue"] or 0
            x["costs"] += (p["direct_costs"] or 0) + (p["team_costs"] or 0)
        tot_contrib = sum(v["revenue"] - v["costs"] for v in cp.values())
        for c, v in sorted(cp.items(), key=lambda kv: -kv[1]["revenue"]):
            contrib = v["revenue"] - v["costs"]
            client_profit.append({"name": c, "revenue": r2(v["revenue"]), "costs": r2(v["costs"]), "contribution": r2(contrib),
                                  "revenue_share_pct": r2(v["revenue"] / total_rev * 100) if total_rev else None,
                                  "contribution_share_pct": r2(contrib / tot_contrib * 100) if tot_contrib else None,
                                  "margin_pct": r2(contrib / v["revenue"] * 100) if v["revenue"] else None})

    # ---- recurring expenses (present in >= 75% of months)
    recurring = []
    if cat_key and len(months) >= 3:
        em = exp.assign(_m=exp["date"].map(lambda d: month_key(d) if not pd.isna(d) else None))
        for k, sub in em.dropna(subset=[cat_key]).groupby(cat_key):
            if sub["_m"].nunique() >= 0.75 * len(months):
                recurring.append({"name": k, "avg_monthly": r2(sub["amount"].sum() / len(months))})
        recurring.sort(key=lambda x: -(x["avg_monthly"] or 0))

    # ---- availability
    avail = {
        "revenue": bool(len(rev)),
        "expenses": bool(len(exp)),
        "dates": len(months) >= 2,
        "months": len(months),
        "revenue_clients": bool(rev_by_client),
        "revenue_projects": bool(rev_by_project),
        "revenue_streams": bool(rev_by_stream) and len(rev_by_stream) > 1,
        "expense_categories": cat_key == "category",
        "expense_vendors_only": cat_key == "vendor",
        "expenses_linked_to_projects_pct": r2(linked_share),
        "project_costs": bool(has_proj_costs),
        "team_hours": hours_info is not None,
        "team_hours_costed": bool(hours_info and hours_info.get("costed")),
        "team_capacity": bool(hours_info and hours_info.get("utilization_pct") is not None),
        "invoice_status": bool(unpaid_values),
        "due_dates": bool(rev["due_date"].notna().any()) if len(rev) else False,
        "recurring_expenses": bool(recurring),
        "cash_balance": bool(BALANCES) or (mapping.get("business", {}) or {}).get("cash_balance") is not None,
    }

    kpis = {"revenue": r2(total_rev), "expenses": r2(total_exp) if len(exp) else None, "profit": r2(profit), "margin_pct": r2(margin),
            "outstanding": r2(outstanding) if outstanding is not None else None,
            "overdue": r2(overdue) if overdue else None,
            "cash_balance": BALANCES[-1]["balance"] if BALANCES else r2((mapping.get("business", {}) or {}).get("cash_balance")),
            "cash_balance_date": BALANCES[-1]["date"] if BALANCES else None,
            "avg_monthly_revenue": r2(total_rev / len(months)) if months else None,
            "avg_monthly_profit": r2(profit / len(months)) if months and profit is not None else None}

    results = {
        "meta": {"generated_at": datetime.now().isoformat(timespec="seconds"), "currency": currency, "language": lang,
                 "business": mapping.get("business", {}),
                 "period": {"start": months[0] if months else None, "end": months[-1] if months else None, "months": len(months)},
                 "sources": sources_used, "partial_month_excluded": partial["month"] if partial and mapping.get("partial_month", "exclude") == "exclude" else None},
        "kpis": kpis,
        "monthly": monthly,
        "trends": trends,
        "cost_breakdown": cost_breakdown,
        "cost_breakdown_by": cat_key,
        "revenue_by_client": rev_by_client,
        "revenue_by_project": rev_by_project,
        "revenue_by_stream": rev_by_stream,
        "concentration": concentration,
        "project_profitability": project_profit,
        "client_profitability": client_profit,
        "hours": hours_info,
        "recurring_expenses": recurring,
        "availability": avail,
        "excluded": EXCLUDED[:],
        "client_gaps": client_gaps(rev, months),
    }
    results["facts"] = build_facts(results)
    results["opportunities"] = opportunities(results, mapping)
    results["data_notes"] = notes.items
    results["sheet_totals"] = TOTAL_CHECKS[:]
    results["reconciliation"] = RECONCILIATIONS[:]
    evaluate(results, recs, hrs, mapping, sorted(unpaid_values))
    return results


def client_gaps(rev, months):
    """For recurring clients (paid in >= half of the months), list months with no revenue
    between their first and last payment — for retainer businesses these are often unpaid
    invoices or paused work."""
    if not len(rev) or not rev["client"].notna().any() or len(months) < 4:
        return []
    out = []
    rm = rev.dropna(subset=["client"]).assign(_m=rev["date"].map(lambda d: month_key(d) if not pd.isna(d) else None)).dropna(subset=["_m"])
    for c, sub in rm.groupby("client"):
        present = sorted(set(sub["_m"]))
        if len(present) < max(3, len(months) / 2):
            continue
        span = [m for m in months if present[0] <= m <= months[-1]]
        missing = [m for m in span if m not in present]
        if missing and len(missing) <= len(span) / 2:
            out.append({"client": c, "months_paid": len(present), "missing_months": missing,
                        "typical_monthly": r2(sub["amount"].sum() / len(present))})
    return out


# ---------------------------------------------------------------- facts ------

def build_facts(R):
    """Numeric observations the agent can turn into human insights. Every number
    here is computed — the agent should reuse these numbers, not invent new ones."""
    f = []
    k, t = R["kpis"], R["trends"]
    if t and t["revenue_change_pct"] is not None:
        def sg(v):
            return "n/a" if v is None else f"{v:+}%"
        txt = f"Last {t['window_months']} months vs previous {t['window_months']}: revenue {sg(t['revenue_change_pct'])}"
        if R["availability"]["expenses"]:
            txt += (f", expenses {sg(t['expenses_change_pct'])}, profit {sg(t['profit_change_pct'])}, "
                    f"margin {t['margin_previous_pct']}% → {t['margin_last_pct']}%")
        f.append({"id": "trend", "numbers": t, "text": txt})
        if t["revenue_change_pct"] > 3 and (t["margin_change_pp"] or 0) < -2:
            f.append({"id": "growth_without_profit", "severity": "warn",
                      "text": f"Revenue grew {t['revenue_change_pct']}% but margin fell by {abs(t['margin_change_pp'])} pp — growth is getting more expensive"})
    for c in R["cost_breakdown"][:8]:
        if t and c.get("change_pct") is not None and (c["share_pct"] or 0) >= 7 and c["change_pct"] - (t["revenue_change_pct"] or 0) >= 10:
            f.append({"id": f"cost_growth:{c['name']}", "severity": "warn",
                      "text": f"'{c['name']}' costs grew {c['change_pct']}% vs revenue {t['revenue_change_pct']}%; now {c['share_pct']}% of all expenses"})
    if R["cost_breakdown"]:
        c = R["cost_breakdown"][0]
        f.append({"id": "largest_cost", "text": f"Largest cost: '{c['name']}' = {c['share_pct']}% of expenses"})
    con = R["concentration"]
    if con and (con["top1_share_pct"] or 0) >= 25:
        f.append({"id": "concentration", "severity": "warn",
                  "text": f"{con['top1_name']} brings {con['top1_share_pct']}% of revenue; top 3 clients = {con['top3_share_pct']}%"})
    m = [x for x in R["monthly"] if x["revenue"] and x["profit"] is not None]
    if len(m) >= 3:
        best = max(m, key=lambda x: x["profit"])
        worst = min(m, key=lambda x: x["profit"])
        f.append({"id": "best_worst_month", "text": f"Best month {best['month']} (profit {best['profit']}), weakest {worst['month']} (profit {worst['profit']})"})
        losses = [x["month"] for x in m if x["profit"] < 0]
        if losses:
            f.append({"id": "loss_months", "severity": "warn", "text": f"Loss-making months: {', '.join(losses)}"})
    if k.get("outstanding"):
        avg = k.get("avg_monthly_revenue") or 0
        f.append({"id": "outstanding", "severity": "warn" if avg and k["outstanding"] > 0.5 * avg else None,
                  "text": f"Unpaid invoices: {k['outstanding']}" + (f" (overdue: {k['overdue']})" if k.get("overdue") else "")
                          + (f" ≈ {round(k['outstanding'] / avg, 1)} months of average revenue" if avg else "")})
    pp = R["project_profitability"]
    if pp:
        withm = [p for p in pp if p["margin_pct"] is not None]
        if withm:
            hi = max(withm, key=lambda p: p["margin_pct"])
            lo = min(withm, key=lambda p: p["margin_pct"])
            f.append({"id": "project_margins", "text": f"Project contribution margin ranges from {lo['margin_pct']}% ({lo['name']}) to {hi['margin_pct']}% ({hi['name']}) — before overheads"})
            neg = [p["name"] for p in withm if p["contribution"] < 0]
            if neg:
                f.append({"id": "loss_projects", "severity": "warn", "text": f"Projects that cost more than they earned: {', '.join(neg)}"})
    for c in R["client_profitability"]:
        rs, cs = c.get("revenue_share_pct"), c.get("contribution_share_pct")
        if rs and cs is not None and rs >= 10 and rs - cs >= 8:
            f.append({"id": f"client_mismatch:{c['name']}", "severity": "warn",
                      "text": f"{c['name']}: {rs}% of revenue but only {cs}% of project contribution"})
    for g in R.get("client_gaps", []):
        f.append({"id": f"client_gap:{g['client']}", "severity": "warn",
                  "text": f"{g['client']} usually brings ~{g['typical_monthly']}/month but nothing in {', '.join(g['missing_months'])} — unpaid invoice or paused work?"})
    ex = [e for e in R.get("excluded", []) if e.get("amount")]
    if ex:
        f.append({"id": "excluded", "text": "Left out of expenses/revenue: " + "; ".join(f"{e['reason']} = {e['amount']}" for e in ex)})
    lp = R["availability"]["expenses_linked_to_projects_pct"]
    if R["project_profitability"] and lp is not None and lp < 60:
        f.append({"id": "unallocated", "text": f"Only {lp}% of expenses are linked to projects — project margins exclude salaries/overheads"})
    h = R["hours"]
    if h:
        f.append({"id": "hours", "text": f"{h['total_hours']} hours logged, {h['billable_share_pct']}% billable"
                  + (f", utilization {h['utilization_pct']}%" if h.get("utilization_pct") is not None else "")})
        er = h.get("effective_rate_by_project") or []
        if len(er) >= 2:
            f.append({"id": "effective_rate", "text": f"Revenue per hour: {er[0]['name']} {er[0]['revenue_per_hour']} vs {er[-1]['name']} {er[-1]['revenue_per_hour']}"})
    return f


# -------------------------------------------------------- opportunities ------

CATALOG = [
    # id, satisfied(avail) -> bool, missing(avail) -> list[str]
    ("profit_and_margin", lambda a: a["expenses"], lambda a: ["expenses (bank export, cost sheet or accounting export)"]),
    ("monthly_trends", lambda a: a["dates"], lambda a: ["dates on transactions"]),
    ("cost_breakdown", lambda a: a["expense_categories"], lambda a: ["expense categories"]),
    ("revenue_by_client", lambda a: a["revenue_clients"], lambda a: ["client name on each invoice / income row"]),
    ("project_profitability", lambda a: a["project_costs"],
     lambda a: (["project on each invoice"] if not a["revenue_projects"] else []) + ["team hours per project", "project-related costs (freelancers, tools) tagged by project"]),
    ("client_profitability", lambda a: a["project_costs"] and a["revenue_clients"],
     lambda a: (["client on each invoice"] if not a["revenue_clients"] else []) + ["costs linked to clients or projects", "team time per client"]),
    ("team_utilization", lambda a: a["team_capacity"],
     lambda a: (["team hours (timesheet)"] if not a["team_hours"] else []) + ["each person's available hours per month"]),
    ("effective_hourly_rate", lambda a: a["team_hours"] and a["revenue_projects"],
     lambda a: (["team hours per project"] if not a["team_hours"] else []) + (["project on each invoice"] if not a["revenue_projects"] else [])),
    ("cash_forecast", lambda a: False,
     lambda a: (["expected payment dates of open invoices"] if a["invoice_status"] else ["unpaid invoices with due dates"])
     + ([] if a.get("cash_balance") else ["current cash balance"]) + ([] if a["recurring_expenses"] else ["list of recurring monthly payments"])),
    ("revenue_by_service", lambda a: a["revenue_streams"], lambda a: ["service / offer type on each invoice"]),
    ("pipeline_forecast", lambda a: False, lambda a: ["deal pipeline with expected value and close date (CRM)"]),
]
PRIORITY = ["profit_and_margin", "monthly_trends", "project_profitability", "client_profitability", "cash_forecast", "team_utilization",
            "effective_hourly_rate", "revenue_by_client", "cost_breakdown", "revenue_by_service", "pipeline_forecast"]


def opportunities(R, mapping):
    a = R["availability"]
    unlocked, locked = [], []
    for oid, ok, missing in CATALOG:
        if ok(a):
            unlocked.append(oid)
        else:
            locked.append({"id": oid, "missing": missing(a)})
    locked.sort(key=lambda x: PRIORITY.index(x["id"]))
    return {"unlocked": unlocked, "locked": locked}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mapping")
    ap.add_argument("--out", default="results.json")
    args = ap.parse_args()
    mp = Path(args.mapping)
    mapping = json.loads(mp.read_text(encoding="utf-8"))
    base = Path(mapping.get("base_dir") or mp.parent)
    res = analyze(mapping, base)
    Path(args.out).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    k = res["kpis"]
    print(json.dumps({"saved": args.out, "kpis": k, "period": res["meta"]["period"],
                      "facts": [x["text"] for x in res["facts"]],
                      "locked": [x["id"] for x in res["opportunities"]["locked"]],
                      "data_notes": res["data_notes"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
