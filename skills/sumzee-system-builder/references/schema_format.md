# schema.json — format

One file describes the whole system. The schema page is drawn from it, the base is
built from it, and Profit Agent later reads it to find revenue, costs and clients in the
base. Never build anything in Airtable that is not in `schema.json` first.

`scripts/compose_schema.py` writes a draft from a template; you edit the draft for the
client; `scripts/validate_schema.py` checks it.

```json
{
  "version": 1,
  "business": {
    "name": "Brightside",
    "model": "projects",
    "language": "ru",
    "currency": "EUR",
    "currencies": ["EUR"],
    "plan": "free"
  },
  "groups": [
    {"id": "sales", "label": "Продажи"},
    {"id": "work", "label": "Работа"},
    {"id": "money", "label": "Деньги"},
    {"id": "costs", "label": "Расходы"}
  ],
  "tables": [
    {
      "name": "Projects",
      "label": "Проекты",
      "group": "sales",
      "description": "Один проект = один договор с клиентом.",
      "entered_by": "Менеджер проекта, при подписании договора",
      "estimated_records": 60,
      "fields": [
        {"name": "Project", "type": "singleLineText", "description": "Название проекта"},
        {"name": "Client", "type": "link", "to": "Clients", "inverse": "Projects",
         "description": "Клиент. Новый клиент — сначала в таблицу Clients."},
        {"name": "Status", "type": "singleSelect",
         "choices": ["Lead", "Active", "Done", "Cancelled"]},
        {"name": "Contract value", "type": "currency", "required": true},
        {"name": "Paid", "type": "rollup", "via": "Payments", "field": "Amount",
         "formula": "SUM(values)", "description": "Сумма оплат по проекту. Не трогать."},
        {"name": "Margin", "type": "formula",
         "formula": "{Paid} - {Team cost} - {Direct costs}"}
      ]
    }
  ],
  "questions": [
    {"text": "Какая маржа у каждого проекта", "tables": ["Projects", "Hours", "Expenses"]}
  ],
  "roles": {
    "revenue": {"table": "Payments", "amount": "Amount", "date": "Payment date",
                "status": "Status", "paid_values": ["Paid"]},
    "expenses": {"table": "Expenses", "amount": "Amount", "date": "Date",
                 "category": "Category"},
    "client": {"table": "Clients", "name": "Client"},
    "project": {"table": "Projects", "name": "Project"},
    "hours": {"table": "Hours", "hours": "Hours", "cost": "Cost"},
    "exclude": [{"table": "Expenses", "field": "Type", "values": ["Internal transfer"]}]
  },
  "notes_for_team": [],
  "todo_for_sumzee": []
}
```

## Tables

- `name` — technical name in English, used in formulas (keep it stable).
- `label` — the owner's word for it, in their language. The schema page shows labels.
- `group` — one of `groups[].id`. Groups are the blocks on the schema page.
- `description` — what one record is. Goes into Airtable as the table description.
- `entered_by` — who adds records and how: by hand, through a form, by import,
  automatically. Shown on the schema page.
- `estimated_records` — per year, for the free-plan check. Optional but ask for it.
- The **first field is the primary field** and must be one of: singleLineText,
  multilineText, number, currency, percent, date, dateTime, email, url, phoneNumber,
  autoNumber, duration. (A formula cannot be primary through the API.)

## Field types

Plain fields (created with the base):

| `type` | Extra keys | Notes |
|---|---|---|
| `singleLineText`, `multilineText`, `email`, `url`, `phoneNumber`, `multipleAttachments`, `singleCollaborator`, `autoNumber`, `createdTime` | — | |
| `number`, `percent` | `precision` (default 0 / 0) | |
| `currency` | `precision` (default 2), `symbol` (default from `business.currency`) | |
| `date` | `format`: `european` (default), `iso`, `us`, `friendly`, `local` | |
| `checkbox` | — | |
| `singleSelect`, `multipleSelects` | `choices`: list of names | |

Computed / linked fields (created after the base, in this order):

| `type` | Keys | Notes |
|---|---|---|
| `link` | `to` (table name), `inverse` (name of the field Airtable creates in the other table) | Define each link **once**, on the "many" side (Payments → Project). Airtable creates the reverse field itself. |
| `lookup` | `via` (a link field in this table), `field` (field in the linked table) | |
| `rollup` | `via`, `field`, `formula` (e.g. `SUM(values)`) | |
| `count` | `via` | |
| `formula` | `formula` | Reference fields as `{Field name}`. Formulas may reference other formulas — the build orders them. |

Common optional keys on any field: `description` (always write one for computed fields
and for anything a person might be tempted to edit), `required` (true → the field is
required on the entry form and gets a "missing value" check; Airtable itself does not
enforce it in the grid).

## questions

5–7 questions the owner will be able to answer, in their words, each with the tables
it comes from. These are the "Что вы сможете видеть" block on the schema page — the
most important part of the page for the owner.

## roles

Tells Profit Agent where things live. Fill it whenever the tables exist: revenue,
expenses, client, project, hours, and what to exclude (internal transfers, owner draws).

## notes_for_team / todo_for_sumzee

- `notes_for_team` — Sumzee mode only: simplifications, open questions for the client.
- `todo_for_sumzee` — owner mode: concrete things worth finishing for *this* business
  (a form for hours on the phone, bank import, a partner dashboard). Shown at the end.
