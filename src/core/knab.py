"""Pure MT940 parsing for Knab's named, slash-delimited descriptions."""

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Iterator

from src.core.domain import CSV_HEADERS
from src.core.parsing import GENERIC_COUNTERPARTY_NAMES, _empty_description_fields


_MT940_TAG = re.compile(r"^:(?P<tag>\d{2}[A-Z]?):(?P<value>.*)$")
_SWIFT_ENVELOPE = re.compile(r"^\{(?:[12]:[A-Z]\d{2}|[35]:\{|4:\s*$)")
_SWIFT_CLOSE = re.compile(r"^-}(?:\{[1-5]:|$)")
_ACCOUNT_IDENTIFICATION = re.compile(r"(?m)^:25:([^\r\n]*)")
_KNAB_ACCOUNT = re.compile(r"NL\d{2}KNAB\d{10}(?:[A-Z]{3})?")
_KNAB_SENDER = re.compile(r"\{1:[A-Z]\d{2}KNABNL2H[A-Z0-9]*", re.IGNORECASE)
_BALANCE = re.compile(r"^(?P<status>[CD])\d{6}(?P<currency>[A-Z]{3})(?P<amount>\d+(?:[,.]\d*)?)$")
_TRANSACTION = re.compile(
    r"^(?P<value_date>\d{6})(?P<entry_date>\d{4})?"
    r"(?P<status>R?[CD])(?P<funds_code>[A-Z])?"
    r"(?P<amount>\d{1,15}(?:[,.]\d{0,2})?)"
    r"(?P<transaction_type>[A-Z][A-Z0-9]{3})(?P<references>[^\r\n]*)$"
)
_DESCRIPTION_TAGS = (
    "TRTP", "IBAN", "BBAN", "BIC", "NAME", "REMI", "EREF", "MARF",
    "CSID", "RTRN", "PURP", "ULTC",
)
_DESCRIPTION_MARKER = re.compile(r"/{1,2}(?P<tag>" + "|".join(_DESCRIPTION_TAGS) + r")/")


def looks_like_knab_content(content: str) -> bool:
    """Prefer own-account identities; use the SWIFT sender only without account tags."""
    content = content or ""
    accounts = _ACCOUNT_IDENTIFICATION.findall(content)
    if accounts:
        return all(_KNAB_ACCOUNT.fullmatch(account.strip()) for account in accounts)
    return bool(_KNAB_SENDER.search(content))


def _normalize_text(value: str) -> str:
    """Normalize derived fields while retaining slash text in free descriptions."""
    return re.sub(r"\s+", " ", value).strip()


def _tag_blocks(content: str) -> Iterator[tuple[str, str, str]]:
    """Read tagged fields without mistaking colon-prefixed continuation text for tags."""
    current_tag = ""
    value_parts: list[str] = []
    raw_parts: list[str] = []
    for line in content.splitlines():
        match = _MT940_TAG.match(line)
        framing = _SWIFT_ENVELOPE.match(line) or _SWIFT_CLOSE.match(line.strip()) or line.strip() == "}"
        if match or framing:
            if current_tag:
                yield current_tag, "".join(value_parts), "\n".join(raw_parts)
            current_tag = ""
            value_parts = []
            raw_parts = []
            if match:
                current_tag = match["tag"]
                value_parts = [match["value"]]
                raw_parts = [line]
        elif current_tag:
            value_parts.append(line)
            raw_parts.append(line)
    if current_tag:
        yield current_tag, "".join(value_parts), "\n".join(raw_parts)


def _description_fields(raw_86: str) -> dict[str, str]:
    markers = list(_DESCRIPTION_MARKER.finditer(raw_86))
    values: dict[str, str] = {}
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(raw_86)
        values.setdefault(marker["tag"], _normalize_text(raw_86[marker.end():end]))

    fields = _empty_description_fields()
    fields["description_format"] = "knab"
    fields["counterparty_name"] = values.get("NAME", "")
    fields["counterparty_iban"] = values.get("IBAN", "")
    fields["counterparty_account"] = fields["counterparty_iban"] or values.get("BBAN", "")
    fields["counterparty_bic"] = values.get("BIC", "")
    fields["bank_transaction_label"] = values.get("TRTP", "")
    for source, target in (
        ("REMI", "payment_description"),
        ("EREF", "payment_reference"),
        ("MARF", "mandate_reference"),
        ("CSID", "creditor_id"),
        ("RTRN", "return_reason"),
        ("PURP", "purpose_code"),
        ("ULTC", "ultimate_creditor"),
    ):
        fields[target] = values.get(source, "")

    name = fields["counterparty_name"]
    remittance = fields["payment_description"]
    if name.upper() in GENERIC_COUNTERPARTY_NAMES and remittance:
        fields["description"] = remittance
    else:
        fields["description"] = name or remittance or fields["ultimate_creditor"]
    if not fields["description"]:
        fields["description"] = fields["bank_transaction_label"] or _normalize_text(raw_86)
    if fields["bank_transaction_label"].upper().startswith(("BETAALAUTOMAAT", "GELDAUTOMAAT")):
        fields["card_terminal"] = name
    return fields


