# Sumzee methodology — how to read results.json and write the narrative

Thresholds are in `thresholds.json` (skill root). The script applies them; this file
explains what the numbers mean so your words match Sumzee's point of view.

## Business models

| model | owner's main question | what goes on top |
|---|---|---|
| projects | which projects really earn, which eat team time | project margin after team time, utilization |
| retainers | how stable is the base, are we working more than we're paid for | recurring revenue, client × month payments, overservice |
| subscriptions | are we growing, how many customers do we lose | MRR growth, churn |
| launches | what each launch really brings, what we live on between launches | profit per launch, revenue between launches |

`results.json → model`: `detected` (from the data), `stated` (owner), `primary`,
`secondary` (a mixed business), `mismatch`. If the owner's stated model and the data
disagree, say so gently in `verdict_text` ("you called it project work, but 80% of revenue
comes from the same clients every month — that's a retainer business, and it's measured
differently").

## Metrics

`results.json → metrics`: each has `group` (core or a model), `value`, `unit`, `status`
(green / yellow / red / locked), `critical`, `rule` (the thresholds), `missing` (for locked).

Core — every business:
- **Margin after owner pay** (critical). Profit after whatever the owner takes out. A 30%
  margin before a 2 000/month owner draw can be 12% after — that is the real number.
- **Cash runway** (critical). Balance ÷ monthly outflow (expenses + owner draws).
- **Largest client's share**. Above 40% one client can sink the business.
- **Overdue invoices vs monthly revenue**. Invoices 30+ days unpaid.
- **Team costs vs revenue**. Salaries + freelancers ÷ revenue.

Model metrics are in the `thresholds.json` groups; their names show on the dashboard.

## Verdict

`results.json → verdict`: `healthy`, `attention`, `risk` or `insufficient`, with
`confidence` (share of metrics that could be computed) and the `red` / `yellow` lists.
Rules: any critical red or two reds → risk; one red or two yellows → attention; otherwise
healthy. Without any critical metric and low confidence → insufficient. Do not soften or
override the verdict; explain it.

`verdict_text` (narrative): 1–2 sentences — *why* this verdict, in the owner's words, with
the one or two numbers that drive it. E.g. "The studio pays its bills and you, but thinly:
after your draws it keeps 12.7%, and cash covers under two months of costs."

## Checks

`results.json → checks`: reconciliation with bank balance, owner pay, non-expenses left
out, typical costs not seen (taxes, insurance, accountant, bank fees), the sheet's own
Total rows, incomplete month, sanity of the margin. The dashboard words them
automatically; override a line in `narrative.checks` only when you know something the
script doesn't (`[{"id": "missing_costs", "text": "..."}]`).

## Actions

`results.json → actions`: candidates with a computed `effect` (`monthly` or `one_off`).
Pick 2–3 for `narrative.actions`, most money first, and write each as
`{"title": "Chase the two missing retainer payments", "text": "why / how, one sentence",
"effect": <the computed number>, "kind": "one_off"}`.
Rules:
- Only use effects from `results.json` (or from a small pandas calculation you ran on the
  same data). No action without a number — if you can't compute the effect, it's a
  locked card, not an action.
- `price_plus_5` is a scenario — use it only when nothing stronger is there, or as the third.
- Actions are concrete: who/what/when, not "optimise costs".

## Locked cards

Pick 2–4 for `narrative.locked`, in this order: locked **critical** core metrics (cash
runway, margin after owner) → locked metrics of the primary model the owner cares about →
catalog views (`cash_forecast`, `project_profitability`, …). Locked metric ids work as card
ids (`"id": "overservice_pct"`). Write the card's text for this business: name their
clients, projects, columns.

## Honesty rules

- A threshold is a norm for small service businesses, not a law. If a metric is red for a
  reason the owner explained (a planned investment month), say so.
- Never state a benchmark ("agencies usually…") that isn't in `thresholds.json`.
