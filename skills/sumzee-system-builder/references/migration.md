# Moving the history in

The owner should open the base and see **their** clients, projects and money — that's
the moment that works. Empty tables don't.

## 1. Count before loading

From the source files estimate records per table (pandas: row counts after cleaning).
Write the prepared files (step 3) and run:

```bash
python <scripts>/batch_records.py count prepared/ --schema schema.json
```

Default plan is **free: 1,000 records per base, all tables together.** Always tell the
owner the number before loading: «получится примерно 640 записей из 1 000 — останется
360 на новые данные». Leave at least ~30% headroom for the coming months, or say
plainly that the free plan will run out soon.

## 2. If it doesn't fit — offer a selection

Offer options with numbers for *their* data, recommend one, let them choose (combine
freely):

| Criterion | Example | What is lost |
|---|---|---|
| Period | only the last 3, 6 or 12 months row by row | older history as rows |
| Data type | money (payments, expenses) row by row; hours or attendance as monthly totals | per-person / per-session detail in the past |
| Status | only active projects / members; closed ones as one record each or not at all | history of closed deals |
| Importance | top clients row by row, the rest as "Other" | detail on small clients |
| Summary | everything older than the period = one record per month and category | row detail, not the trend |

A monthly summary is a normal record: e.g. Expenses `Expense = "Сводка: Software,
2025-11"`, Date = last day of the month, Amount = the month total, Kind/Category as
usual. Payments the same with a `Comment` "monthly summary". Profit Agent then still
sees the trend.

If even the minimal selection doesn't fit — say so: the Team plan is needed ($20 per
editor per month, billed annually, 50,000 records per base — prices change, check
airtable.com/pricing), or keep the old history in the spreadsheet.

## 3. Prepare

Clean with pandas into `prepared/<Table>.json` (format in `batch_records.py`), using
schema field names. Same rules as Profit Agent:

- header rows, "Total"/«Итого» rows, empty rows — out;
- dates → `YYYY-MM-DD`; amounts → numbers (spaces, commas, currency signs removed);
  refunds positive with `Kind = Refund`;
- merge spelling variants of clients and categories before creating records
  (show the merge list to the owner when it's not obvious);
- transfers between own accounts → `Kind = Internal transfer`; owner pay via
  draws/dividends → Expenses `Kind = Owner draw`; cancelled invoices → `Status =
  Cancelled` or skip;
- bank exports: categorise big items with rules; don't load the same money twice from
  an invoice list *and* a bank statement — one is the source of payments, the other
  (if loaded at all) goes to Transactions;
- `_key` on every row that others link to (client name, project code, invoice number);
- never write computed fields (they are skipped anyway).

Unclear mapping → one message with your defaults and max 3 questions, like Profit
Agent does. Show the column mapping as a short table «ваша колонка → поле в базе».

## 4. Load

```bash
python <scripts>/batch_records.py batches prepared/ --schema schema.json --ids ids.json --idmap idmap.json --out batches/
```

For every batch file printed: `create_records_for_table(baseId, tableId, records)`
with the file's `tableId` and `records`; save the response; then

```bash
python <scripts>/batch_records.py learn batches/<file>.json response.json --idmap idmap.json
```

Tables that link to others print "waiting" until those are loaded and learned — run
`batches` again after each round. If a call fails midway, `idmap.json` shows what is
already in: never re-send a batch that succeeded (that duplicates records).

Report progress in one line per table, not per batch.

## 5. Reconcile

For money tables compare monthly totals of the source and the prepared rows:

```bash
python <scripts>/reconcile.py --a source.csv --a-date Date --a-amount Amount \
  --b prepared/Payments.json --b-date "Payment date" --b-amount Amount --b-where Status=Paid
```

Then read 2–3 computed totals in the base (`list_records_for_table` with a few fields:
Categories.Spent total, Clients.Total paid, Accounts.Balance) and compare with the
prepared totals. A difference over 1% — stop, find the reason, explain it. Account
balance vs the real bank balance is the strongest check: ask the owner for today's
balance if they know it.

## 6. Report

Short, in the owner's language:
- перенесено: N записей (клиенты X, оплаты Y, расходы Z …), осталось K из лимита;
- что не перенесено и почему (строки без даты, «Итого», дубли — с количеством);
- что сверено: суммы по месяцам совпали / где расхождение и чем объясняется.

## Existing Airtable base as the source

Read it (`list_tables_for_base`, `list_records_for_table` with only the needed fields,
page by page), write the rows to files, and treat them like any other source. Never
write to the old base.
