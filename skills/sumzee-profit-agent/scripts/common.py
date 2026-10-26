"""Shared helpers for the Sumzee Profit Agent scripts.

Everything here is deterministic: the language model decides *what* the data
means (via mapping.json), and this code does the reading and the arithmetic.
Only pandas + openpyxl are required.
"""
from __future__ import annotations

import csv
import io
import math
import re
from datetime import datetime, date
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------- reading ---

TOTAL_WORDS = (
    "total", "subtotal", "grand total", "sum", "totals", "итого", "всего",
    "итог", "сумма итого", "gesamt", "סה\"כ", "סהכ",
)


def _sniff_csv(path: Path):
    raw = path.read_bytes()
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp1251", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("utf-8", errors="replace")
    sample = text[:20000]
    delim = ","
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        counts = {d: sample.count(d) for d in ",;\t|"}
        delim = max(counts, key=counts.get)
    return text, delim


def read_raw_tables(path) -> dict[str, pd.DataFrame]:
    """Return {sheet_name: DataFrame without header} for a CSV/XLSX/XLS file."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in (".csv", ".tsv", ".txt"):
        text, delim = _sniff_csv(path)
        df = pd.read_csv(io.StringIO(text), sep=delim, header=None, dtype=str,
                         keep_default_na=False, engine="python")
        df = df.replace({"": None})
        return {"(csv)": df}
    if suffix in (".xlsx", ".xlsm", ".xls"):
        sheets = pd.read_excel(path, sheet_name=None, header=None)
        return {str(k): v for k, v in sheets.items()}
    raise ValueError(f"Unsupported file type: {path.name} (use .xlsx, .xls or .csv)")


def drop_empty(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(how="all")
    df = df.dropna(axis=1, how="all")
    return df


def _is_texty(v) -> bool:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return False
    if isinstance(v, (int, float, datetime, date, pd.Timestamp)):
        return False
    s = str(v).strip()
    if not s:
        return False
    if parse_amount(s) is not None:
        return False
    return True


def detect_header_row(raw: pd.DataFrame, max_scan: int = 20) -> int:
    """Index (0-based, positional) of the most header-like row."""
    raw = raw.reset_index(drop=True)
    best, best_score = 0, -1.0
    ncols = raw.shape[1]
    for i in range(min(max_scan, len(raw))):
        row = raw.iloc[i].tolist()
        texty = sum(_is_texty(v) for v in row)
        filled = sum(v is not None and not (isinstance(v, float) and math.isnan(v)) for v in row)
        if texty < 2:
            continue
        below = raw.iloc[i + 1:i + 6]
        below_filled = below.notna().sum(axis=1).mean() if len(below) else 0
        # header rows are mostly text, reasonably wide, and have data under them
        score = texty + 0.5 * filled / max(ncols, 1) + 0.3 * below_filled - 0.2 * i
        if texty / max(filled, 1) < 0.6:
            score -= 2
        if score > best_score:
            best, best_score = i, score
    return best


def make_unique(names):
    seen, out = {}, []
    for n in names:
        n = "" if n is None or (isinstance(n, float) and math.isnan(n)) else str(n).strip()
        if isinstance(n, str) and re.fullmatch(r"\d+\.0", n):
            n = n[:-2]
        base = n or "Unnamed"
        k = base
        c = 1
        while k in seen:
            c += 1
            k = f"{base} ({c})"
        seen[k] = 1
        out.append(k)
    return out


def table_with_header(raw: pd.DataFrame, header_row_1based: int | None):
    """Apply a header row. header_row is 1-based *within the non-empty table*,
    exactly as printed by inspect_files.py."""
    raw = drop_empty(raw).reset_index(drop=True)
    h = detect_header_row(raw) if not header_row_1based else header_row_1based - 1
    header = raw.iloc[h].tolist()
    body = raw.iloc[h + 1:].reset_index(drop=True)
    body.columns = make_unique(header)
    body = body.dropna(how="all")
    return body, h + 1


def load_source_table(base_dir: Path, file: str, sheet: str | None, header_row: int | None):
    path = Path(file)
    if not path.is_absolute():
        path = (base_dir / path)
    tables = read_raw_tables(path)
    if sheet is None or sheet not in tables:
        if sheet is not None and sheet not in tables:
            raise KeyError(f"Sheet '{sheet}' not found in {path.name}. Sheets: {list(tables)}")
        sheet = next(iter(tables))
    return table_with_header(tables[sheet], header_row)


def is_total_row(row: pd.Series) -> bool:
    for v in row.tolist():
        if isinstance(v, str):
            s = v.strip().lower().strip(":")
            if s in TOTAL_WORDS or re.match(r"^(total|итого|всего|subtotal)\b", s):
                return True
    return False


# ---------------------------------------------------------------- amounts ---

CURRENCY_SIGNS = {
    "€": "EUR", "$": "USD", "£": "GBP", "₪": "ILS", "₽": "RUB", "₴": "UAH",
    "zł": "PLN", "₸": "KZT", "₾": "GEL", "₺": "TRY", "¥": "JPY", "₹": "INR",
}
CURRENCY_CODES = ("EUR", "USD", "GBP", "ILS", "NIS", "RUB", "RUR", "UAH", "PLN",
                  "CHF", "KZT", "GEL", "TRY", "AED", "CZK", "SEK", "NOK", "DKK",
                  "CAD", "AUD", "JPY", "INR", "RSD", "HUF", "RON", "BGN", "AMD")
_CODE_RE = re.compile(r"\b(" + "|".join(CURRENCY_CODES) + r")\b", re.I)
_DATE_LIKE = re.compile(r"^\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2})(\s|$|T)")
_RUS_CUR = {"руб": "RUB", "р.": "RUB", "евро": "EUR", "долл": "USD", "шек": "ILS"}


def currency_in(value) -> str | None:
    if not isinstance(value, str):
        return None
    for sign, code in CURRENCY_SIGNS.items():
        if sign in value:
            return code
    m = _CODE_RE.search(value)
    if m:
        c = m.group(1).upper()
        return {"NIS": "ILS", "RUR": "RUB"}.get(c, c)
    low = value.lower()
    for k, c in _RUS_CUR.items():
        if k in low:
            return c
    return None


def parse_amount(v):
    """Turn '€1,200.50', '1 200,50', '(300)', '300-', '12.5k' into float. None if not a number."""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        if isinstance(v, float) and math.isnan(v):
            return None
        return float(v)
    if isinstance(v, (datetime, date, pd.Timestamp)):
        return None
    s = str(v).strip()
    if not s or s in {"-", "—", "–", "n/a", "N/A", "na", "—", "?"}:
        return None
    if _DATE_LIKE.match(s):
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1]
    s = s.replace(" ", " ").replace(" ", " ")
    for sign in CURRENCY_SIGNS:
        s = s.replace(sign, "")
    s = _CODE_RE.sub("", s)
    s = re.sub(r"(руб\.?|р\.|евро|долл\.?|шек\.?)", "", s, flags=re.I)
    s = s.strip()
    mult = 1.0
    m = re.fullmatch(r"(.*?)[\s]*([kKкК]|тыс\.?)$", s)
    if m and re.search(r"\d", m.group(1)):
        s, mult = m.group(1), 1000.0
    if s.endswith("-"):
        neg, s = True, s[:-1]
    if s.startswith("-") or s.startswith("−") or s.startswith("–"):
        neg, s = (not neg), s[1:]
    if s.startswith("+"):
        s = s[1:]
    s = s.replace(" ", "").replace("'", "")
    if not s or not re.fullmatch(r"[\d.,]+", s):
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):  # 1.234,56
            s = s.replace(".", "").replace(",", ".")
        else:  # 1,234.56
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            s = s.replace(",", ".")  # decimal comma
        else:
            s = s.replace(",", "")  # thousands comma
    elif s.count(".") > 1:
        s = s.replace(".", "")
    elif "." in s:
        head, tail = s.split(".")
        if len(tail) == 3 and len(head) <= 3 and head not in ("0", ""):
            # '1.200' is far more often 1200 than 1.2 in finance sheets
            s = head + tail
    try:
        val = float(s) * mult
    except ValueError:
        return None
    return -val if neg else val


def amounts(series: pd.Series) -> pd.Series:
    return series.map(parse_amount).astype("float64")


# ------------------------------------------------------------------ dates ---

RU_MONTHS = {
    "янв": 1, "фев": 2, "мар": 3, "апр": 4, "май": 5, "мая": 5, "июн": 6,
    "июл": 7, "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12,
}
EN_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _month_word(s: str):
    s = s.lower()
    for k, v in {**EN_MONTHS, **RU_MONTHS}.items():
        if s.startswith(k):
            return v
    return None


def parse_month_label(v, default_year=None):
    """Parse a column header like 'Jan-26', 'January 2026', '2026-01', 'Янв 2026', 1/2026."""
    if isinstance(v, (datetime, pd.Timestamp)):
        return pd.Timestamp(v.year, v.month, 1)
    if isinstance(v, date):
        return pd.Timestamp(v.year, v.month, 1)
    if v is None:
        return None
    s = str(v).strip()
    m = re.fullmatch(r"(\d{4})[-/.](\d{1,2})(?:[-/.]\d{1,2})?(?: 00:00:00)?", s)
    if m and 1 <= int(m.group(2)) <= 12:
        return pd.Timestamp(int(m.group(1)), int(m.group(2)), 1)
    m = re.fullmatch(r"(\d{1,2})[-/.](\d{4})", s)
    if m and 1 <= int(m.group(1)) <= 12:
        return pd.Timestamp(int(m.group(2)), int(m.group(1)), 1)
    m = re.fullmatch(r"([A-Za-zА-Яа-яёЁ]+)\.?[\s\-'’/]*(\d{2,4})?", s)
    if m:
        mon = _month_word(m.group(1))
        if mon and len(m.group(1)) >= 3:
            y = m.group(2)
            if y is None:
                if default_year is None:
                    return None
                y = default_year
            y = int(y)
            if y < 100:
                y += 2000
            return pd.Timestamp(y, mon, 1)
    return None


def _decide_dayfirst(strings) -> bool:
    first_gt12 = second_gt12 = 0
    for s in strings:
        m = re.match(r"^\s*(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", s)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a > 12:
                first_gt12 += 1
            if b > 12:
                second_gt12 += 1
        elif re.match(r"^\s*\d{1,2}\.\d{1,2}\.\d{2,4}", s):
            first_gt12 += 0.1  # dotted dates are almost always day-first
    if second_gt12 > first_gt12:
        return False
    return True  # Europe/Israel/Russia default


def parse_dates(series: pd.Series) -> pd.Series:
    out = {}
    strings = []
    for idx, v in series.items():
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        if isinstance(v, (pd.Timestamp, datetime)):
            out[idx] = pd.Timestamp(v)
        elif isinstance(v, date):
            out[idx] = pd.Timestamp(v)
        elif isinstance(v, (int, float)) and 20000 < float(v) < 70000:
            out[idx] = pd.Timestamp("1899-12-30") + pd.to_timedelta(float(v), unit="D")
        else:
            strings.append((idx, str(v).strip()))
    if strings:
        dayfirst = _decide_dayfirst([s for _, s in strings])
        for idx, s in strings:
            ts = None
            if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}.*", s):
                ts = pd.to_datetime(s[:10], errors="coerce")
            elif re.match(r"^\d{1,2}[./-]\d{1,2}[./-]\d{2,4}", s):
                ts = pd.to_datetime(s.split(" ")[0], dayfirst=dayfirst, errors="coerce")
            else:
                ts = parse_month_label(s)
                if ts is None:
                    try:
                        ts = pd.to_datetime(s, errors="coerce", dayfirst=dayfirst)
                    except (ValueError, TypeError, OverflowError):
                        ts = None
            if ts is not None and not pd.isna(ts):
                out[idx] = pd.Timestamp(ts)
    values = [out.get(i) for i in series.index]
    values = [v.to_pydatetime().replace(tzinfo=None) if v is not None else None for v in values]
    return pd.Series(pd.to_datetime(values, errors="coerce"), index=series.index)


# ------------------------------------------------------------------ misc ----

def clean_label(v) -> str | None:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    s = re.sub(r"\s+", " ", str(v)).strip()
    if isinstance(v, float) and v.is_integer():
        s = str(int(v))
    return s or None


def canonical_labels(series: pd.Series, mapping: dict | None = None) -> pd.Series:
    """Merge 'Freelancers ', 'freelancers', 'FREELANCERS' into one label; apply explicit map."""
    mapping = mapping or {}
    low_map = {str(k).strip().lower(): v for k, v in mapping.items()}
    cleaned = series.astype(object).map(clean_label)
    # pick the most common spelling as canonical for each lowercase key
    counts = cleaned.dropna().value_counts()
    canon = {}
    for label, _ in counts.items():
        if isinstance(label, str):
            canon.setdefault(label.lower(), label)
    def f(x):
        if not isinstance(x, str):
            return None
        if x.lower() in low_map:
            return low_map[x.lower()]
        return canon.get(x.lower(), x)
    return cleaned.map(f).astype(object)


def month_key(ts) -> str:
    return f"{ts.year:04d}-{ts.month:02d}"
