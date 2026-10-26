# Airtable design rules

Every schema is checked against these before the owner sees it (`validate_schema.py`
catches most of them automatically; the rest are on you). Each rule comes from a real
base — BEsmart (projects, 20 tables) or the choir (passes and attendance).

| # | Rule | What goes wrong otherwise | Where we learned it |
|---|---|---|---|
| 1 | No field per person, per category or per month. Put the items in their own table and sum with a rollup. | A new employee or category = new columns and formulas. BEsmart had ~30 per-employee hours fields and 4 fields × 10 categories in Budgets. | BEsmart: Projects, Budgets |
| 2 | No hardcoded years or dates in formulas and filters. Use `YEAR(TODAY())`, `DATETIME_FORMAT(TODAY(), 'YYYY-MM')`. | In January the numbers quietly break. | BEsmart: Budgets filtered on 2026 |
| 3 | No manual step that a number silently depends on. If something must be picked, an automation picks it; if it's missing, a visible ⚠ check shows it. | "Month of conversion" not picked → amount in EUR = 0, nobody notices. | BEsmart: exchange rates |
| 4 | Key fields (date, amount, link to client/project) are required on forms, and a `Check` formula flags them in the grid. | A payment without a date falls out of every month; revenue is understated. | Choir: Payments |
| 5 | Values that change over time (hour cost, exchange rate, price) are copied onto the record when it is created, not looked up live. | A salary change rewrites the margin of every past project. | BEsmart: net cost via automation (good) |
| 6 | Formulas never read a link field directly. Use a technical rollup: `SUM(values)` for numbers, `ARRAYJOIN(values)` for text, `MAX(values)` for dates. | A link is an array; formulas on it break or concatenate. | BEsmart: prjct_id lookup (good) |
| 7 | Every table and every computed or sensitive field has a description: what it is, who fills it, "computed — do not edit". | In six months nobody knows what can be deleted. | BEsmart (good) |
| 8 | No leftover or experimental fields and tables. If unsure, don't add it. | Confusion, stray links, accidental edits. | Choir: self-links in Attendance; BEsmart: "пауза 4" |
| 9 | Personal cards and cash are Accounts with a holder and a visible balance. | Nobody knows where the money is. | Choir: cash kept on founders' personal cards |
| 10 | Internal transfers and owner draws are recorded, but marked with `Kind` and excluded from revenue/costs by the formula, not by memory. | Revenue is inflated by money moved between own accounts. | BEsmart: Payments rules |
| 11 | Design for the record limit. One record per event only where the event matters; otherwise a monthly summary. Free plan: 1,000 records per base. | The base hits the limit and blocks new entries. | Choir: 1,429 attendance records |
| 12 | Closed lists are single-select options, not free text. Old options are kept (renamed or hidden), not deleted. | "Freelance", "freelancers ", "Фриланс" = three categories. | Profit Agent test data |
| 13 | Each link is defined once, on the "many" side (Payment → Client). Name the reverse field clearly (`inverse`). | Duplicated links that disagree; reverse fields named "Table 2". | General |
| 14 | One base per business. Several legal entities = a select or an Entities table, not separate bases. | Totals across bases are impossible without exports. | BEsmart: Core + Venture in one base (good) |
| 15 | The primary field is something a person recognises: a name, or an auto-number for transactional tables. Never a formula through the API. | Links show meaningless ids; creation fails. | API constraint |
| 16 | Keep tables narrow enough to fill: a person entering a payment should see ≤ 10 fields on the form. | Nobody fills wide forms; data stops. | BEsmart: Projects with 60+ fields |

## Naming

- Field names in English (formulas reference them; Profit Agent reads them). Table
  names in the owner's language when `business.table_names = "label"` (default for
  non-English) — tables are never referenced by name in formulas.
- Descriptions, select options the owner reads every day, and the schema page — in the
  owner's language. Keep `Kind`/`Status` options in English: formulas compare them.
  If the owner insists on translated options, change the formulas to match and re-run
  `validate_schema.py`.

## Simplify first

When in doubt, leave it out. A field that nobody fills is noise; a table that nobody
fills breaks every formula that depends on it. The core + the model tables + one module
is usually enough for a first version. Everything else goes to `todo_for_sumzee`.
