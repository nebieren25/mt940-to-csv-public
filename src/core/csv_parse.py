"""
Parse CSV content into transaction rows compatible with app schema.
Pure logic; no I/O. Raises ValueError when required columns are missing.
"""

import csv
import io

from src.core.domain import CSV_HEADERS

# Minimum columns needed for preview and summary: at least one date, one amount
REQUIRED_CSV_KEYS = (
    {"value_date", "entry_date"},  # at least one
    {"signed_amount", "amount"},   # at least one
)


class CSVColumnError(ValueError):
    """Raised when CSV headers are missing or invalid."""

    pass


def _detect_delimiter(content: str) -> str:
    """Try comma, semicolon, tab; return the one that yields valid headers."""
    for delim in (",", ";", "\t"):
        reader = csv.DictReader(io.StringIO(content), delimiter=delim)
        try:
            row = next(reader)
        except StopIteration:
            continue
        keys = set(k.strip().lower() for k in row.keys() if k)
        has_date = bool(keys & {"value_date", "entry_date"})
        has_amount = bool(keys & {"signed_amount", "amount"})
        if has_date and has_amount:
            return delim
    return ","


def csv_content_to_rows(content: str, delimiter: str | None = None) -> list[dict]:
    """
    Parse CSV string into list of row dicts with keys matching CSV_HEADERS.
    If delimiter is None, try to detect it. Raises CSVColumnError if required
    columns (date and amount) are missing.
    """
    content = content.strip()
    if not content:
        return []

    if delimiter is None:
        delimiter = _detect_delimiter(content)
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    rows = []
    key_map = None  # lowercase header -> original header
    for raw in reader:
        if key_map is None:
            keys_lower = {k.strip().lower(): k.strip() for k in raw.keys() if k}
            keys_seen = set(keys_lower.keys())
            has_date = bool(keys_seen & {"value_date", "entry_date"})
            has_amount = bool(keys_seen & {"signed_amount", "amount"})
            if not has_date or not has_amount:
                missing = []
                if not has_date:
                    missing.append("value_date or entry_date")
                if not has_amount:
                    missing.append("signed_amount or amount")
                raise CSVColumnError(
                    f"CSV columns missing or invalid. Required: {', '.join(missing)}."
                )
            key_map = keys_lower
        # Map CSV columns (case-insensitive) to our schema
        out = {}
        for h in CSV_HEADERS:
            orig_key = key_map.get(h, h)
            out[h] = raw.get(orig_key, raw.get(h, ""))
        rows.append(out)
    return rows
