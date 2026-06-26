"""
MT940 parsing: custom parser and pure helpers.
No file I/O; operates on content string only.
"""

import re

from src.core.domain import DESCRIPTION_TAGS

STRUCTURED_86_TAGS = (
    "RTRN",
    "EREF",
    "MARF",
    "CSID",
    "CNTP",
    "REMI",
    "PURP",
    "ULTC",
    "CDTR",
    "DBTR",
    "ORDPTY",
    "BENEF",
    "AB",
)

GENERIC_COUNTERPARTY_NAMES = {
    "WORLDPAY",
}

CARD_METADATA_PATTERNS = {
    "card_terminal_id": r"TERMINALID:\s*([A-Z0-9]+)",
    "card_sequence_number": r"PASVOLGNR:\s*([A-Z0-9]+)",
    "card_transaction_number": r"TRANSACTIENR:\s*([A-Z0-9]+)",
}

ABN_FIELD_LABELS = {
    "iban": "counterparty_iban",
    "bic": "counterparty_bic",
    "naam": "counterparty_name",
    "omschrijving": "payment_description",
    "kenmerk": "payment_reference",
    "betalingskenm.": "payment_reference",
    "machtiging": "mandate_reference",
    "incassant": "creditor_id",
    "voor": "ultimate_creditor",
    "nr": "card_terminal_id",
}


def _parse_amount_str(s: str) -> str:
    """Normalize amount: comma to dot, return as string."""
    return s.replace(",", ".").strip()


def _parse_yyymmdd(yymmdd: str) -> str:
    """Convert YYMMDD to DD-MM-YYYY."""
    if len(yymmdd) < 6:
        return ""
    yy, mm, dd = yymmdd[0:2], yymmdd[2:4], yymmdd[4:6]
    year = "20" + yy if int(yy) < 50 else "19" + yy
    return f"{dd}-{mm}-{year}"


def _parse_mmdd(mmdd: str) -> str:
    """Convert MMDD to MM-DD (for entry_date display)."""
    if len(mmdd) < 4:
        return ""
    return f"{mmdd[0:2]}-{mmdd[2:4]}"


