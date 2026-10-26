# Sumzee System Builder · v0.1

Claude skill. Interviews a small-business owner, shows their operations & finance
system as a schema, builds it in Airtable through the connector and moves their
history in. Pairs with Sumzee Profit Agent (before: diagnosis; after: monthly view on
the built base).

Install: Claude → Customize → Skills → upload the ZIP. Needs the Airtable connector
(with access to a whole workspace) for stages 5–6; stages 1–4 work without it.

## Layout
- `SKILL.md` — workflow and principles
- `references/` — interview, Airtable rules, build order, migration, schema format
- `templates/` — core + models (projects ✓, subscriptions & passes · retainers · launches — drafts) + modules
- `scripts/` — compose_schema · validate_schema · render_schema · build_plan · check_built · batch_records · reconcile (Python 3, stdlib)
- `config.json` — booking link, defaults

## Quick check
```
cd scripts
python3 compose_schema.py --list
python3 compose_schema.py --model projects --modules budgets --out /tmp/s.json
python3 validate_schema.py /tmp/s.json
python3 render_schema.py /tmp/s.json --out /tmp/s.html
python3 build_plan.py /tmp/s.json --out /tmp/plan.json --summary
```

## Known gaps (v0.1)
- Not yet run end-to-end on a live Airtable workspace (offline pipeline tested).
- Subscriptions template built from screenshots of the choir base (Payments, Attendance);
  Members / Subscriptions / Price reconstructed.
- Retainers and launches templates have no reference base.
- Field names are English (formulas, Profit Agent); table names and descriptions follow the owner's language.
