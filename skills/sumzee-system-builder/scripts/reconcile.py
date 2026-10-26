#!/usr/bin/env python3
"""Compare monthly totals between two tables of rows — the owner's source and what was
prepared or loaded. Stops the migration if any month differs by more than 1%.

Usage:
  reconcile.py --a source.csv --a-date Date --a-amount Amount
               --b prepared/Payments.json --b-date "Payment date" --b-amount Amount
               [--b-where Status=Paid] [--a-where Type=Income] [--tolerance 0.01]

Files: .csv (comma or semicolon) or a prepared .json ({"rows": [...]}) or a JSON list.
Dates: ISO, DD.MM.YYYY, DD/MM/YYYY or MM/DD/YYYY (--dayfirst no). Amounts may carry
spaces, commas, currency signs.
"""
import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import datetime


def read_rows(path):
    if path.endswith(".json"):
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d["rows"] if isinstance(d, dict) else d
    with open(path, encoding="utf-8-sig") as f:
        sample = f.read(4096)
        f.seek(0)
        delim = ";" if sample.count(";") > sample.count(",") else ","
        return list(csv.DictReader(f, delimiter=delim))


def month(v, dayfirst=True):
    if not v:
        return None
    s = str(v).strip()[:10]
    fmts = ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y" if dayfirst else "%m/%d/%Y", "%d.%m.%y"]
    for f in fmts:
        try:
            return datetime.strptime(s, f).strftime("%Y-%m")
        except ValueError:
            pass
    return None


def amount(v):
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-]", "", str(v))
    if s.count(",") and s.count("."):
        s = s.replace(",", "") if s.rfind(".") > s.rfind(",") else s.replace(".", "").replace(",", ".")
    elif s.count(","):
        s = s.replace(",", ".") if len(s.split(",")[-1]) <= 2 else s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def totals(rows, dcol, acol, where, dayfirst):
    out, skipped = defaultdict(float), 0
    for r in rows:
        if where and any(str(r.get(k, "")) != v for k, v in where):
            continue
        m = month(r.get(dcol), dayfirst)
        if not m:
            skipped += 1
            continue
        out[m] += amount(r.get(acol))
    return out, skipped


def parse_where(items):
    return [tuple(x.split("=", 1)) for x in items or []]


def main():
    ap = argparse.ArgumentParser()
    for side in ("a", "b"):
        ap.add_argument(f"--{side}", required=True)
        ap.add_argument(f"--{side}-date", required=True)
        ap.add_argument(f"--{side}-amount", required=True)
        ap.add_argument(f"--{side}-where", action="append")
    ap.add_argument("--tolerance", type=float, default=0.01)
    ap.add_argument("--dayfirst", default="yes")
    x = ap.parse_args()
    df = x.dayfirst != "no"
    ta, sa = totals(read_rows(x.a), x.a_date, x.a_amount, parse_where(x.a_where), df)
    tb, sb = totals(read_rows(x.b), x.b_date, x.b_amount, parse_where(x.b_where), df)
    bad = 0
    print(f"{'month':8} {'source':>14} {'loaded':>14} {'diff':>12}")
    for m in sorted(set(ta) | set(tb)):
        a, b = ta.get(m, 0.0), tb.get(m, 0.0)
        diff = b - a
        flag = ""
        if abs(diff) > max(abs(a) * x.tolerance, 0.5):
            flag, bad = "  ⚠", bad + 1
        print(f"{m:8} {a:14,.2f} {b:14,.2f} {diff:12,.2f}{flag}")
    print(f"{'TOTAL':8} {sum(ta.values()):14,.2f} {sum(tb.values()):14,.2f} {sum(tb.values()) - sum(ta.values()):12,.2f}")
    if sa or sb:
        print(f"rows without a readable date: source {sa}, loaded {sb}")
    if bad:
        print(f"\n{bad} month(s) differ by more than {x.tolerance:.0%} — explain before going on")
        sys.exit(1)
    print("\nOK — months match")


if __name__ == "__main__":
    main()
