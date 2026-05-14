"""
Core domain and conversion logic for MT940 → CSV.
No I/O: accepts and returns strings / list[dict].
"""

from src.core.convert import content_to_rows, rows_to_csv_string
from src.core.domain import CSV_HEADERS, DESCRIPTION_TAGS
from src.core.parsing import parse_mt940_custom

__all__ = [
    "CSV_HEADERS",
    "DESCRIPTION_TAGS",
    "content_to_rows",
    "rows_to_csv_string",
    "parse_mt940_custom",
]
