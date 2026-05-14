"""
Financial summary from transaction rows. Pure logic; no I/O.
"""

import re
from datetime import datetime
from decimal import Decimal
from typing import Any


def _parse_amount(row: dict) -> Decimal:
    """Extract signed numeric amount from row. Prefer signed_amount; fallback amount + debit_credit."""
    raw = row.get("signed_amount") or row.get("amount") or ""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        dc = (row.get("debit_credit") or "").strip().upper()
        raw = row.get("amount") or ""
        if not raw:
            return Decimal("0")
        s = str(raw).strip().replace(",", ".")
        try:
            num = Decimal(s)
            return -num if dc == "D" else num
        except Exception:
            return Decimal("0")
    s = str(raw).strip().replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0")


def _parse_date(value: Any) -> str | None:
    """Parse date to YYYY-MM-DD. Accepts ISO, YYYY-MM-DD, DD-MM-YYYY, etc."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    s = str(value).strip()
    if not s:
        return None
    # ISO
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # DD-MM-YYYY or DD/MM/YYYY
    m = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})", s)
    if m:
        d, mo, y = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)
        return f"{y}-{mo}-{d}"
    # YYYY/MM/DD
    m = re.match(r"^(\d{4})[-/](\d{2})[-/](\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    return None


def compute_financial_summary(rows: list[dict]) -> dict | None:
    """
    Compute financial summary from transaction rows.
    Returns None if rows is empty; otherwise a dict with date_range, totals, counts, yearly_breakdown.
    Uses Decimal for amounts to avoid float issues.
    """
    if not rows:
        return None
    total_income = Decimal("0")
    total_expense = Decimal("0")
    income_count = 0
    expense_count = 0
    dates: list[str] = []
    yearly: dict[str, tuple[Decimal, Decimal]] = {}  # year -> (income, expense)
    for r in rows:
        amt = _parse_amount(r)
        d = _parse_date(r.get("value_date") or r.get("entry_date"))
        year = d[:4] if d and len(d) >= 4 else None
        if amt > 0:
            total_income += amt
            income_count += 1
            if year:
                inc, exp = yearly.get(year, (Decimal("0"), Decimal("0")))
                yearly[year] = (inc + amt, exp)
        elif amt < 0:
            total_expense += abs(amt)
            expense_count += 1
            if year:
                inc, exp = yearly.get(year, (Decimal("0"), Decimal("0")))
                yearly[year] = (inc, exp + abs(amt))
        if d:
            dates.append(d)
    date_from = min(dates) if dates else None
    date_to = max(dates) if dates else None
    yearly_breakdown = []
    for y in sorted(yearly.keys()):
        inc, exp = yearly[y]
        yearly_breakdown.append({"year": y, "income": float(inc), "expense": float(exp)})
    return {
        "date_range": {
            "from": date_from or "",
            "to": date_to or "",
        },
        "total_income": float(total_income),
        "total_expense": float(total_expense),
        "net_change": float(total_income - total_expense),
        "total_count": len(rows),
        "income_count": income_count,
        "expense_count": expense_count,
        "yearly_breakdown": yearly_breakdown,
    }