def _cleared_description(description: str) -> str:
    """
    Remove MT940 structural tags (/REMI/, /CNTP/, /EREF/, /USTD/, etc.)
    and normalize, leaving only the important readable parts.
    """
    if not description:
        return ""
    if any(f"/{tag}/" in description for tag in STRUCTURED_86_TAGS):
        structured = _extract_description_fields(description)
        if structured["description"]:
            return structured["description"]
    s = description
    for tag in DESCRIPTION_TAGS:
        s = s.replace(tag, " ")
    # Remove IBAN-like segments (e.g. NL00TEST9876543210)
    s = re.sub(r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7,10}\b", " ", s)
    # Remove BIC (e.g. INGBNL2A, ABNANL2A)
    s = re.sub(r"\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}\b", " ", s)
    # Remove leftover tag values (USTD = unstructured)
    s = re.sub(r"\bUSTD\b", " ", s)
    # Collapse slashes and multiple spaces
    s = re.sub(r"[/]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _normalize_space(value: str) -> str:
    """Collapse whitespace and trim common MT940 separator slashes."""
    value = value.replace("\n", " ").replace("\r", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip(" /")


def _strip_trailing_terminal_datetime(value: str) -> str:
    """Remove trailing card terminal date/time such as 24-03-2023 13:34."""
    value = _normalize_space(value)
    value = re.sub(
        r"\s+\d{1,2}[-/]\d{1,2}[-/]\d{4}\s+\d{1,2}:\d{2}\s*$",
        "",
        value,
    )
    return _normalize_space(value)


def _append_wrapped_text(current: str, part: str) -> str:
    """Append ABN wrapped text, joining obvious split words without a space."""
    current = _normalize_space(current)
    part = _normalize_space(part)
    if not current:
        return part
    if not part:
        return current
    prev_token = current.split()[-1] if current.split() else ""
    next_token = part.split()[0] if part.split() else ""
    join_without_space = False
    if current[-1:] in ("-", "/"):
        join_without_space = True
    elif prev_token and next_token and prev_token[-1:].isdigit() and next_token[:1].isdigit():
        join_without_space = True
    elif (
        prev_token.isalpha()
        and next_token.isalpha()
        and prev_token.isupper()
        and next_token.isupper()
        and len(next_token) <= 6
    ):
        join_without_space = True
    elif next_token[:1].islower():
        join_without_space = True
    return current + ("" if join_without_space else " ") + part


def _empty_description_fields(description: str = "") -> dict[str, str]:
    """Return the full description-field shape used by row builders."""
    return {
        "counterparty_name": "",
        "counterparty_account": "",
        "counterparty_iban": "",
        "counterparty_bic": "",
        "payment_reference": "",
        "mandate_reference": "",
        "creditor_id": "",
        "purpose_code": "",
        "return_reason": "",
        "payment_description": "",
        "ultimate_creditor": "",
        "card_terminal": "",
        "card_terminal_id": "",
        "card_sequence_number": "",
        "card_transaction_number": "",
        "bank_transaction_label": "",
        "description_format": "unstructured",
        "supplementary": "",
        "description": _normalize_space(description),
    }


def _extract_card_metadata(value: str) -> dict[str, str]:
    """Extract Dutch card/cash terminal metadata and return cleaned text plus fields."""
    text = value or ""
    fields = {
        "card_terminal_id": "",
        "card_sequence_number": "",
        "card_transaction_number": "",
    }
    for key, pattern in CARD_METADATA_PATTERNS.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            fields[key] = match.group(1).strip()
        text = re.sub(r"\s*" + pattern, " ", text, flags=re.IGNORECASE)
    text = _strip_trailing_terminal_datetime(text)
    return {**fields, "cleaned_text": text}


def apply_card_metadata_cleanup(row: dict) -> dict:
    """Move card terminal metadata out of human-readable description fields."""
    out = dict(row)
    source = ""
    for key in ("payment_description", "description", "cleared_description"):
        candidate = str(out.get(key) or "")
        if any(re.search(pattern, candidate, flags=re.IGNORECASE) for pattern in CARD_METADATA_PATTERNS.values()):
            source = candidate
            break
    metadata = _extract_card_metadata(str(source))
    has_existing_metadata = any(out.get(key) for key in CARD_METADATA_PATTERNS)
    has_extracted_metadata = any(metadata.get(key) for key in CARD_METADATA_PATTERNS)
    if not has_extracted_metadata and not has_existing_metadata:
        return out

    cleaned = metadata["cleaned_text"]
    for key in CARD_METADATA_PATTERNS:
        if metadata[key] and not out.get(key):
            out[key] = metadata[key]
    if cleaned:
        out["card_terminal"] = out.get("card_terminal") or cleaned
    for key in ("description", "cleared_description", "payment_description", "card_terminal"):
        if out.get(key):
            out[key] = _extract_card_metadata(str(out[key]))["cleaned_text"]
    return out


def _is_iban(value: str) -> bool:
    """Return True for a simple IBAN-looking value."""
    compact = re.sub(r"\s+", "", value or "").upper()
    return bool(re.match(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$", compact))


def _is_bic(value: str) -> bool:
    """Return True for a simple BIC-looking value."""
    compact = re.sub(r"\s+", "", value or "").upper()
    return bool(re.match(r"^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$", compact))


def _extract_structured_tag(raw: str, tag: str) -> str:
    """Extract a structured :86: subfield value such as /CNTP/... or /REMI/...."""
    if not raw:
        return ""
    text = raw.replace("\r", "").replace("\n", "")
    marker = f"/{tag}/"
    start = text.find(marker)
    if start == -1:
        return ""
    start += len(marker)
    end_candidates = []
    for next_tag in STRUCTURED_86_TAGS:
        if next_tag == tag:
            continue
        for next_marker in (f"//{next_tag}/", f"/{next_tag}/"):
            pos = text.find(next_marker, start)
            if pos != -1:
                end_candidates.append(pos)
    end = min(end_candidates) if end_candidates else len(text)
    return text[start:end].strip(" /")


def _clean_payment_description(value: str) -> str:
    """Normalize REMI/ULTC text and remove internal USTD formatting marker."""
    value = value.replace("USTD//", " ").replace("USTD/", " ").replace("USTD", " ")
    return _normalize_space(value)


def _shorten_payment_description(value: str) -> str:
    """Make a compact display label from a longer remittance text."""
    value = _clean_payment_description(value)
    for marker in (" Factuurnr.", " Factuurnummer", " Betreft IBAN", " Periode:"):
        pos = value.lower().find(marker.lower())
        if pos > 0:
            return value[:pos].strip()
    return value


def _parse_counterparty(value: str) -> dict[str, str]:
    """Parse /CNTP/account/bic/name into separate counterparty fields."""
    parts = [_normalize_space(p) for p in value.split("/") if _normalize_space(p)]
    account = parts[0] if parts else ""
    bic = parts[1] if len(parts) > 1 and _is_bic(parts[1]) else ""
    name_parts = parts[2:] if bic else parts[1:]
    name = _normalize_space(" ".join(name_parts))
    iban = re.sub(r"\s+", "", account).upper() if _is_iban(account) else ""
    return {
        "counterparty_name": name,
        "counterparty_account": account,
        "counterparty_iban": iban,
        "counterparty_bic": bic,
    }


def _looks_like_abn_86(raw_86: str) -> bool:
    """ABN AMRO STA/MT940 :86: lines start with a 4-digit sequence."""
    return bool(re.match(r"^\s*\d{4}\s+", raw_86 or ""))


def _canonical_abn_label(label: str) -> str:
    """Normalize ABN label text to a stable dictionary key."""
    return _normalize_space(label).lower()


def _prepare_abn_86(raw_86: str) -> str:
    """Remove ABN continuation markers and make field labels split-friendly."""
    text = (raw_86 or "").replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\?\d{2}", " ", text)
    label_pattern = (
        r"(IBAN|BIC|Naam|Omschrijving|Kenmerk|Betalingskenm\\.?|"
        r"Machtiging|Incassant|Voor)"
    )
    text = re.sub(rf"\s+({label_pattern}):", r" | \1:", text)
    text = re.sub(r"\s*\|\s*", " | ", text)
    return _normalize_space(text)


def _split_abn_label(segment: str) -> tuple[str, str] | None:
    """Return (label, value) when an ABN pipe segment starts with a known label."""
    segment = _normalize_space(segment)
    segment = re.sub(r"^\(\d{1,2}[-/]\d{1,2}\)\s*", "", segment)
    m = re.match(
        r"^(IBAN|BIC|Naam|Omschrijving|Kenmerk|Betalingskenm\\.?|"
        r"Machtiging|Incassant|Voor):\s*(.*)$",
        segment,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    return _canonical_abn_label(m.group(1)), _normalize_space(m.group(2))


def _clean_abn_card_terminal(value: str) -> tuple[str, str]:
    """Return cleaned BEA merchant text and PAS sequence when present."""
    text = _normalize_space(value)
    card_sequence = ""
    m = re.search(r"\bPAS\s*([A-Z0-9]+)\b", text, flags=re.IGNORECASE)
    if m:
        card_sequence = m.group(1).strip()
    text = re.sub(r"\bPAS\s*[A-Z0-9]+\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d{1,2}[.-]\d{1,2}[.-]\d{2,4}/\d{1,2}[.:]\d{2}\b", " ", text)
    text = text.replace(",", " ")
    return _normalize_space(text), card_sequence


def _extract_abn_description_fields(raw_86: str) -> dict[str, str]:
    """Extract fields from ABN AMRO STA/MT940 unstructured :86: content."""
    prepared = _prepare_abn_86(raw_86)
    fields = _empty_description_fields()
    fields["description_format"] = "abn"

    m = re.match(r"^(?P<sequence>\d{4})\s+(?P<body>.*)$", prepared)
    body = prepared
    if m:
        fields["supplementary"] = m.group("sequence")
        body = m.group("body")

    segments = [_normalize_space(part) for part in body.split("|") if _normalize_space(part)]
    current_key = ""
    unlabeled_parts: list[str] = []
    transaction_label = ""

    for idx, segment in enumerate(segments):
        nr_match = re.search(r"\bNR:([A-Z0-9]+)", segment, flags=re.IGNORECASE)
        if nr_match:
            if not fields["card_terminal_id"]:
                fields["card_terminal_id"] = nr_match.group(1)
            segment = re.sub(r"\bNR:[A-Z0-9]+", " ", segment, flags=re.IGNORECASE)
            segment = re.sub(r"\b\d{1,2}[.]\d{1,2}[.]\d{2,4}/\d{1,2}[.]\d{2}\b", " ", segment)
            segment = _normalize_space(segment)
            if not segment:
                continue

        parsed = _split_abn_label(segment)
        if parsed:
            label, value = parsed
            key = ABN_FIELD_LABELS.get(label)
            if key:
                fields[key] = _append_wrapped_text(fields.get(key, ""), value)
                current_key = key
            continue

        if idx == 0:
            transaction_label = segment
            nr_match = re.search(r"\bNR:([A-Z0-9]+)", transaction_label, flags=re.IGNORECASE)
            if nr_match and not fields["card_terminal_id"]:
                fields["card_terminal_id"] = nr_match.group(1)
            transaction_label = re.sub(r"\bNR:[A-Z0-9]+", " ", transaction_label, flags=re.IGNORECASE)
            transaction_label = re.sub(r"\b\d{1,2}[.]\d{1,2}[.]\d{2,4}/\d{1,2}[.]\d{2}\b", " ", transaction_label)
            transaction_label = _normalize_space(transaction_label)
            continue

        if current_key:
            fields[current_key] = _append_wrapped_text(fields.get(current_key, ""), segment)
        else:
            unlabeled_parts.append(segment)

    if fields["counterparty_iban"]:
        fields["counterparty_account"] = fields["counterparty_iban"]

    fields["bank_transaction_label"] = transaction_label

    if transaction_label.upper().startswith("BEA"):
        terminal_text = " ".join(unlabeled_parts)
        terminal_text = re.sub(r"^\(\d{1,2}[-/]\d{1,2}\)\s*", "", terminal_text)
        terminal_text, card_sequence = _clean_abn_card_terminal(terminal_text)
        fields["card_terminal"] = terminal_text
        if card_sequence and not fields["card_sequence_number"]:
            fields["card_sequence_number"] = card_sequence
        if terminal_text:
            fields["description"] = terminal_text
    elif fields["counterparty_name"]:
        fields["description"] = fields["counterparty_name"]
    elif fields["payment_description"]:
        fields["description"] = fields["payment_description"]
    else:
        fields["description"] = transaction_label or prepared

    if fields["payment_reference"].upper() == "NOTPROVIDED":
        fields["payment_reference"] = ""

    for key in (
        "counterparty_name",
        "counterparty_account",
        "counterparty_iban",
        "counterparty_bic",
        "payment_reference",
        "mandate_reference",
        "creditor_id",
        "payment_description",
        "ultimate_creditor",
        "card_terminal",
        "bank_transaction_label",
        "description",
    ):
        fields[key] = _normalize_space(fields.get(key, ""))

    return fields


def _extract_description_fields(raw_86: str) -> dict[str, str]:
    """
    Split structured :86: details into CSV-friendly fields.
    The display description prefers a real counterparty name; for payment processors
    such as WORLDPAY it falls back to remittance or ultimate-creditor text.
    """
    if _looks_like_abn_86(raw_86):
        return _extract_abn_description_fields(raw_86)

    payment_reference = _normalize_space(_extract_structured_tag(raw_86, "EREF"))
    mandate_reference = _normalize_space(_extract_structured_tag(raw_86, "MARF"))
    creditor_id = _normalize_space(_extract_structured_tag(raw_86, "CSID"))
    purpose_code = _normalize_space(_extract_structured_tag(raw_86, "PURP"))
    return_reason = _normalize_space(_extract_structured_tag(raw_86, "RTRN"))
    payment_description = _clean_payment_description(_extract_structured_tag(raw_86, "REMI"))
    original_payment_description = payment_description
    card_metadata = _extract_card_metadata(payment_description)
    payment_description = card_metadata["cleaned_text"] or payment_description
    has_card_details = (
        any(card_metadata[key] for key in CARD_METADATA_PATTERNS)
        or card_metadata["cleaned_text"] != original_payment_description
    )
    ultimate_creditor = _clean_payment_description(_extract_structured_tag(raw_86, "ULTC"))
    counterparty = _parse_counterparty(_extract_structured_tag(raw_86, "CNTP"))

    counterparty_name = counterparty["counterparty_name"]
    generic_counterparty = counterparty_name.upper() in GENERIC_COUNTERPARTY_NAMES
    display_description = ""
    if counterparty_name and not generic_counterparty:
        display_description = counterparty_name
    elif payment_description:
        display_description = _shorten_payment_description(payment_description)
    elif ultimate_creditor:
        display_description = ultimate_creditor
    elif counterparty_name:
        display_description = counterparty_name

    if not display_description:
        display_description = _shorten_payment_description(raw_86)

    return {
        **_empty_description_fields(),
        **counterparty,
        "payment_reference": payment_reference,
        "mandate_reference": mandate_reference,
        "creditor_id": creditor_id,
        "purpose_code": purpose_code,
        "return_reason": return_reason,
        "payment_description": payment_description,
        "ultimate_creditor": ultimate_creditor,
        "card_terminal": card_metadata["cleaned_text"] if has_card_details else "",
        "card_terminal_id": card_metadata["card_terminal_id"],
        "card_sequence_number": card_metadata["card_sequence_number"],
        "card_transaction_number": card_metadata["card_transaction_number"],
        "bank_transaction_label": "",
        "description_format": "structured" if (raw_86 or "").startswith("/") else "unstructured",
        "description": _normalize_space(display_description),
    }


def _parse_transaction_details(rest: str, amount_str: str) -> dict[str, str]:
    """Parse the post-amount portion of a :61: line into transaction fields."""
    tail = rest[11 + len(amount_str):]
    transaction_type = tail[:4] if len(tail) >= 4 else ""
    reference_part = tail[4:] if len(tail) >= 4 else tail
    customer_ref = reference_part
    bank_ref = ""
    if "//" in reference_part:
        customer_ref, bank_ref = reference_part.split("//", 1)
    bank_ref = bank_ref.split()[0].strip() if bank_ref else ""
    return {
        "transaction_type": transaction_type.strip(),
        "customer_ref": customer_ref.strip(),
        "bank_ref": bank_ref.strip(),
    }


def _format_signed_amount(amount_str: str, debit_credit: str) -> str:
    """Credit keeps the amount positive; debit makes it negative. Return comma decimals."""
    if not amount_str:
        return ""
    num_str = amount_str.replace(",", ".")
    try:
        num = float(num_str)
    except ValueError:
        return amount_str.replace(".", ",")
    if debit_credit == "D":
        num = -num
    s = f"{num:.2f}".replace(".", ",")
    if num > 0 and s[0] != "-":
        pass  # Positive amounts are written without a leading plus sign.
    return s


def _parse_balance_line(line: str) -> str:
    """Extract the amount from :60F:, :62F:, or :64: and return comma decimals."""
    m = re.search(r"[DC]\d{6}[A-Z]{3}([\d,\.]+)", line)
    if not m:
        return ""
    return m.group(1).replace(".", ",").strip()


def parse_mt940_custom(content: str, encoding: str = "utf-8") -> tuple[list[dict], str]:
    """
    Custom parser for MT940: extract :25:, :60F:, :61:, :86:, :62F:/:64: blocks.
    Returns (list of transaction dicts, account).
    """
    account = ""
    statement_number = ""
    transaction_reference = ""
    statement_currency = ""
    statement_opening_balance = ""
    statement_closing_balance = ""
    transactions = []
    lines = content.splitlines()

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(":20:"):
            transaction_reference = line[4:].strip()
            i += 1
            continue
        if line.startswith(":25:"):
            account = line[4:].strip()
            i += 1
            continue
        if line.startswith(":28C:"):
            statement_number = line[5:].strip()
            i += 1
            continue
        if line.startswith(":60F:"):
            m = re.search(r"[DC]\d{6}([A-Z]{3})", line)
            if m:
                statement_currency = m.group(1)
            statement_opening_balance = _parse_balance_line(line)
            i += 1
            continue
        if line.startswith(":62F:") or line.startswith(":64:"):
            if not statement_closing_balance:
                statement_closing_balance = _parse_balance_line(line)
            i += 1
            continue
        if line.startswith(":61:"):
            raw_61_parts = [line.strip()]
            rest = line[4:].strip()
            if len(rest) < 12:
                i += 1
                continue
            value_date_str = rest[0:6]
            entry_date_str = rest[6:10]
            dc = rest[10:11]
            if dc not in ("D", "C"):
                i += 1
                continue
            amount_match = re.match(r"(\d{1,15}[,.]?\d{0,2})", rest[11:])
            amount_str = amount_match.group(1) if amount_match else ""
            transaction_details = _parse_transaction_details(rest, amount_str)
            reference = transaction_details["bank_ref"] or transaction_details["customer_ref"]
            i += 1
            while i < len(lines) and lines[i].startswith("/") and not lines[i].startswith(":86:"):
                raw_61_parts.append(lines[i].strip())
                i += 1
            raw_61 = " ".join(raw_61_parts)

            description_parts = []
            if i < len(lines) and lines[i].startswith(":86:"):
                description_parts.append(lines[i][4:].rstrip())
                i += 1
                while i < len(lines) and not lines[i].strip().startswith(":"):
                    description_parts.append(lines[i].rstrip())
                    i += 1
            raw_86 = "".join(description_parts).replace("\n", " ")
            description_fields = _extract_description_fields(raw_86)
            description = description_fields["description"]
            raw_all_together = f"{raw_61} {raw_86}".strip()
            amt_normalized = _parse_amount_str(amount_str)
            signed_amount = _format_signed_amount(amt_normalized, dc)
            value_date = _parse_yyymmdd(value_date_str)

            transactions.append({
                "date": value_date,
                "description": description,
                "amount": signed_amount,
                "value_date": value_date,
                "entry_date": _parse_mmdd(entry_date_str),
                "currency": statement_currency,
                "debit_credit": dc,
                "transaction_type": transaction_details["transaction_type"],
                "bank_transaction_label": description_fields["bank_transaction_label"],
                "customer_ref": transaction_details["customer_ref"],
                "bank_ref": transaction_details["bank_ref"],
                "counterparty_name": description_fields["counterparty_name"],
                "counterparty_account": description_fields["counterparty_account"],
                "counterparty_iban": description_fields["counterparty_iban"],
                "counterparty_bic": description_fields["counterparty_bic"],
                "payment_reference": description_fields["payment_reference"],
                "mandate_reference": description_fields["mandate_reference"],
                "creditor_id": description_fields["creditor_id"],
                "purpose_code": description_fields["purpose_code"],
                "return_reason": description_fields["return_reason"],
                "payment_description": description_fields["payment_description"],
                "ultimate_creditor": description_fields["ultimate_creditor"],
                "card_terminal": description_fields["card_terminal"],
                "card_terminal_id": description_fields["card_terminal_id"],
                "card_sequence_number": description_fields["card_sequence_number"],
                "card_transaction_number": description_fields["card_transaction_number"],
                "description_format": description_fields["description_format"],
                "supplementary": description_fields["supplementary"],
                "account": account,
                "statement_number": statement_number,
                "transaction_reference": transaction_reference,
                "opening_balance": statement_opening_balance,
                "closing_balance": statement_closing_balance,
                "original_amount": amt_normalized,
                "signed_amount": signed_amount,
                "reference": reference,
                "cleared_description": description,
                "raw_61": raw_61,
                "raw_86": raw_86,
                "raw_all_together": raw_all_together,
            })
            continue
        i += 1

    if account and not statement_currency:
        m = re.search(r"([A-Z]{3})$", account)
        if m:
            statement_currency = m.group(1)
            for t in transactions:
                t["currency"] = statement_currency

    for t in transactions:
        if not t.get("opening_balance"):
            t["opening_balance"] = statement_opening_balance
        if not t.get("closing_balance"):
            t["closing_balance"] = statement_closing_balance

    return transactions, account


def _read_balances_from_content(content: str) -> tuple[str, str]:
    """Read opening/closing balance from content (:60F: and :62F:/:64:)."""
    opening, closing = "", ""
    for line in content.splitlines():
        if line.startswith(":60F:"):
            opening = _parse_balance_line(line)
        if line.startswith(":62F:") or line.startswith(":64:"):
            if not closing:
                closing = _parse_balance_line(line)
    return opening, closing
