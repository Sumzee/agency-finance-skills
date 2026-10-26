# mapping.json — format

`mapping.json` tells `analyze.py` what each file means. Write it after reading the
`inspect_files.py` output. Use exact column names as printed by inspect (they are
case-sensitive) and the `header_row` it reported.

## Top level

```json
{
  "business": {
    "name": "Brightside Studio",
    "type": "Marketing / creative agency",
    "revenue_model": "Client projects + retainers",
    "team_size": "11-20",
    "wants": "Which clients/projects make the most money",
    "data_location": "Google Sheets",
    "model": "retainers",
    "owner_pay": {"method": "draws", "monthly_outside_data": 0},
    "hour_cost": 28,
    "target_hourly_rate": 60,
    "cash_balance": 18500,
    "backlog_amount": 42000
  },
  "team_categories": ["Salaries", "Freelancers"],
  "retainer_hours": {"Halcyon Hotels": 20, "Opal Fitness": 15},
  "currency": "EUR",
  "language": "en",
  "revenue_basis": "invoiced",
  "partial_month": "exclude",
  "period": {"start": "2026-01-01", "end": "2026-08-31", "year": 2026},
  "monthly_capacity_hours_per_person": 120,
  "base_dir": "/mnt/user-data/uploads",
  "sources": [ ... ]
}
```

| key | meaning |
|---|---|
| `currency` | ISO code of the money in the files. If files use different currencies, do **not** mix them: map one currency, mention the rest in narrative `data_notes`. |
| `language` | `en` or `ru` for built-in labels; any other code works if narrative.json provides `labels`. |
| `revenue_basis` | `invoiced` (default: every issued invoice counts; unpaid ones are shown separately) or `paid` (cash basis). |
| `partial_month` | `exclude` (default) drops a last month that is clearly incomplete; `include` keeps it. |
| `period` | optional filter. `year` is used for month headers without a year ("Jan", "Feb"). |
| `monthly_capacity_hours_per_person` | only if the owner told you; enables utilization. |
| `business.model` | what the owner said: `projects`, `retainers`, `subscriptions` or `launches`. The script also detects the model from the data and flags a mismatch; the stated model wins. Leave out if the owner didn't say. |
| `business.owner_pay` | how the owner pays themself. If the owner's own salary is a visible line in the data ("Owner salary"), exclude it with `"owner": true` too (method `salary`) — it is then shown as owner pay, so profit before/after owner pay stays meaningful. `method`: `salary` (already in payroll), `draws` (transfers/dividends — mark those rows with `"owner": true` in `exclude_if`/`rules`), `both`, `none`, or `unknown`. `monthly_outside_data`: what the owner takes that isn't in these files at all. Drives "profit before / after owner pay". |
| `business.hour_cost` | cost of one team hour, **from the owner** (never estimated from payroll). Used to cost timesheet hours. |
| `business.target_hourly_rate` | the rate the owner aims to earn per hour, from onboarding. Enables "real rate vs target". |
| `business.cash_balance` | current cash balance if the owner told you and there's no bank balance column. |
| `business.backlog_amount` | signed but not yet delivered work (projects), if the owner told you. |
| `team_categories` | expense categories that are team costs (salaries, freelancers, contractors). If omitted, detected by keywords. |
| `retainer_hours` | hours included in each client's retainer per month, if the owner told you. |
| `base_dir` | where the files are. Default: the folder of mapping.json — so if mapping.json lives in a scratch folder, set `base_dir` to the uploads folder (or use absolute `file` paths). |

## Sources

Each source is one sheet (or one CSV). `role` is one of:

### `revenue` — income / invoices
```json
{"file": "finance.xlsx", "sheet": "Income", "header_row": 2, "role": "revenue",
 "columns": {"date": "Date", "amount": "Amount (€)", "client": "Client", "project": "Project",
             "status": "Status", "stream": "Service", "due_date": "Due"},
 "unpaid_values": ["Sent", "Overdue"],
 "exclude_if": [{"column": "Status", "values": ["Cancelled", "Draft"]}]}
```

### `expenses` — costs
```json
{"file": "finance.xlsx", "sheet": "Costs", "header_row": 1, "role": "expenses",
 "columns": {"date": "Date", "amount": "Amount", "category": "Category", "vendor": "Vendor", "project": "Project"},
 "category_map": {"Freelance": "Freelancers", "SaaS tools": "Software"},
 "exclude_if": [{"column": "Category", "values": ["Transfer", "Owner draw", "Loan"]}]}
```
Signs are handled automatically (a sheet of negative numbers is read as costs).

