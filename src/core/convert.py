"""
Core conversion: MT940 content → rows; rows → CSV string.
Pure functions; no I/O.
"""

import csv
import io
import re

from src.core.domain import CSV_HEADERS
from src.core.library_adapter import parse_with_library
from src.core.parsing import parse_mt940_custom


def content_to_rows(content: str, encoding: str = "utf-8") -> tuple[list[dict], str]:
    """
    Convert MT940 content to list of transaction rows and account.
    Tries library first, then custom parser. Applies currency fallback.
    Returns (rows, account). rows may be empty.
    """
    rows, account = parse_with_library(content, encoding)
    if rows is None or not rows:
        rows, account = parse_mt940_custom(content, encoding)

    if not rows:
        return [], account or ""

    if not any(r.get("currency") for r in rows) and account:
        m = re.search(r"([A-Z]{3})$", account)
        if m:
            for r in rows:
                r["currency"] = m.group(1)

    return rows, account


def rows_to_csv_string(
    rows: list[dict],
    delimiter: str = ",",
    decimal_sep: str = ",",
) -> str:
    """
    Serialize rows to CSV string using CSV_HEADERS.
    Amount-like fields use decimal_sep (e.g. comma for Excel).
    """
    out = io.StringIO()
    writer = csv.DictWriter(
        out,
        fieldnames=CSV_HEADERS,
        delimiter=delimiter,
        extrasaction="ignore",
    )
    writer.writeheader()
    for r in rows:
        row = dict(r)
        row["date"] = row.get("date") or row.get("value_date") or row.get("entry_date") or ""
        row["description"] = (
            row.get("description")
            or row.get("cleared_description")
            or row.get("counterparty_name")
            or row.get("payment_description")
            or ""
        )
        row["amount"] = row.get("amount") or row.get("signed_amount") or ""
        for key in ("amount", "opening_balance", "closing_balance", "signed_amount", "original_amount"):
            if row.get(key):
                value = str(row[key]).strip()
                if decimal_sep == ",":
                    row[key] = value.replace(".", ",")
                else:
                    row[key] = value.replace(",", ".")
        writer.writerow(row)
    return out.getvalue()
