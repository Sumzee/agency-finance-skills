#!/usr/bin/env python3
"""Prepare the owner's history for loading through the Airtable connector.

You first clean the owner's data (pandas) into one JSON file per table in a folder,
using the field names from schema.json:

  prepared/Clients.json
  {"table": "Clients", "rows": [{"_key": "Nordlicht", "Client": "Nordlicht", "Email": "..."}]}

  prepared/Payments.json
  {"table": "Payments", "rows": [{"_key": "inv-2026-014", "Client": "Nordlicht",
     "Amount": 4200, "Kind": "Client payment", "Status": "Paid", "Payment date": "2026-03-12"}]}

Link fields hold the _key of the linked record (or a list of keys). Dates are ISO
YYYY-MM-DD, money and numbers are plain numbers, selects are option names.

Commands:
  count    prepared/ --schema schema.json
           rows per table, total vs the plan's record limit
  batches  prepared/ --schema schema.json --ids ids.json --idmap idmap.json --out batches/
           one file per 50 records, in dependency order (linked tables first); links
           resolved through idmap.json; stops if a link can't be resolved
  learn    batches/Payments-001.json response.json --idmap idmap.json
           after create_records_for_table: remember which record id each _key got

Load tables in the order `batches` prints. Run `batches` again before each table that
links to tables you just loaded — the new ids must be in idmap.json first.
"""
import argparse
import glob
import json
import os
import sys

from common import PLAN_LIMITS, load_json, save_json, table_map

SKIP_TYPES = {"formula", "rollup", "lookup", "count", "autoNumber", "createdTime", "lastModifiedTime"}


def load_prepared(folder):
    out = {}
    for p in sorted(glob.glob(os.path.join(folder, "*.json"))):
        d = load_json(p)
        out[d["table"]] = d
    return out


def load_order(schema, present):
    """Tables that others link to come first."""
    deps = {t["name"]: {f["to"] for f in t["fields"] if f["type"] == "link"} for t in schema["tables"]}
    order, seen = [], set()

    def visit(n, stack=()):
        if n in seen or n in stack:
            return
        for d in deps.get(n, ()):
            if d != n:
                visit(d, stack + (n,))
        seen.add(n)
        order.append(n)

    for n in deps:
        visit(n)
    return [n for n in order if n in present]


def cmd_count(a):
    schema = load_json(a.schema)
    prep = load_prepared(a.folder)
    plan = schema["business"].get("plan", "free")
    limit = PLAN_LIMITS.get(plan, 1000)
    total = 0
    for name in load_order(schema, prep):
        n = len(prep[name]["rows"])
        total += n
        print(f"  {name:22} {n:6}")
    print(f"  {'TOTAL':22} {total:6}   limit on plan '{plan}': {limit} per base, headroom {limit - total}")
    if total > limit:
        print("  OVER THE LIMIT — choose a selection (see references/migration.md) before loading")
        sys.exit(1)
    if total > limit * 0.8:
        print("  Less than 20% headroom left for new records — say so to the owner")


def cmd_batches(a):
    schema = load_json(a.schema)
    tables = table_map(schema)
    ids = load_json(a.ids)
    idmap = load_json(a.idmap) if os.path.exists(a.idmap) else {}
    prep = load_prepared(a.folder)
    os.makedirs(a.out, exist_ok=True)
    problems = []
    order = load_order(schema, prep)
    for name in order:
        if name in idmap and len(idmap[name]) >= len(prep[name]["rows"]) and not a.force:
            print(f"  {name}: already loaded ({len(idmap[name])} ids) — skip (use --force to rebuild)")
            continue
        t = tables[name]
        waiting = [f["to"] for f in t["fields"] if f["type"] == "link" and f["to"] in prep
                   and f["to"] != name and f["to"] not in idmap]
        if waiting:
            print(f"  {name}: waiting — load {', '.join(sorted(set(waiting)))} first, run `learn`, then `batches` again")
            continue
        fdefs = {f["name"]: f for f in t["fields"]}
        fids = ids["fields"].get(name, {})
        recs, keys = [], []
        for i, row in enumerate(prep[name]["rows"]):
            fields = {}
            for k, v in row.items():
                if k == "_key" or v is None or v == "":
                    continue
                fd = fdefs.get(k)
                if not fd:
                    problems.append(f"{name} row {i}: unknown field '{k}'")
                    continue
                if fd["type"] in SKIP_TYPES:
                    continue
                if fd["type"] == "link":
                    vals = v if isinstance(v, list) else [v]
                    target = idmap.get(fd["to"], {})
                    rid = []
                    for x in vals:
                        if str(x) in target:
                            rid.append(target[str(x)])
                        else:
                            problems.append(f"{name} row {i}: {k} → '{x}' not loaded in {fd['to']} yet")
                    v = rid
                if fd["type"] in ("singleSelect",) and fd.get("choices") and v not in fd["choices"]:
                    problems.append(f"{name} row {i}: {k} = '{v}' is not one of {fd['choices']}")
                if k not in fids:
                    problems.append(f"{name}: field '{k}' not found in the built base (ids.json)")
                    continue
                fields[fids[k]] = v
            recs.append({"fields": fields})
            keys.append(str(row.get("_key", i)))
        if problems:
            break
        n = 0
        for start in range(0, len(recs), 50):
            n += 1
            path = os.path.join(a.out, f"{name}-{n:03d}.json")
            save_json({"table": name, "tableId": ids["tables"][name], "keys": keys[start:start + 50],
                       "records": recs[start:start + 50]}, path)
        print(f"  {name}: {len(recs)} records → {n} batch file(s)")
    if problems:
        print("\nSTOPPED:")
        print("\n".join(problems[:40]))
        if len(problems) > 40:
            print(f"... and {len(problems) - 40} more")
        sys.exit(1)
    print("load order:", " → ".join(order))


def cmd_learn(a):
    batch = load_json(a.batch)
    resp = load_json(a.response)
    recs = resp.get("records", resp) if isinstance(resp, dict) else resp
    if len(recs) != len(batch["keys"]):
        sys.exit(f"response has {len(recs)} records, batch had {len(batch['keys'])}")
    idmap = load_json(a.idmap) if os.path.exists(a.idmap) else {}
    m = idmap.setdefault(batch["table"], {})
    for k, r in zip(batch["keys"], recs):
        m[k] = r["id"]
    save_json(idmap, a.idmap)
    print(f"{batch['table']}: {len(recs)} ids saved ({len(m)} total)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("count"); c.add_argument("folder"); c.add_argument("--schema", required=True)
    b = sub.add_parser("batches"); b.add_argument("folder"); b.add_argument("--schema", required=True)
    b.add_argument("--ids", required=True); b.add_argument("--idmap", required=True)
    b.add_argument("--out", required=True); b.add_argument("--force", action="store_true")
    l = sub.add_parser("learn"); l.add_argument("batch"); l.add_argument("response"); l.add_argument("--idmap", required=True)
    a = ap.parse_args()
    {"count": cmd_count, "batches": cmd_batches, "learn": cmd_learn}[a.cmd](a)


if __name__ == "__main__":
    main()