def _format_decimal(value: Decimal) -> str:
    return format(value, ".2f").replace(".", ",")


def _balance_fields(value: str) -> tuple[str, str]:
    match = _BALANCE.fullmatch(value.strip())
    if not match:
        return "", ""
    amount = Decimal(match["amount"].replace(",", "."))
    if match["status"] == "D":
        amount = -amount
    return _format_decimal(amount), match["currency"]


def _value_date(value: str) -> str:
    year = int(value[:2])
    parsed = date((2000 if year < 50 else 1900) + year, int(value[2:4]), int(value[4:]))
    return parsed.strftime("%d-%m-%Y")


def _transaction_row(raw_61: str) -> dict[str, str] | None:
    # Supplementary :61: lines are kept raw, separate from its reference fields.
    first_line = raw_61.split("\n", 1)[0]
    match = _TRANSACTION.fullmatch(first_line[4:].strip())
    if not match:
        return None
    try:
        value_date = _value_date(match["value_date"])
        amount = Decimal(match["amount"].replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    if match["status"] in {"D", "RC"}:
        amount = -amount
    signed_amount = _format_decimal(amount)
    customer_ref, separator, bank_ref = match["references"].partition("//")
    entry_date = match["entry_date"] or ""
    row = {key: "" for key in CSV_HEADERS}
    row.update(_empty_description_fields())
    row.update({
        "date": value_date,
        "value_date": value_date,
        "entry_date": f"{entry_date[:2]}-{entry_date[2:]}" if entry_date else "",
        "amount": signed_amount,
        "signed_amount": signed_amount,
        "original_amount": match["amount"].replace(",", "."),
        "debit_credit": match["status"],
        "transaction_type": match["transaction_type"],
        "customer_ref": customer_ref.strip(),
        "bank_ref": bank_ref.strip() if separator else "",
        "reference": (bank_ref if separator and bank_ref.strip() else customer_ref).strip(),
        "description_format": "knab",
        "raw_61": raw_61,
        "raw_all_together": raw_61,
    })
    return row


@dataclass
class _Page:
    account: str = ""
    statement_number: str = ""
    transaction_reference: str = ""
    opening_balance: str = ""
    closing_balance: str = ""
    currency: str = ""
    rows: list[dict[str, str]] = field(default_factory=list)

    def finish(self, output: list[dict]) -> None:
        for row in self.rows:
            row.update({
                "account": self.account,
                "statement_number": self.statement_number,
                "transaction_reference": self.transaction_reference,
                "opening_balance": self.opening_balance,
                "closing_balance": self.closing_balance,
                "currency": self.currency,
            })
        output.extend(self.rows)


def parse_knab_mt940(content: str, encoding: str = "utf-8") -> tuple[list[dict], str]:
    """Parse Knab transactions and finalize balances within their own MT940 page."""
    rows: list[dict] = []
    account = ""
    page = _Page()
    current_row: dict[str, str] | None = None
    for tag, value, raw in _tag_blocks(content):
        if tag == "20":
            page.finish(rows)
            page = _Page(transaction_reference=value.strip())
            current_row = None
        elif tag == "25":
            if page.rows:
                page.finish(rows)
                page = _Page(transaction_reference=page.transaction_reference)
                current_row = None
            page.account = value.strip()
            account = page.account
        elif tag == "28C":
            if page.rows:
                page.finish(rows)
                page = _Page(account=page.account, transaction_reference=page.transaction_reference)
                current_row = None
            page.statement_number = value.strip()
        elif tag in {"60F", "60M"}:
            if page.rows:
                page.finish(rows)
                page = _Page(
                    account=page.account,
                    transaction_reference=page.transaction_reference,
                    statement_number=page.statement_number,
                )
                current_row = None
            page.opening_balance, page.currency = _balance_fields(value)
        elif tag in {"62F", "62M"}:
            page.closing_balance, closing_currency = _balance_fields(value)
            page.currency = page.currency or closing_currency
            current_row = None
        elif tag == "64":
            # The statement closing balance takes priority over available funds.
            if not page.closing_balance:
                page.closing_balance, closing_currency = _balance_fields(value)
                page.currency = page.currency or closing_currency
            current_row = None
        elif tag == "61":
            current_row = _transaction_row(raw)
            if current_row is not None:
                page.rows.append(current_row)
        elif tag == "86" and current_row is not None:
            current_row.update(_description_fields(value))
            current_row["raw_86"] = value
            current_row["raw_all_together"] = f"{current_row['raw_61']} {value}".strip()
            current_row["cleared_description"] = current_row["description"]
    page.finish(rows)
    return rows, account