### `ledger` — one table with both income and costs (bank export, cashbook)
Tell the script how to tell them apart — one of:
```json
"ledger": {"revenue_if": {"column": "Type", "values": ["Income", "Приход"]},
           "expense_if": {"column": "Type", "values": ["Expense", "Расход"]}}
"ledger": {"sign": "positive_is_revenue"}
"columns": {"amount_in": "Credit", "amount_out": "Debit", ...}
```
Refunds: add `"refund_if": {"column": "Counterparty", "values": ["Refund", "Возврат"]}` inside
`ledger` — those rows become negative revenue (not a cost), so revenue and margin are net
of refunds and the refunds metric works.

If `expense_if` is omitted, every non-revenue row is an expense — only do that if there are no transfers/loans/owner movements mixed in (use `exclude_if` for those).

### `wide_pnl` — months as columns, line items as rows
```json
{"file": "PnL.xlsx", "sheet": "P&L 2026", "header_row": 2, "role": "wide_pnl",
 "wide": {"label_column": "Line item",
          "revenue_rows": ["Revenue - Retainers", "Revenue - Projects"],
          "expense_rows": {"Salaries": "Team", "Freelancers": "Freelancers", "Software": "Software"}}}
```
List only real line items — never "Total revenue", "Gross profit", "Net profit" or other computed rows (they would be double-counted). `expense_rows` can be a list or a {row label: category} map to merge rows.

### `hours` — timesheet
```json
{"file": "timesheet.csv", "role": "hours",
 "columns": {"date": "date", "person": "person", "project": "project", "hours": "hours", "cost_rate": "Rate"},
 "default_cost_rate": 35, "cost_rates": {"Dana": 45},
 "non_billable_projects": ["Internal", "Admin"]}
```
Cost rates (what an hour costs the business) come from a column, the owner, or not at all — never invent them. With costed hours, project profitability includes team time. Project names must match the revenue sheet to link them — use `project_map` to align spellings.

## Common options (any source)

- `columns.*` — any subset; unmapped fields are simply unavailable.
- `<field>_map` (`category_map`, `client_map`, `project_map`, `vendor_map`, `stream_map`, `person_map`) — merge spellings: `{"freelance": "Freelancers"}`. Case and extra spaces are merged automatically already.
- `exclude_if` / `include_if` — lists of `{"column": ..., "values": [...]}`, case-insensitive.
- `amount_multiplier` — e.g. `1000` if the sheet is "in thousands".
- `unpaid_values` — statuses meaning "invoice not paid yet".

Total/subtotal rows ("Total", "Итого", "Всего", …) are dropped automatically.

## Text rules — for bank exports and other tables without clean columns

When categories, clients or "not really an expense" rows only show up inside a
description, use `rules` (case-insensitive "contains" match; the first matching rule wins):

```json
"rules": [
  {"column": "Memo", "contains": ["DIVIDEND", "OWNER"], "exclude": true, "owner": true, "reason": "owner's pay"},
  {"column": "Memo", "contains": ["OWN ACCOUNT", "SAVINGS"], "exclude": true, "reason": "transfer between own accounts"},
  {"column": "Memo", "contains": ["SALARY", "GUSTO"], "set": {"category": "Salaries"}},
  {"column": "Memo", "contains": ["FIVERR", "CONTRACTOR"], "set": {"category": "Freelancers"}},
  {"column": "Memo", "contains": ["ACME LTD"], "set": {"client": "Acme"}}
]
```

`set` can fill `category`, `client`, `project`, `vendor`, `stream`. Excluded amounts are
totalled in `results.json` → `excluded`, so you can say e.g. "you took out $12k in owner
draws" with a real number.

If a bank export has a running balance, map it as `columns.balance` — the latest balance
shows on the dashboard and counts as "current cash balance" for the cash-forecast card. Aim to categorise the
big amounts; a small "Uncategorised" remainder is fine. Exclusions are listed in the
dashboard's "How this was calculated".

`"owner": true` on an exclusion (in `rules` or `exclude_if`) marks those rows as the owner's
pay: they stay out of expenses but are shown as "profit after owner pay", and the cash
runway counts them as outflow.
