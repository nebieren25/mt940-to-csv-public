"""
MT940 parsing: custom parser and pure helpers.
No file I/O; operates on content string only.
"""

import re

from src.core.domain import DESCRIPTION_TAGS


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
    s = description
    for tag in DESCRIPTION_TAGS:
        s = s.replace(tag, " ")
    # Remove IBAN-like segments (e.g. NL94INGB0709778465)
    s = re.sub(r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7,10}\b", " ", s)
    # Remove BIC (e.g. INGBNL2A, ABNANL2A)
    s = re.sub(r"\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}\b", " ", s)
    # Remove leftover tag values (USTD = unstructured)
    s = re.sub(r"\bUSTD\b", " ", s)
    # Collapse slashes and multiple spaces
    s = re.sub(r"[/]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _format_signed_amount(amount_str: str, debit_credit: str) -> str:
    """Credit = +tutar, Debit = -tutar; virgüllü string (31,25 veya -31,25)."""
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
        pass  # +31,25 yerine 31,25 yazılabilir; negatifte - mutlaka
    return s


def _parse_balance_line(line: str) -> str:
    """:60F: veya :62F: / :64: satırından tutarı al (virgüllü)."""
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
    statement_currency = ""
    statement_opening_balance = ""
    statement_closing_balance = ""
    transactions = []
    lines = content.splitlines()

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(":25:"):
            account = line[4:].strip()
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
            ref_match = re.search(r"N[A-Z]*REF//(\S+)", rest)
            reference = ref_match.group(1) if ref_match else ""
            i += 1
            while i < len(lines) and lines[i].startswith("/") and not lines[i].startswith(":86:"):
                raw_61_parts.append(lines[i].strip())
                i += 1
            raw_61 = " ".join(raw_61_parts)

            description_parts = []
            if i < len(lines) and lines[i].startswith(":86:"):
                description_parts.append(lines[i][4:].strip())
                i += 1
                while i < len(lines) and not lines[i].strip().startswith(":"):
                    description_parts.append(lines[i].strip())
                    i += 1
            raw_86 = " ".join(description_parts).replace("\n", " ")
            description = raw_86.strip()
            raw_all_together = f"{raw_61} {raw_86}".strip()
            cleared = _cleared_description(description)
            amt_normalized = _parse_amount_str(amount_str)

            transactions.append({
                "entry_date": _parse_mmdd(entry_date_str),
                "debit_credit": dc,
                "amount": amt_normalized,
                "currency": statement_currency,
                "reference": reference,
                "description": description,
                "raw_61": raw_61,
                "raw_86": raw_86,
                "raw_all_together": raw_all_together,
                "account": account,
                "opening_balance": statement_opening_balance,
                "closing_balance": statement_closing_balance,
                "value_date": _parse_yyymmdd(value_date_str),
                "cleared_description": cleared,
                "signed_amount": _format_signed_amount(amt_normalized, dc),
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
