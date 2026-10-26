#!/usr/bin/env python3
"""Step 1 — look at the client's files and describe their structure.

Usage:
    python inspect_files.py FILE_OR_FOLDER [FILE_OR_FOLDER ...] [--rows 3]

Prints a compact JSON description of every sheet: detected header row,
columns with type, examples, totals, low-cardinality values, and guesses for
which column is the date / amount / client / project / category etc.
It never prints the whole table — only what is needed to build mapping.json.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (amounts, canonical_labels, clean_label, currency_in,  # noqa: E402
                    drop_empty, is_total_row, parse_dates, parse_month_label,
                    read_raw_tables, table_with_header)

SUPPORTED = {".xlsx", ".xlsm", ".xls", ".csv", ".tsv"}

ROLE_WORDS = {
    "date": ["date", "дата", "day", "paid on", "invoice date", "issued", "период", "תאריך", "datum", "month", "месяц"],
    "due_date": ["due", "срок", "payment date expected", "due date", "оплатить до"],
    "amount": ["amount", "sum", "сумма", "total", "value", "net", "gross", "price", "стоимость", "סכום", "betrag", "€", "$", "usd", "eur"],
    "amount_in": ["income", "inflow", "credit", "приход", "поступлен", "доход", "in"],
    "amount_out": ["outflow", "debit", "расход", "списан", "out", "spent"],
    "client": ["client", "customer", "клиент", "заказчик", "account", "company", "לקוח", "kunde", "brand"],
    "project": ["project", "проект", "job", "deal", "сделка", "campaign", "פרויקט", "engagement"],
    "category": ["category", "категор", "статья", "expense type", "cost type", "type of", "group", "группа", "קטגוריה", "account name"],
    "vendor": ["vendor", "supplier", "payee", "поставщик", "контрагент", "получатель", "merchant", "ספק"],
    "status": ["status", "статус", "paid?", "оплачен", "state", "stage"],
    "type": ["type", "тип", "direction", "вид", "kind", "in/out"],
    "hours": ["hours", "часы", "часов", "hrs", "duration", "time spent", "שעות"],
    "person": ["employee", "person", "сотрудник", "исполнитель", "team member", "freelancer", "name", "who", "עובד"],
    "rate": ["rate", "ставка", "hourly", "cost per hour"],
    "description": ["description", "описание", "comment", "коммент", "notes", "note", "memo", "назначение", "details", "תיאור"],
    "invoice": ["invoice", "счет", "счёт", "inv", "חשבונית"],
}


def guess_roles(columns: list[dict]) -> dict:
    guesses = {}
    for role, words in ROLE_WORDS.items():
        best = None
        for c in columns:
            name = c["name"].lower()
            hit = any((w in name) if len(w) > 3 else re.search(rf"\b{re.escape(w)}\b", name) for w in words)
            if not hit:
                continue
            kind = c["kind"]
            if role in ("date", "due_date") and kind != "date":
                continue
            if role in ("amount", "amount_in", "amount_out", "hours", "rate") and kind != "number":
                continue
            if role in ("client", "project", "category", "vendor", "status", "type", "person", "description") and kind != "text":
                continue
            best = best or c["name"]
        if best:
            guesses[role] = best
    # a lone date / a lone number column is a strong hint even without keywords
    dates = [c["name"] for c in columns if c["kind"] == "date"]
    nums = [c["name"] for c in columns if c["kind"] == "number"]
    if "date" not in guesses and dates:
        guesses["date"] = dates[0]
    if "amount" not in guesses and len(nums) == 1 and nums[0] not in guesses.values():
        guesses["amount"] = nums[0]
    return guesses


def describe_column(name: str, s: pd.Series, rows: int) -> dict:
    non_null = s.dropna()
    non_null = non_null[non_null.map(lambda v: str(v).strip() != "")]
    n = len(non_null)
    info = {"name": name, "filled": int(n)}
    if n == 0:
        info["kind"] = "empty"
        return info
    nums = amounts(non_null)
    dates = parse_dates(non_null)
    num_share = nums.notna().mean()
    date_share = dates.notna().mean()
    is_datetime_typed = pd.api.types.is_datetime64_any_dtype(s) or non_null.map(
        lambda v: hasattr(v, "year") and hasattr(v, "month")).mean() > 0.8
    if is_datetime_typed or (date_share >= 0.8 and num_share < 0.8):
        info["kind"] = "date"
        d = dates.dropna()
        info["min"] = str(d.min().date()) if len(d) else None
        info["max"] = str(d.max().date()) if len(d) else None
        info["unparsed"] = int(n - len(d))
    elif num_share >= 0.8:
        info["kind"] = "number"
        v = nums.dropna()
        info["sum"] = round(float(v.sum()), 2)
        info["min"] = round(float(v.min()), 2)
        info["max"] = round(float(v.max()), 2)
        info["negatives"] = int((v < 0).sum())
        info["unparsed"] = int(n - len(v))
        cur = {currency_in(x) for x in non_null if isinstance(x, str)} - {None}
        cur |= {currency_in(name)} - {None}
        if cur:
            info["currency_hint"] = sorted(cur)
    else:
        info["kind"] = "text"
        labels = canonical_labels(non_null)
        vc = labels.value_counts()
        info["distinct"] = int(len(vc))
        if len(vc) <= 25:
            info["values"] = {str(k): int(v) for k, v in vc.items()}
        else:
            info["top_values"] = {str(k): int(v) for k, v in vc.head(8).items()}
        raw_distinct = non_null.map(clean_label).nunique()
        if raw_distinct > len(vc):
            info["merged_spellings"] = int(raw_distinct - len(vc))
    info["examples"] = [str(x)[:40] for x in non_null.drop_duplicates().head(3).tolist()]
    return info


def inspect_sheet(file: Path, sheet: str, raw: pd.DataFrame) -> dict:
    raw = drop_empty(raw)
    if raw.empty:
        return {"file": file.name, "sheet": sheet, "empty": True}
    body, header_row = table_with_header(raw, None)
    total_idx = [int(i) for i, r in body.iterrows() if is_total_row(r)]
    clean = body.drop(index=total_idx) if total_idx else body
    cols = [describe_column(c, clean[c], len(clean)) for c in clean.columns]
    cols = [c for c in cols if c.get("kind") != "empty"]
    month_cols = [c for c in body.columns if parse_month_label(c, default_year=2000) is not None]
    layout = "wide (months are columns)" if len(month_cols) >= 3 else "long (one row per transaction/record)"
    out = {
        "file": file.name,
        "path": str(file),
        "sheet": sheet,
        "header_row": header_row,
        "data_rows": int(len(clean)),
        "layout": layout,
        "columns": cols,
        "guesses": guess_roles(cols),
    }
    if len(month_cols) >= 3:
        out["month_columns"] = [str(c) for c in month_cols]
        first = clean.columns[0]
        out["row_labels"] = [clean_label(v) for v in clean[first].tolist() if clean_label(v)][:60]
    if total_idx:
        out["total_rows_excluded"] = len(total_idx)
    if header_row > 1:
        above = [" ".join(clean_label(v) for v in row if clean_label(v))
                 for row in raw.iloc[:header_row - 1].itertuples(index=False)]
        above = [a for a in above if a]
        if above:
            out["text_above_header"] = [a[:80] for a in above[:3]]
    return out


def collect(paths: list[str]) -> list[Path]:
    files = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            files += sorted(f for f in p.rglob("*") if f.suffix.lower() in SUPPORTED and not f.name.startswith(("~$", ".")))
        elif p.exists():
            files.append(p)
        else:
            print(json.dumps({"error": f"not found: {p}"}), file=sys.stderr)
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    args = ap.parse_args()
    report = []
    for f in collect(args.paths):
        try:
            for sheet, raw in read_raw_tables(f).items():
                report.append(inspect_sheet(f, sheet, raw))
        except Exception as e:  # keep going: one broken file shouldn't stop the analysis
            report.append({"file": f.name, "error": f"{type(e).__name__}: {e}"})
    print(json.dumps(report, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
