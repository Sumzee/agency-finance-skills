"""Generate the fictional "Lumen Creative" sample data (15-person agency, EUR, Jan-Sep 2026).

Everything here is invented. Run: python3 make_sample_data.py  -> writes into ./lumen-creative/data/
Needs: openpyxl
"""
import csv
import os
import random
from datetime import date, timedelta

from openpyxl import Workbook

random.seed(7)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lumen-creative", "data")
os.makedirs(OUT, exist_ok=True)
MONTHS = list(range(1, 10))  # Jan-Sep 2026

# ---- clients: monthly retainers + one-off projects ---------------------------------
RETAINERS = {  # client: (monthly fee, hours/month actually spent on average)
    "Halcyon Hotels": (13500, 150),
    "Opal Fitness": (8500, 70),
    "Northpoint Dental": (6500, 85),
    "Verde Organics": (10000, 95),
    "Kestrel Logistics": (7500, 60),
}
PROJECTS = [  # (client, project, month, fee, hours spent)
    ("Halden Retail", "Halden — rebrand", 2, 56000, 1500),
    ("Halden Retail", "Halden — rebrand (phase 2)", 5, 33000, 900),
    ("Marlow Bank", "Marlow — app launch campaign", 3, 69000, 520),
    ("Marlow Bank", "Marlow — Q3 campaign", 7, 61000, 470),
    ("Saffron Kitchens", "Saffron — website", 4, 42000, 360),
    ("Brio Travel", "Brio — summer campaign", 5, 28000, 230),
    ("Tidewater Energy", "Tidewater — annual report", 6, 36000, 300),
    ("Saffron Kitchens", "Saffron — menu shoot", 8, 14000, 120),
    ("Corvo Wines", "Corvo — launch video", 9, 26000, 210),
]

inv_rows, n = [], 1001
for m in MONTHS:
    for client, (fee, _) in RETAINERS.items():
        if client == "Kestrel Logistics" and m in (4, 7):
            continue  # missed retainer invoices
        status = "Paid"
        if m == 9:
            status = "Sent"
        inv_rows.append([f"LC-{n}", date(2026, m, 3), client, f"{client.split()[0]} — retainer",
                         "Retainer", fee, status, date(2026, m, 3) + timedelta(days=30)]); n += 1
    for client, proj, pm, fee, _ in PROJECTS:
        if pm == m:
            first, second = round(fee * 0.5), fee - round(fee * 0.5)
            inv_rows.append([f"LC-{n}", date(2026, m, 10), client, proj, "Project", first, "Paid",
                             date(2026, m, 10) + timedelta(days=30)]); n += 1
            m2 = min(m + 2, 9)
            st = "Paid" if m2 <= 7 else ("Overdue" if client == "Tidewater Energy" else "Sent")
            inv_rows.append([f"LC-{n}", date(2026, m2, 24), client, proj, "project", second, st,
                             date(2026, m2, 24) + timedelta(days=30)]); n += 1
inv_rows.append([f"LC-{n}", date(2026, 6, 15), "Brio Travel", "Brio — extra banners", "Project", 3200,
                 "Cancelled", date(2026, 7, 15)]); n += 1
inv_rows.append([f"LC-{n}", date(2026, 8, 12), "Opal Fitness", "Opal — event photos", "project", 2400,
                 "Overdue", date(2026, 9, 11)]); n += 1
inv_rows.sort(key=lambda r: r[1])

wb = Workbook()
ws = wb.active
ws.title = "Invoices"
ws.append(["Lumen Creative — invoices 2026 (export from invoicing tool)"])
ws.append(["Invoice #", "Date", "Client", "Project", "Service", "Amount (€)", "Status", "Due"])
for r in inv_rows:
    ws.append(r)
ws.append([])
ws.append(["", "", "", "", "Total", sum(r[5] for r in inv_rows), "", ""])
wb.save(os.path.join(OUT, "invoices.xlsx"))

# ---- bank export: costs, owner dividends, own transfers, client receipts -------------
raw = []
def add(d, desc, amt):
    raw.append((d, desc, round(amt, 2)))

for m in MONTHS:
    for r in inv_rows:  # client receipts (shown in bank but revenue is counted from invoices)
        if r[6] == "Paid" and r[1].month == m:
            add(date(2026, m, min(r[1].day + 21, 28)), f"PAYMENT FROM {r[2].upper()} {r[0]}", r[5])
    add(date(2026, m, 25), "SALARY RUN — PAYROLL LTD", -round(random.uniform(45500, 47000), 2))
    add(date(2026, m, 12), "UPWORK FREELANCERS", -round(random.uniform(5500, 9000), 2))
    add(date(2026, m, 18), "CONTRACTOR — M. ROSSI MOTION", -round(random.uniform(2500, 5200), 2))
    add(date(2026, m, 1), "OFFICE RENT — HARBOUR SPACES", -6200.00)
    add(date(2026, m, 5), "ADOBE / FIGMA / NOTION SUBS", -round(random.uniform(1900, 2300), 2))
    add(date(2026, m, 9), "GOOGLE ADS (CLIENT SPEND REBILL)", -round(random.uniform(800, 1600), 2))
    add(date(2026, m, 20), "ACCOUNTANT — FIGURES & CO", -900.00)
    add(date(2026, m, 27), "DIVIDEND TO OWNER", -8000.00)
    if m in (3, 6, 9):
        add(date(2026, m, 15), "TRANSFER TO OWN SAVINGS ACCOUNT", -10000.00)
        add(date(2026, m, 16), "VAT PAYMENT", -round(random.uniform(14000, 17000), 2))
    if m == 5:
        add(date(2026, 5, 14), "LAPTOPS — TECHSTORE", -7400.00)
raw.sort(key=lambda r: r[0])
bank, balance = [], 130000.0
for d, desc, amt in raw:
    balance += amt
    bank.append([d.isoformat(), desc, f"{amt:.2f}", f"{balance:.2f}"])
with open(os.path.join(OUT, "bank_export.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["Date", "Description", "Amount", "Balance"])
    w.writerows(bank)

# ---- timesheet: hours per person per project per month -------------------------------
people = ["Ana", "Ben", "Chloe", "Dan", "Eli", "Femi", "Gia", "Hugo", "Iris", "Jon", "Kai", "Lea"]
hours = []
proj_by_month = {m: [] for m in MONTHS}
for client, (fee, h) in RETAINERS.items():
    for m in MONTHS:
        proj_by_month[m].append((client, f"{client.split()[0]} — retainer", h * random.uniform(0.85, 1.15)))
for client, proj, pm, fee, h in PROJECTS:
    span = [mm for mm in (pm, pm + 1, pm + 2) if mm in MONTHS]
    for mm in span:
        proj_by_month[mm].append((client, proj, h / len(span)))
for m in MONTHS:
    for client, proj, h in proj_by_month[m]:
        left = h
        while left > 1:
            chunk = min(left, random.choice([8, 12, 16, 24]))
            hours.append([date(2026, m, random.randint(1, 28)).isoformat(), random.choice(people), client, proj,
                          round(chunk, 1)])
            left -= chunk
    for p in people:
        hours.append([date(2026, m, 28).isoformat(), p, "", "Internal", random.choice([10, 14, 18])])
hours.sort(key=lambda r: r[0])
with open(os.path.join(OUT, "timesheet.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["date", "person", "client", "project", "hours"])
    w.writerows(hours)

print("invoices:", len(inv_rows), "bank rows:", len(bank), "timesheet rows:", len(hours),
      "closing balance:", round(balance, 2))
