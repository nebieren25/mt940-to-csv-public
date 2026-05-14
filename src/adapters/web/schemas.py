"""
Pydantic schemas for web API request/response.
Validation: encoding, delimiter, decimal_sep (M4).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Allowed values for API validation (422 if invalid)
ALLOWED_ENCODINGS = ("utf-8", "latin-1", "cp1252", "iso-8859-1", "windows-1252")
ALLOWED_DELIMITERS = (",", ";", "\t")
ALLOWED_DECIMAL_SEP = (".", ",")

DelimiterType = Literal[",", ";", "\t"]
DecimalSepType = Literal[".", ","]


class DateRangeSummary(BaseModel):
    """Date range in summary (ISO dates)."""

    from_: str = Field(default="", alias="from", description="Earliest transaction date YYYY-MM-DD")
    to: str = Field(default="", description="Latest transaction date YYYY-MM-DD")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class YearlyBreakdownItem(BaseModel):
    """Income and expense per year."""

    year: str = ""
    income: float = 0.0
    expense: float = 0.0


class FinancialSummary(BaseModel):
    """Financial summary computed from loaded rows."""

    date_range: DateRangeSummary = Field(default_factory=lambda: DateRangeSummary(from_="", to=""))
    total_income: float = 0.0
    total_expense: float = 0.0
    net_change: float = 0.0
    total_count: int = 0
    income_count: int = 0
    expense_count: int = 0
    yearly_breakdown: list[YearlyBreakdownItem] = Field(default_factory=list, description="Income/expense per year")


class ConvertResponse(BaseModel):
    """Response after MT940 or CSV → rows/CSV."""

    success: bool = True
    account: str = ""
    row_count: int = 0
    rows: list[dict] = Field(default_factory=list, description="Transaction rows (CSV_HEADERS keys)")
    csv: str = Field(default="", description="Full CSV string for download")
    truncated: bool = Field(default=False, description="True if response was truncated by MAX_ROWS")
    total_rows: int | None = Field(default=None, description="Total rows before truncation (if truncated)")
    summary: FinancialSummary | None = Field(default=None, description="Financial summary when rows are present")


class ExportRequest(BaseModel):
    """Request to re-export rows to CSV with different options (preview → download)."""

    rows: list[dict] = Field(..., description="Transaction rows from /api/convert")
    delimiter: DelimiterType = Field(default=",", description="CSV field delimiter: , ; or tab")
    decimal_sep: DecimalSepType = Field(default=",", description="Decimal separator: . or ,")


class ExportResponse(BaseModel):
    """CSV string for download after re-export."""

    csv: str = Field(..., description="Full CSV string")
