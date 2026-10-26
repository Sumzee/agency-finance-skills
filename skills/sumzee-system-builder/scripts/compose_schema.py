#!/usr/bin/env python3
"""Compose a draft schema.json from the core, one model template and optional modules.

Usage:
  compose_schema.py --model projects [--modules budgets,multicurrency]
                    [--lang ru] [--currency EUR] [--currencies EUR,USD]
                    [--name "Brightside"] [--plan free] [--mode owner]
                    [--table-names label|name] --out schema.json
  compose_schema.py --list            # show models and modules

The result is a starting point: edit it for the client (rename choices, drop fields
they don't need, add their own), then run validate_schema.py.
"""
import argparse
import copy
import glob
import json
import os

from common import TEMPLATES, load_json, save_json, tr, die

SYMBOLS = {"EUR": "€", "USD": "$", "GBP": "£", "RUB": "₽", "GEL": "₾", "NIS": "₪", "ILS": "₪",
           "RSD": "RSD", "TRY": "₺", "PLN": "zł", "CHF": "CHF", "AED": "AED", "KZT": "₸", "AMD": "֏"}


def list_templates():
    models = []
    for p in sorted(glob.glob(os.path.join(TEMPLATES, "*.json"))):
        t = load_json(p)
        if t["id"] != "core":
            models.append((t["id"], tr(t.get("label"), "en"), t.get("status", ""), tr(t.get("fits"), "en")))
    mods = []
    for p in sorted(glob.glob(os.path.join(TEMPLATES, "modules", "*.json"))):
        m = load_json(p)
        mods.append((m["id"], tr(m.get("label"), "en"), tr(m.get("when"), "en")))
    return models, mods


def resolve(obj, lang, subs):
    """Translate {"en","ru"} dicts and substitute {{PLACEHOLDERS}} recursively."""
    if isinstance(obj, dict):
        if set(obj.keys()) <= {"en", "ru"} and obj:
            return resolve(tr(obj, lang), lang, subs)
        return {k: resolve(v, lang, subs) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve(v, lang, subs) for v in obj]
    if isinstance(obj, str):
        if obj in subs and isinstance(subs[obj], list):
            return list(subs[obj])
        for k, v in subs.items():
            if not isinstance(v, list):
                obj = obj.replace(k, v)
        return obj
    return obj


def merge_part(schema, part, origin):
    tables = {t["name"]: t for t in schema["tables"]}
    for t in part.get("tables", []):
        if t["name"] in tables:
            die(f"{origin}: table {t['name']} already exists")
        t = copy.deepcopy(t)
        t["origin"] = origin
        schema["tables"].append(t)
        tables[t["name"]] = t
    for tname, fields in part.get("extend", {}).items():
        if tname not in tables:
            die(f"{origin}: extends unknown table {tname}")
        existing = {f["name"] for f in tables[tname]["fields"]}
        for f in fields:
            if f["name"] in existing:
                die(f"{origin}: field {tname}.{f['name']} already exists")
            tables[tname]["fields"].append(copy.deepcopy(f))
    for tname, ovr in part.get("override", {}).items():
        for fname, formula in ovr.items():
            fld = next((f for f in tables[tname]["fields"] if f["name"] == fname), None)
            if not fld:
                die(f"{origin}: override of unknown field {tname}.{fname}")
            fld["formula"] = formula
    for tname, rl in part.get("relabel", {}).items():
        if tname in tables:
            tables[tname].update(copy.deepcopy(rl))
    schema["questions"].extend(copy.deepcopy(part.get("questions", [])))
    for k, v in part.get("roles", {}).items():
        if k == "exclude":
            schema["roles"].setdefault("exclude", []).extend(v)
        else:
            schema["roles"][k] = v
    for a in part.get("automations", []):
        schema["automations"].append(copy.deepcopy(a))
    if part.get("notes"):
        schema["notes_for_team"].append(part["notes"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--modules", default="")
    ap.add_argument("--lang", default="ru")
    ap.add_argument("--currency", default="EUR")
    ap.add_argument("--currencies", default="")
    ap.add_argument("--name", default="")
    ap.add_argument("--plan", default="free", choices=["free", "team", "business"])
    ap.add_argument("--mode", default="owner", choices=["owner", "sumzee"])
    ap.add_argument("--table-names", default=None, choices=["label", "name"])
    ap.add_argument("--out")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    if a.list:
        models, mods = list_templates()
        print("MODELS")
        for m in models:
            print(f"  {m[0]:14} {m[1]:28} [{m[2]}]  {m[3]}")
        print("MODULES")
        for m in mods:
            print(f"  {m[0]:20} {m[1]:30} {m[2]}")
        return
    if not a.model or not a.out:
        die("--model and --out are required (or --list)")

    base = a.currency.upper()
    currencies = [c.strip().upper() for c in a.currencies.split(",") if c.strip()] or [base]
    if base not in currencies:
        currencies.insert(0, base)
    modules = [m.strip() for m in a.modules.split(",") if m.strip()]
    if len(currencies) > 1 and "multicurrency" not in modules:
        modules.append("multicurrency")

    core = load_json(os.path.join(TEMPLATES, "core.json"))
    model_path = os.path.join(TEMPLATES, f"{a.model}.json")
    if not os.path.exists(model_path):
        die(f"unknown model {a.model}; see --list")
    model = load_json(model_path)

    schema = {
        "version": 1,
        "business": {
            "name": a.name, "model": a.model, "language": a.lang, "currency": base,
            "currencies": currencies, "plan": a.plan, "mode": a.mode,
            "table_names": a.table_names or ("name" if a.lang == "en" else "label"),
            "template_status": model.get("status", ""),
            "modules": modules,
        },
        "groups": copy.deepcopy(core["groups"]),
        "tables": [],
        "questions": [],
        "roles": {},
        "automations": [],
        "notes_for_team": [],
        "todo_for_sumzee": [],
    }
    merge_part(schema, core, "core")
    # model questions should come first on the page
    core_q = schema["questions"]
    schema["questions"] = []
    merge_part(schema, model, a.model)
    schema["questions"].extend(core_q)
    for mid in modules:
        p = os.path.join(TEMPLATES, "modules", f"{mid}.json")
        if not os.path.exists(p):
            die(f"unknown module {mid}; see --list")
        m = load_json(p)
        for req in m.get("requires", []):
            if req != a.model:
                die(f"module {mid} requires model {req}")
        merge_part(schema, m, mid)
        if m.get("record_warning"):
            schema["notes_for_team"].append(m["record_warning"])

    subs = {
        "{{BASE}}": base,
        "{{CURRENCIES}}": currencies,
        "{{OTHER_CURRENCIES}}": [c for c in currencies if c != base] or [base],
    }
    schema = resolve(schema, a.lang, subs)
    sym = SYMBOLS.get(base, base)
    for t in schema["tables"]:
        for f in t["fields"]:
            if f.get("type") == "currency":
                f.setdefault("symbol", sym)
                f.setdefault("precision", 2)
    save_json(schema, a.out)
    n_f = sum(len(t["fields"]) for t in schema["tables"])
    print(f"wrote {a.out}: model={a.model} modules={modules or '-'} "
          f"tables={len(schema['tables'])} fields={n_f} lang={a.lang} currency={base}")


if __name__ == "__main__":
    main()
