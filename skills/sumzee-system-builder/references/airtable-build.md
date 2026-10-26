# Building the base through the Airtable connector

Build only from `plan.json` (made by `build_plan.py` from the confirmed `schema.json`).
Never improvise fields in Airtable — change `schema.json`, re-validate, re-plan.

## 0. Before anything

- **Connector present?** Look for `mcp__Airtable__*` tools (load them with tool search
  if they are deferred). None → stop and show the owner how to connect (below).
- **Workspace access.** `list_workspaces`. Empty list = the connector was given access
  to individual bases only; a new base can't be created. Ask the owner to reconnect
  Airtable and grant a whole workspace (Settings → Connectors → Airtable → reconnect →
  choose the workspace). Several workspaces → ask which one.
- **Confirm before creating.** One line: "Создаю базу «X» в пространстве «Y»: N таблиц,
  M полей. Создаю?" Creating is easy to undo (the owner can delete the base), but it
  is still their account — ask once, then build without further questions.
- **Never** call delete tools, and never modify a base you didn't create in this
  session. An existing base of the owner is read-only: a migration source.

### If the owner has no Airtable yet

1. Sign up at airtable.com (the free plan is enough to start: 1,000 records per base,
   100 automation runs a month, up to 5 editors).
2. In Claude: Settings → Connectors → Airtable → Connect; when Airtable asks what to
   share, pick the whole workspace.
3. Come back to this chat and say "готово". The schema and plan are already saved.

## 1. create_base

`create_base(workspaceId, name, tables)` with `plan.create_base.tables` as is: every
table with its plain fields, primary field first. Save the response — it has the table
ids. If the call is too big or fails on one table, create the base with the first
table and add the rest with `create_table` one by one.

Build a map `{schema table name → table id}` (`plan.table_names` maps schema names to
the Airtable names). Replace every `@Table` in the plan with its id.

## 2. links

For each item in `plan.links`: `create_field(baseId, tableId, field)` with
`field.options.linkedTableId` = the target table id. Airtable creates the reverse field
in the target table automatically, named after the source table.

## 3. renames

For each item in `plan.renames`, find the reverse field Airtable created and rename it
to `rename_to` with `update_field`:
- the `create_field` response for the link usually carries
  `options.inverseLinkFieldId` — use it;
- otherwise read the target table (`get_table_schema` or `list_tables_for_base`) and
  take the new `multipleRecordLinks` field named after the source table
  (`airtable_default_name`, possibly with a number: "Оплаты 2").
Do all renames before step 4 — rollups refer to these names.

## 4. computed

`plan.computed` is already in dependency order: create each with `create_field` as
is. Lookups and rollups reference link fields and target fields **by name**; formulas
reference fields by `{Name}`.

If a field is refused:
- read the error; most often a referenced field name is wrong (fix `schema.json`) or a
  formula function is unsupported;
- fix in `schema.json`, re-run `validate_schema.py` and `build_plan.py`, continue from
  the failed item (fields already created stay);
- if a formula still fails after two tries, create it simplified and add a line to
  `notes_for_team` / tell the owner what is simplified. Never loop.

## 5. check

`list_tables_for_base(baseId)` → save the result as `built.json` →
`check_built.py schema.json built.json --ids ids.json`. Fix every MISSING / TYPE /
EXTRA line (usually an unrenamed reverse link) until it prints OK. `ids.json` is needed
for loading records.

## 6. automations (proposals)

`plan.automations` are described in words (trigger + action). Tell the owner what each
one does and why, in one line each. Only after a yes: `get_create_automation_instructions`
once, then `create_automation`. Automations are created **switched off**; the owner
turns them on in Airtable after a look. On the free plan mention the 100 runs a month.

## 7. forms (instructions, not built)

The connector doesn't make fields required. For each table in `plan.required_fields`,
tell the owner (or the Sumzee team) to make a form in Airtable with those fields marked
required — that's where people should enter data. One short list, not a tutorial.

## Base link

`https://airtable.com/<baseId>` — pass it to `render_schema.py --stage built --base-url`.

## Useful facts

- Primary field types allowed through the API: text, long text, number, currency,
  percent, date, date-time, email, url, phone, duration, barcode, auto-number.
- `create_records_for_table` takes up to 50 records per call; keys are field ids;
  selects by option name; links as arrays of record ids; dates `YYYY-MM-DD`.
  Keep `typecast` off — a wrong select value should fail, not create a new option.
- Rollup formulas: `SUM(values)`, `MAX(values)`, `MIN(values)`, `COUNTA(values)`,
  `ARRAYJOIN(values)`, `AND(values)`.
- Field names are unique per table, case-insensitive.
