"""Shared helpers for the Sumzee System Builder scripts (stdlib only)."""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEMPLATES = os.path.join(ROOT, "templates")

PLAIN_TYPES = {
    "singleLineText", "multilineText", "email", "url", "phoneNumber", "richText",
    "multipleAttachments", "singleCollaborator", "multipleCollaborators", "barcode",
    "autoNumber", "number", "percent", "currency", "date", "dateTime", "checkbox",
    "singleSelect", "multipleSelects", "rating", "duration",
}
COMPUTED_TYPES = {"link", "lookup", "rollup", "count", "formula", "createdTime", "lastModifiedTime"}
ALL_TYPES = PLAIN_TYPES | COMPUTED_TYPES
PRIMARY_OK = {
    "singleLineText", "email", "url", "multilineText", "number", "percent", "currency",
    "duration", "date", "dateTime", "phoneNumber", "barcode", "autoNumber",
}
# Airtable types as they come back from list_tables_for_base
API_TYPE = {
    "link": "multipleRecordLinks",
    "lookup": "multipleLookupValues",
    "rollup": "rollup",
    "count": "count",
    "formula": "formula",
}
FREE_PLAN_RECORDS = 1000
PLAN_LIMITS = {"free": 1000, "team": 50000, "business": 125000}

FORMULA_REF = re.compile(r"\{([^{}]+)\}")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(obj, path):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def tr(value, lang):
    """Resolve an {"en": .., "ru": ..} dict to one language; pass strings through."""
    if isinstance(value, dict) and ("en" in value or "ru" in value):
        return value.get(lang) or value.get("en") or next(iter(value.values()))
    return value


def table_map(schema):
    return {t["name"]: t for t in schema["tables"]}


def inverse_fields(schema):
    """{target_table: [{"name": inverse, "from_table": src, "from_field": f}]}"""
    out = {}
    for t in schema["tables"]:
        for f in t["fields"]:
            if f.get("type") == "link":
                out.setdefault(f["to"], []).append(
                    {"name": f.get("inverse") or t["name"], "from_table": t["name"], "from_field": f["name"]}
                )
    return out


def all_field_names(schema):
    """{table: {field_name: descriptor}} including inverse link fields."""
    inv = inverse_fields(schema)
    res = {}
    for t in schema["tables"]:
        names = {f["name"]: {"kind": "own", "field": f} for f in t["fields"]}
        for i in inv.get(t["name"], []):
            names.setdefault(i["name"], {"kind": "inverse", "to": i["from_table"], "field": None})
        res[t["name"]] = names
    return res


def link_target(schema, table, field_name):
    """Which table does a link field (own or inverse) in `table` point to?"""
    names = all_field_names(schema)[table]
    d = names.get(field_name)
    if not d:
        return None
    if d["kind"] == "inverse":
        return d["to"]
    f = d["field"]
    if f.get("type") == "link":
        return f["to"]
    return None


def formula_refs(formula):
    return FORMULA_REF.findall(formula or "")


def airtable_table_name(schema, table):
    mode = schema.get("business", {}).get("table_names", "label")
    if mode == "label" and table.get("label"):
        return table["label"]
    return table["name"]


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)
