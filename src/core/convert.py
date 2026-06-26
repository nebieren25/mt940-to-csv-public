"""
Core conversion: MT940 content → rows; rows → CSV string.
Pure functions; no I/O.
"""

import csv
import io
import re

from src.core.domain import (
    BANK_PROFILES,
    CSV_HEADERS,
    DEFAULT_BANK_PROFILE,
    DEFAULT_DESCRIPTION_STYLE,
    DESCRIPTION_STYLES,
)
from src.core.library_adapter import parse_with_library
from src.core.parsing import GENERIC_COUNTERPARTY_NAMES, parse_mt940_custom


def _looks_like_abn_content(content: str) -> bool:
    """Return True when the statement contains ABN-style :86: descriptions."""
    return bool(re.search(r"(?m)^:86:\s*\d{4}\s+", content or ""))


def _normalize_option(value: str, allowed: tuple[str, ...], default: str) -> str:
    """Normalize a string option to a known value."""
    value = (value or "").strip().lower()
    return value if value in allowed else default


def _clean_component(value: object) -> str:
    """Normalize a description component and drop non-informative placeholders."""
    text = re.sub(r"\s+", " ", str(value or "")).strip(" /")
    if text.upper() in {"", "NOTPROVIDED", "NONREF", "NOREF", "N/A", "NA", "NONE"}:
        return ""
    return text


def _first_description_component(row: dict) -> str:
    """Choose the main readable entity for the first CSV description column."""
    counterparty_name = _clean_component(row.get("counterparty_name"))
    existing_description = _clean_component(row.get("description"))
    if counterparty_name:
        if counterparty_name.upper() in GENERIC_COUNTERPARTY_NAMES and existing_description:
            return existing_description
        return counterparty_name

    for key in (
        "card_terminal",
        "ultimate_creditor",
        "description",
        "cleared_description",
        "payment_description",
    ):
        text = _clean_component(row.get(key))
        if text:
            return text
    return ""


def _is_sepa_overboeking(row: dict) -> bool:
    """ABN STA labels Dutch bank transfers as 'SEPA Overboeking'."""
    label = _clean_component(row.get("bank_transaction_label")).casefold()
    return "sepa overboeking" in label


def _combine_description(primary: str, detail: str) -> str:
    """Append detail to primary without repeating the same text."""
    primary = _clean_component(primary)
    detail = _clean_component(detail)
    if not primary:
        return detail
    if not detail:
        return primary
    primary_fold = primary.casefold()
    detail_fold = detail.casefold()
    if detail_fold in primary_fold or primary_fold in detail_fold:
        return primary
    return f"{primary} - {detail}"


def compose_display_description(
    row: dict,
    description_style: str = DEFAULT_DESCRIPTION_STYLE,
) -> str:
    """Build the user-facing description column from parsed detail fields."""
    style = _normalize_option(description_style, DESCRIPTION_STYLES, DEFAULT_DESCRIPTION_STYLE)
    primary = _first_description_component(row)
    payment_description = _clean_component(row.get("payment_description"))

    if style == "counterparty_with_description":
        return _combine_description(primary, payment_description)
    if style == "sepa_overboeking_with_description" and _is_sepa_overboeking(row):
        return _combine_description(primary, payment_description)
    return primary or payment_description


def apply_description_style(
    rows: list[dict],
    description_style: str = DEFAULT_DESCRIPTION_STYLE,
) -> list[dict]:
    """Return rows with the first description columns recalculated."""
    styled_rows = []
    for row in rows or []:
        out = dict(row)
        description = compose_display_description(out, description_style)
        if description:
            out["description"] = description
            out["cleared_description"] = description
        styled_rows.append(out)
    return styled_rows


def _parse_rows_for_profile(
    content: str,
    encoding: str,
    bank_profile: str,
) -> tuple[list[dict] | None, str | None]:
    """Parse content using the requested bank/parser profile."""
    profile = _normalize_option(bank_profile, BANK_PROFILES, DEFAULT_BANK_PROFILE)
    custom_first = profile in {"abn", "raw"} or (profile == "auto" and _looks_like_abn_content(content))

    if custom_first:
        rows, account = parse_mt940_custom(content, encoding)
        if rows or profile == "raw":
            return rows, account
        return parse_with_library(content, encoding)

    rows, account = parse_with_library(content, encoding)
    if rows is None or not rows:
        rows, account = parse_mt940_custom(content, encoding)
    return rows, account


def content_to_rows(
    content: str,
    encoding: str = "utf-8",
    bank_profile: str = DEFAULT_BANK_PROFILE,
    description_style: str = DEFAULT_DESCRIPTION_STYLE,
) -> tuple[list[dict], str]:
    """
    Convert MT940 content to list of transaction rows and account.
    Uses the requested parser profile and applies currency fallback.
    Returns (rows, account). rows may be empty.
    """
    rows, account = _parse_rows_for_profile(content, encoding, bank_profile)

    if not rows:
        return [], account or ""

    if not any(r.get("currency") for r in rows) and account:
        m = re.search(r"([A-Z]{3})$", account)
        if m:
            for r in rows:
                r["currency"] = m.group(1)

    return apply_description_style(rows, description_style), account or ""


def rows_to_csv_string(
    rows: list[dict],
    delimiter: str = ",",
    decimal_sep: str = ",",
    description_style: str = DEFAULT_DESCRIPTION_STYLE,
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
    for r in apply_description_style(rows, description_style):
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
