#!/usr/bin/env python3
"""Turn schema.json into an ordered build plan for the Airtable connector.

Usage: build_plan.py schema.json --out plan.json [--summary]

Phases (each item is ready to pass to the connector after replacing @Table with the
real table id):
  1. create_base   — one call: all tables with their plain fields (primary first)
  2. links         — create_field multipleRecordLinks, one per link (needs table ids)
  3. renames       — read the base, rename the reverse link fields Airtable created
  4. computed      — lookups, rollups, counts, formulas in dependency order
  5. automations   — proposals only; create switched off after the owner agrees
"""
import argparse
import json

from common import airtable_table_name, formula_refs, load_json, save_json, table_map

DATE_FMT = {"european": "european", "iso": "iso", "us": "us", "friendly": "friendly", "local": "local"}


def desc(f):
    d = f.get("description")
    return {"description": d[:20000]} if d else {}


def plain_field(f, schema):
    t = f["type"]
    out = {"name": f["name"], "type": t, **desc(f)}
    if t == "number":
        out["options"] = {"precision": int(f.get("precision", 0))}
    elif t == "percent":
        out["options"] = {"precision": int(f.get("precision", 0))}
    elif t == "currency":
        out["options"] = {"precision": int(f.get("precision", 2)),
                          "symbol": f.get("symbol") or schema["business"].get("currency", "€")}
    elif t == "date":
        out["options"] = {"dateFormat": {"name": DATE_FMT.get(f.get("format", "european"), "european")}}
    elif t == "dateTime":
        out["options"] = {"dateFormat": {"name": DATE_FMT.get(f.get("format", "european"), "european")},
                          "timeFormat": {"name": "24hour"}, "timeZone": f.get("timeZone", "Europe/Berlin")}
    elif t == "checkbox":
        out["options"] = {"icon": "check", "color": "greenBright"}
    elif t in ("singleSelect", "multipleSelects"):
        out["options"] = {"choices": [{"name": c} for c in f["choices"]]}
    return out


def computed_field(f):
    t = f["type"]
    if t == "formula":
        return {"name": f["name"], "type": "formula", "options": {"formula": f["formula"]}, **desc(f)}
    if t == "lookup":
        return {"name": f["name"], "type": "multipleLookupValues",
                "options": {"recordLinkFieldId": f["via"], "fieldIdInLinkedTable": f["field"]}, **desc(f)}
    if t == "rollup":
        return {"name": f["name"], "type": "rollup",
                "options": {"recordLinkFieldId": f["via"], "fieldIdInLinkedTable": f["field"],
                            "formula": f["formula"]}, **desc(f)}
    if t == "count":
        return {"name": f["name"], "type": "count", "options": {"recordLinkFieldId": f["via"]}, **desc(f)}
    return {"name": f["name"], "type": t, **desc(f)}  # createdTime, lastModifiedTime


def order_computed(schema):
    """Topological order of computed fields across tables."""
    tables = table_map(schema)
    from common import link_target
    nodes, deps = [], {}
    for t in schema["tables"]:
        for f in t["fields"]:
            if f["type"] in ("formula", "lookup", "rollup", "count", "createdTime", "lastModifiedTime"):
                key = (t["name"], f["name"])
                nodes.append(key)
                d = set()
                if f["type"] == "formula":
                    d = {(t["name"], r) for r in formula_refs(f["formula"])}
                elif f["type"] in ("lookup", "rollup"):
                    target = link_target(schema, t["name"], f["via"])
                    d = {(target, f["field"])}
                deps[key] = d
    computed = set(nodes)
    order, state = [], {}

    def visit(n):
        if state.get(n) == 2:
            return
        if state.get(n) == 1:
            raise SystemExit(f"dependency cycle at {n}")
        state[n] = 1
        for d in deps.get(n, ()):
            if d in computed:
                visit(d)
        state[n] = 2
        order.append(n)

    for n in nodes:
        visit(n)
    fields = {(t["name"], f["name"]): f for t in schema["tables"] for f in t["fields"]}
    return [(tn, fields[(tn, fn)]) for tn, fn in order]


def build(schema):
    tables = table_map(schema)
    at = {t["name"]: airtable_table_name(schema, t) for t in schema["tables"]}
    base_tables = []
    for t in schema["tables"]:
        fields = [plain_field(f, schema) for f in t["fields"] if f["type"] not in
                  ("link", "lookup", "rollup", "count", "formula", "createdTime", "lastModifiedTime")]
        tdesc = t.get("description") or ""
        if at[t["name"]] != t["name"]:
            tdesc = f"{tdesc}\n\n[schema: {t['name']}]".strip()
        base_tables.append({"name": at[t["name"]], "description": tdesc[:20000], "fields": fields})

    links, renames = [], []
    for t in schema["tables"]:
        for f in t["fields"]:
            if f["type"] != "link":
                continue
            links.append({
                "table": t["name"], "airtable_table": at[t["name"]], "table_id": f"@{t['name']}",
                "field": {"name": f["name"], "type": "multipleRecordLinks",
                          "options": {"linkedTableId": f"@{f['to']}"}, **desc(f)},
            })
            renames.append({
                "table": f["to"], "airtable_table": at[f["to"]], "table_id": f"@{f['to']}",
                "created_by": f"{t['name']}.{f['name']}",
                "airtable_default_name": at[t["name"]],
                "rename_to": f.get("inverse") or at[t["name"]],
            })

    computed = []
    for tn, f in order_computed(schema):
        computed.append({"table": tn, "airtable_table": at[tn], "table_id": f"@{tn}", "field": computed_field(f)})

    required = {}
    for t in schema["tables"]:
        r = [f["name"] for f in t["fields"] if f.get("required")]
        if r:
            required[at[t["name"]]] = r

    base_name = schema["business"].get("name") or "Sumzee"
    lang = schema["business"].get("language", "ru")
    suffix = " — система учёта" if lang == "ru" else " — operations"
    return {
        "base_name": base_name + suffix,
        "table_names": at,
        "create_base": {"name": base_name + suffix, "tables": base_tables},
        "links": links,
        "renames": renames,
        "computed": computed,
        "automations": schema.get("automations", []),
        "required_fields": required,
        "counts": {"tables": len(base_tables),
                   "plain_fields": sum(len(t["fields"]) for t in base_tables),
                   "links": len(links), "computed": len(computed)},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("schema")
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args()
    plan = build(load_json(a.schema))
    save_json(plan, a.out)
    c = plan["counts"]
    print(f"wrote {a.out}: {c['tables']} tables, {c['plain_fields']} plain fields in create_base, "
          f"{c['links']} links, {c['computed']} computed fields, {len(plan['automations'])} automations to propose")
    if a.summary:
        print("\nlinks:")
        for l in plan["links"]:
            print(f"  {l['table']}.{l['field']['name']} → {l['field']['options']['linkedTableId'][1:]}")
        print("computed order:")
        for c_ in plan["computed"]:
            print(f"  {c_['table']}.{c_['field']['name']} ({c_['field']['type']})")


if __name__ == "__main__":
    main()
