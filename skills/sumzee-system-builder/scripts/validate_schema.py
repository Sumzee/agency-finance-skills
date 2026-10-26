#!/usr/bin/env python3
"""Check schema.json against the format and the Airtable rules (references/airtable-rules.md).

Usage: validate_schema.py schema.json [--json]
Exit code 1 if there are errors. Warnings don't block, but read them — most of them are
the traps from BEsmart and the choir base.
"""
import json
import re
import sys
from collections import defaultdict

from common import (ALL_TYPES, COMPUTED_TYPES, PLAN_LIMITS, PRIMARY_OK, all_field_names,
                    formula_refs, link_target, load_json, table_map)

YEAR = re.compile(r"(?<![\d.])20[1-3]\d(?![\d.])")


def validate(schema):
    errors, warnings, info = [], [], []
    E, W, I = errors.append, warnings.append, info.append
    tables = table_map(schema)
    groups = {g["id"] for g in schema.get("groups", [])}
    names = all_field_names(schema)

    if len(tables) != len(schema["tables"]):
        E("duplicate table names")
    if "{{" in json.dumps(schema, ensure_ascii=False):
        E("unresolved {{placeholder}} left in the schema")

    for t in schema["tables"]:
        tn = t["name"]
        if t.get("group") not in groups:
            E(f"{tn}: group '{t.get('group')}' is not in groups")
        if not t.get("fields"):
            E(f"{tn}: no fields")
            continue
        if not t.get("description"):
            W(f"{tn}: no table description")
        if not t.get("entered_by"):
            W(f"{tn}: entered_by is empty — who adds these records?")
        first = t["fields"][0]
        if first.get("type") not in PRIMARY_OK:
            E(f"{tn}: primary (first) field '{first['name']}' has type {first.get('type')}; "
              f"must be one of {sorted(PRIMARY_OK)}")
        seen = set()
        for f in t["fields"]:
            fn, ft = f["name"], f.get("type")
            low = fn.lower()
            if low in seen:
                E(f"{tn}.{fn}: duplicate field name")
            seen.add(low)
            if ft not in ALL_TYPES:
                E(f"{tn}.{fn}: unknown type {ft}")
                continue
            if ft in ("singleSelect", "multipleSelects") and not f.get("choices"):
                E(f"{tn}.{fn}: select without choices")
            if ft == "link":
                if f.get("to") not in tables:
                    E(f"{tn}.{fn}: links to unknown table {f.get('to')}")
                elif not f.get("inverse"):
                    W(f"{tn}.{fn}: no inverse name — Airtable will name the reverse field itself")
            if ft in ("lookup", "rollup", "count"):
                via = f.get("via")
                target = link_target(schema, tn, via) if via else None
                if not target:
                    E(f"{tn}.{fn}: via '{via}' is not a link field in {tn}")
                elif ft != "count" and f.get("field") not in names.get(target, {}):
                    E(f"{tn}.{fn}: field '{f.get('field')}' not found in {target}")
                if ft == "rollup" and not f.get("formula"):
                    E(f"{tn}.{fn}: rollup without formula (e.g. SUM(values))")
            if ft == "formula":
                formula = f.get("formula", "")
                if not formula:
                    E(f"{tn}.{fn}: empty formula")
                for ref in formula_refs(formula):
                    if ref not in names[tn]:
                        E(f"{tn}.{fn}: formula references unknown field {{{ref}}}")
                if YEAR.search(formula):
                    E(f"{tn}.{fn}: hardcoded year in formula — compute it (YEAR(TODAY())) instead")
            if ft in COMPUTED_TYPES and ft != "link" and not f.get("description"):
                W(f"{tn}.{fn}: computed field without description (say it is computed / do not edit)")

        # one field per person / per category pattern
        buckets = defaultdict(list)
        for f in t["fields"]:
            parts = re.split(r"[ _]+", f["name"].strip(), maxsplit=1)
            if len(parts) == 2 and len(parts[1]) > 3:
                buckets[parts[1].lower()].append(f["name"])
        for rest, fs in buckets.items():
            if len(fs) >= 3:
                W(f"{tn}: {len(fs)} fields look like one per person/category ({', '.join(fs[:4])}…). "
                  "Use a linked table and a rollup instead of a column per item.")
        if len(t["fields"]) > 40:
            W(f"{tn}: {len(t['fields'])} fields — probably too wide for people to fill")

    # formula dependency cycles inside a table
    for t in schema["tables"]:
        deps = {f["name"]: [r for r in formula_refs(f.get("formula", ""))]
                for f in t["fields"] if f.get("type") == "formula"}
        state = {}

        def visit(n, stack):
            if state.get(n) == 1:
                E(f"{t['name']}: formula cycle {' → '.join(stack + [n])}")
                return
            if state.get(n) == 2 or n not in deps:
                return
            state[n] = 1
            for d in deps[n]:
                visit(d, stack + [n])
            state[n] = 2

        for n in deps:
            visit(n, [])

    # inverse name collisions
    for target, fs in names.items():
        own = {f["name"].lower() for f in tables[target]["fields"]}
        from common import inverse_fields
        for inv in inverse_fields(schema).get(target, []):
            if inv["name"].lower() in own:
                E(f"{target}: inverse field '{inv['name']}' (from {inv['from_table']}) clashes with an own field")
        inv_names = [i["name"].lower() for i in inverse_fields(schema).get(target, [])]
        dup = {n for n in inv_names if inv_names.count(n) > 1}
        for d in dup:
            E(f"{target}: two links create the same inverse field name '{d}' — set different `inverse`")

    # roles
    for role, r in schema.get("roles", {}).items():
        if role == "exclude":
            for x in r:
                if x["table"] not in tables or x["field"] not in names[x["table"]]:
                    E(f"roles.exclude: {x['table']}.{x['field']} not found")
            continue
        tname = r.get("table")
        if tname not in tables:
            E(f"roles.{role}: table {tname} not found")
            continue
        for k, v in r.items():
            if k in ("table", "paid_values"):
                continue
            if isinstance(v, str) and v not in names[tname]:
                E(f"roles.{role}.{k}: field {tname}.{v} not found")

    if not schema.get("questions"):
        W("no questions — the schema page needs 'what you will be able to see'")
    for q in schema.get("questions", []):
        for tn in q.get("tables", []):
            if tn not in tables:
                W(f"question '{q.get('text')}' mentions unknown table {tn}")

    # records vs plan
    plan = schema.get("business", {}).get("plan", "free")
    limit = PLAN_LIMITS.get(plan, 1000)
    est = {t["name"]: t.get("estimated_records") for t in schema["tables"]}
    known = {k: v for k, v in est.items() if isinstance(v, (int, float))}
    if known:
        total = sum(known.values())
        msg = f"estimated records per year: {int(total)} (plan {plan}, limit {limit} per base)"
        (W if total > limit * 0.8 else I)(msg)
        missing = [k for k, v in est.items() if v is None]
        if missing:
            I("no estimate for: " + ", ".join(missing))
    else:
        I("no estimated_records yet — ask how many clients/payments/expenses per year")

    req = [f"{t['name']}.{f['name']}" for t in schema["tables"] for f in t["fields"] if f.get("required")]
    I(f"required fields (forms + checks): {len(req)}")
    I(f"tables: {len(tables)}, fields: {sum(len(t['fields']) for t in schema['tables'])}")
    return errors, warnings, info


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    schema = load_json(sys.argv[1])
    errors, warnings, info = validate(schema)
    if "--json" in sys.argv:
        print(json.dumps({"errors": errors, "warnings": warnings, "info": info}, ensure_ascii=False, indent=2))
    else:
        for x in errors:
            print("ERROR  ", x)
        for x in warnings:
            print("WARN   ", x)
        for x in info:
            print("info   ", x)
        print(f"\n{len(errors)} errors, {len(warnings)} warnings")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
