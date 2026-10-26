#!/usr/bin/env python3
"""Compare the base that was built with schema.json.

Usage: check_built.py schema.json built.json [--ids ids.json]

built.json = the result of list_tables_for_base for the new base, saved as is
(an object with "tables", or just the list). Prints what is missing, extra or of the
wrong type. With --ids, also writes {schema table name: table id, ...} plus field ids,
which batch_records.py needs.
"""
import argparse
import json
import sys

from common import API_TYPE, airtable_table_name, inverse_fields, load_json, save_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("schema")
    ap.add_argument("built")
    ap.add_argument("--ids")
    a = ap.parse_args()
    schema = load_json(a.schema)
    built = load_json(a.built)
    btables = built.get("tables", built) if isinstance(built, dict) else built
    by_name = {t["name"]: t for t in btables}
    inv = inverse_fields(schema)

    problems, ids = [], {"tables": {}, "fields": {}}
    for t in schema["tables"]:
        an = airtable_table_name(schema, t)
        bt = by_name.get(an) or by_name.get(t["name"])
        if not bt:
            problems.append(f"MISSING table {an}")
            continue
        ids["tables"][t["name"]] = bt["id"]
        bf = {f["name"]: f for f in bt["fields"]}
        ids["fields"][t["name"]] = {f["name"]: f["id"] for f in bt["fields"]}
        expected = {}
        for f in t["fields"]:
            expected[f["name"]] = API_TYPE.get(f["type"], f["type"])
        for i in inv.get(t["name"], []):
            expected[i["name"]] = "multipleRecordLinks"
        for name, typ in expected.items():
            if name not in bf:
                problems.append(f"MISSING field {an}.{name} ({typ})")
            elif bf[name]["type"] != typ:
                problems.append(f"TYPE {an}.{name}: expected {typ}, got {bf[name]['type']}")
        for name in bf:
            if name not in expected:
                problems.append(f"EXTRA field {an}.{name} ({bf[name]['type']}) — not in schema "
                                "(an unrenamed reverse link, or added by hand?)")
        prim = bt.get("primaryFieldId")
        if prim and t["fields"] and ids["fields"][t["name"]].get(t["fields"][0]["name"]) != prim:
            problems.append(f"PRIMARY {an}: primary field is not '{t['fields'][0]['name']}'")
    for bt in btables:
        if bt["name"] not in {airtable_table_name(schema, t) for t in schema["tables"]} | {t["name"] for t in schema["tables"]}:
            problems.append(f"EXTRA table {bt['name']}")

    if a.ids:
        save_json(ids, a.ids)
        print(f"wrote {a.ids}")
    if problems:
        print("\n".join(problems))
        print(f"\n{len(problems)} differences")
        sys.exit(1)
    print("OK — the base matches schema.json")


if __name__ == "__main__":
    main()
