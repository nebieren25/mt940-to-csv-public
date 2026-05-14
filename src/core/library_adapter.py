"""
Adapter for mt-940 library: parse MT940 content (no file I/O).
Returns (rows, account) or (None, None) on failure.
"""

from src.core.parsing import (
    _cleared_description,
    _format_signed_amount,
    _read_balances_from_content,
)


def parse_with_library(content: str, encoding: str = "utf-8") -> tuple[list[dict] | None, str | None]:
    """
    Parse MT940 using mt-940 library.
    Accepts content string (caller is responsible for reading file/upload).
    Returns (rows, account) or (None, None) on failure.
    """
    try:
        import mt940
    except ImportError:
        return None, None

    try:
        transactions_obj = mt940.parse(content)
    except Exception:
        return None, None

    opening_balance, closing_balance = _read_balances_from_content(content)

    account = ""
    rows = []
    try:
        if hasattr(transactions_obj, "data") and transactions_obj.data:
            acc_val = transactions_obj.data.get("account_identification") or transactions_obj.data.get("account")
            if acc_val:
                account = str(acc_val) if not hasattr(acc_val, "value") else getattr(acc_val, "value", str(acc_val))
        for t in transactions_obj:
            if getattr(t, "amount", None) is None:
                continue
            amt = t.amount
            amount_str = str(getattr(amt, "amount", ""))
            if "," in amount_str and "." not in amount_str:
                amount_str = amount_str.replace(",", ".")
            dc = getattr(amt, "status", "C") if amt else "C"
            desc = getattr(t, "data", "") or ""
            if hasattr(t, "transaction_details"):
                desc = getattr(t.transaction_details, "value", desc) or desc
            desc_str = str(desc) if desc else ""
            rows.append({
                "entry_date": "",
                "debit_credit": dc,
                "amount": amount_str,
                "currency": getattr(amt, "currency", "") or "",
                "reference": getattr(t, "id", "") or getattr(t, "reference", "") or "",
                "description": desc_str,
                "raw_61": "",
                "raw_86": "",
                "raw_all_together": "",
                "account": account,
                "opening_balance": opening_balance,
                "closing_balance": closing_balance,
                "value_date": getattr(t.date, "strftime", lambda x: str(t.date))("%d-%m-%Y") if hasattr(t, "date") and t.date else "",
                "cleared_description": _cleared_description(desc_str),
                "signed_amount": _format_signed_amount(amount_str, dc),
            })
        if rows and not account and hasattr(transactions_obj, "data"):
            acc_val = transactions_obj.data.get("account_identification") or transactions_obj.data.get("account")
            if acc_val:
                account = str(acc_val) if not hasattr(acc_val, "value") else getattr(acc_val, "value", str(acc_val))
                for r in rows:
                    r["account"] = account
        return rows, account
    except Exception:
        return None, None
