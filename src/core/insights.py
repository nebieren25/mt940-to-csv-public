"""
Insights aggregation: scope filter, metrics, and drill-down breakdown.
Pure logic; no I/O. JS port should mirror these rules.
"""

from decimal import Decimal
from typing import Any

from src.core.summary import _parse_amount, _parse_date

MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def _row_year_quarter_month(row: dict) -> tuple[int | None, int | None, int | None]:
    """Return (year, quarter, month) from row date. None if date missing/invalid."""
    d = _parse_date(row.get("value_date") or row.get("entry_date"))
    if not d or len(d) < 10:
        return None, None, None
    try:
        y = int(d[:4])
        m = int(d[5:7])
        q = (m - 1) // 3 + 1
        return y, q, m
    except (ValueError, TypeError):
        return None, None, None


def filter_rows_by_scope(
    rows: list[dict],
    scope: dict[str, int | None],
) -> list[dict]:
    """
    Filter rows by scope. scope = {year: int|None, quarter: int|None, month: int|None}.
    None means "All" for that level.
    """
    want_year = scope.get("year")
    want_quarter = scope.get("quarter")
    want_month = scope.get("month")

    out: list[dict] = []
    for r in rows:
        y, q, m = _row_year_quarter_month(r)
        if y is None:
            continue
        if want_year is not None and y != want_year:
            continue
        if want_quarter is not None and q != want_quarter:
            continue
        if want_month is not None and m != want_month:
            continue
        out.append(r)
    return out


def compute_metrics(rows: list[dict]) -> dict[str, Any]:
    """
    Single-pass metrics: date range, income/expense/net, counts, avg txn amounts.
    Optional: most_frequent_description (normalized).
    """
    if not rows:
        return {
            "min_date": None,
            "max_date": None,
            "total_income": 0.0,
            "total_expense": 0.0,
            "net": 0.0,
            "total_count": 0,
            "income_count": 0,
            "expense_count": 0,
            "avg_income_txn": 0.0,
            "avg_expense_txn": 0.0,
            "most_frequent_description": None,
        }

    total_income = Decimal("0")
    total_expense = Decimal("0")
    income_count = 0
    expense_count = 0
    income_sum_for_avg = Decimal("0")
    expense_sum_for_avg = Decimal("0")
    dates: list[str] = []
    desc_counts: dict[str, int] = {}

    for r in rows:
        amt = _parse_amount(r)
        d = _parse_date(r.get("value_date") or r.get("entry_date"))
        if d:
            dates.append(d)
        if amt > 0:
            total_income += amt
            income_count += 1
            income_sum_for_avg += amt
        elif amt < 0:
            total_expense += abs(amt)
            expense_count += 1
            expense_sum_for_avg += abs(amt)
        desc = (r.get("cleared_description") or r.get("description") or "").strip()
        if desc:
            key = " ".join(desc.lower().split())
            desc_counts[key] = desc_counts.get(key, 0) + 1

    min_date = min(dates) if dates else None
    max_date = max(dates) if dates else None
    most_freq = None
    if desc_counts:
        best = max(desc_counts.items(), key=lambda x: x[1])
        most_freq = best[0]

    return {
        "min_date": min_date,
        "max_date": max_date,
        "total_income": float(total_income),
        "total_expense": float(total_expense),
        "net": float(total_income - total_expense),
        "total_count": len(rows),
        "income_count": income_count,
        "expense_count": expense_count,
        "avg_income_txn": float(income_sum_for_avg / income_count) if income_count else 0.0,
        "avg_expense_txn": float(expense_sum_for_avg / expense_count) if expense_count else 0.0,
        "most_frequent_description": most_freq,
    }


def compute_breakdown(rows: list[dict]) -> list[dict]:
    """
    Hierarchical breakdown: years -> quarters -> months.
    Each item: level (0=year, 1=quarter, 2=month), period (label), year, quarter, month,
    income, expense, net, count, avg_txn.
    Quarter = (month-1)//3 + 1. Empty periods (count=0) can be included for UI to hide.
    """
    if not rows:
        return []

    # Aggregate by (year, quarter, month) - month None for quarter row, both None for year row
    # We'll build year -> (quarter -> (month -> totals))
    year_totals: dict[int, tuple[Decimal, Decimal, int]] = {}  # income, expense, count
    quarter_totals: dict[tuple[int, int], tuple[Decimal, Decimal, int]] = {}
    month_totals: dict[tuple[int, int, int], tuple[Decimal, Decimal, int]] = {}

    for r in rows:
        y, q, m = _row_year_quarter_month(r)
        if y is None:
            continue
        amt = _parse_amount(r)
        inc = amt if amt > 0 else Decimal("0")
        exp = abs(amt) if amt < 0 else Decimal("0")
        # year
        yi, ye, yc = year_totals.get(y, (Decimal("0"), Decimal("0"), 0))
        year_totals[y] = (yi + inc, ye + exp, yc + 1)
        # quarter
        if q is not None:
            key_q = (y, q)
            qi, qe, qc = quarter_totals.get(key_q, (Decimal("0"), Decimal("0"), 0))
            quarter_totals[key_q] = (qi + inc, qe + exp, qc + 1)
        # month
        if m is not None and q is not None:
            key_m = (y, q, m)
            mi, me, mc = month_totals.get(key_m, (Decimal("0"), Decimal("0"), 0))
            month_totals[key_m] = (mi + inc, me + exp, mc + 1)

    result: list[dict] = []
    for year in sorted(year_totals.keys()):
        yi, ye, yc = year_totals[year]
        net = yi - ye
        avg = float((yi + ye) / yc) if yc else 0.0
        result.append({
            "level": 0,
            "period": str(year),
            "year": year,
            "quarter": None,
            "month": None,
            "income": float(yi),
            "expense": float(ye),
            "net": float(net),
            "count": yc,
            "avg_txn": avg,
        })
        for quarter in (1, 2, 3, 4):
            key_q = (year, quarter)
            qi, qe, qc = quarter_totals.get(key_q, (Decimal("0"), Decimal("0"), 0))
            net_q = float(qi - qe)
            avg_q = float((qi + qe) / qc) if qc else 0.0
            result.append({
                "level": 1,
                "period": f"Q{quarter} {year}",
                "year": year,
                "quarter": quarter,
                "month": None,
                "income": float(qi),
                "expense": float(qe),
                "net": net_q,
                "count": qc,
                "avg_txn": avg_q,
            })
            for month in range((quarter - 1) * 3 + 1, quarter * 3 + 1):
                key_m = (year, quarter, month)
                mi, me, mc = month_totals.get(key_m, (Decimal("0"), Decimal("0"), 0))
                net_m = float(mi - me)
                avg_m = float((mi + me) / mc) if mc else 0.0
                result.append({
                    "level": 2,
                    "period": MONTH_NAMES[month - 1],
                    "year": year,
                    "quarter": quarter,
                    "month": month,
                    "income": float(mi),
                    "expense": float(me),
                    "net": net_m,
                    "count": mc,
                    "avg_txn": avg_m,
                })
    return result


def check_currencies(rows: list[dict]) -> str | None:
    """
    Return None if no/single currency, "mixed" if more than one currency present.
    """
    currencies: set[str] = set()
    for r in rows:
        c = (r.get("currency") or "").strip()
        if c:
            currencies.add(c)
    if len(currencies) <= 1:
        return None
    return "mixed"
