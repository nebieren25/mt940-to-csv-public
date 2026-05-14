"""
Web API routes: upload MT940, convert, return rows + CSV.
M5: Logging for parse/convert errors and large file warning.
"""

import os

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response

from src.core.convert import content_to_rows, rows_to_csv_string
from src.core.csv_parse import CSVColumnError, csv_content_to_rows
from src.core.summary import compute_financial_summary

from .logging_config import get_logger
from .schemas import (
    ALLOWED_DECIMAL_SEP,
    ALLOWED_DELIMITERS,
    ALLOWED_ENCODINGS,
    ConvertResponse,
    ExportRequest,
    ExportResponse,
    FinancialSummary,
)

router = APIRouter(prefix="/api", tags=["convert"])
logger = get_logger(__name__)

# M6: Limits (env). 0 = disabled.
# Warn when file size exceeds this (bytes).
_MAX_FILE_SIZE_MB = float(os.environ.get("MAX_FILE_SIZE_MB", "0") or 0)
MAX_FILE_SIZE_WARN_BYTES = int(_MAX_FILE_SIZE_MB * 1024 * 1024) if _MAX_FILE_SIZE_MB else 0
# Hard limit: reject uploads larger than this (bytes). 0 = no limit.
_MAX_UPLOAD_MB = float(os.environ.get("MAX_UPLOAD_MB", "0") or 0)
MAX_UPLOAD_BYTES = int(_MAX_UPLOAD_MB * 1024 * 1024) if _MAX_UPLOAD_MB else 0
# Optional max rows: truncate response to first N rows (preview). 0 = no limit.
MAX_ROWS = int(os.environ.get("MAX_ROWS", "0") or 0)


@router.get("/options")
def get_options() -> dict:
    """Return allowed values for encoding, delimiter, decimal_sep; and limits (M6)."""
    return {
        "encodings": list(ALLOWED_ENCODINGS),
        "delimiters": [
            {"value": ",", "label": "Comma (,)"},
            {"value": ";", "label": "Semicolon (;)"},
            {"value": "\t", "label": "Tab"},
        ],
        "decimal_sep": [
            {"value": ",", "label": "Comma (,)"},
            {"value": ".", "label": "Period (.)"},
        ],
        "limits": {
            "max_upload_mb": _MAX_UPLOAD_MB if _MAX_UPLOAD_MB else None,
            "max_rows": MAX_ROWS if MAX_ROWS else None,
        },
    }


def _validate_convert_options(
    encoding: str,
    delimiter: str,
    decimal_sep: str,
) -> None:
    """Raise 422 if any option is not allowed."""
    if encoding not in ALLOWED_ENCODINGS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid encoding. Allowed: {', '.join(ALLOWED_ENCODINGS)}",
        )
    if delimiter not in ALLOWED_DELIMITERS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid delimiter. Allowed: comma, semicolon, tab",
        )
    if decimal_sep not in ALLOWED_DECIMAL_SEP:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid decimal_sep. Allowed: . or ,",
        )


@router.post("/convert", response_model=None)
async def convert_mt940(
    file: UploadFile = File(..., description="MT940 file"),
    encoding: str = Form("utf-8"),
    delimiter: str = Form(","),
    decimal_sep: str = Form(","),
    format: str | None = Query(None, alias="format", description="Set to 'csv' for file download"),
) -> ConvertResponse | Response:
    """
    Upload MT940 file and convert to CSV.
    Returns JSON with rows and CSV string, or raw CSV file if format=csv.
    Validates encoding, delimiter, decimal_sep (422 if invalid).
    """
    _validate_convert_options(encoding, delimiter, decimal_sep)
    try:
        raw = await file.read()
    except Exception as e:
        logger.warning("Failed to read upload: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e)) from e

    if MAX_UPLOAD_BYTES and len(raw) > MAX_UPLOAD_BYTES:
        logger.warning("Rejected upload: %s bytes > %s", len(raw), MAX_UPLOAD_BYTES)
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {_MAX_UPLOAD_MB:.0f} MB",
        )

    if MAX_FILE_SIZE_WARN_BYTES and len(raw) > MAX_FILE_SIZE_WARN_BYTES:
        logger.warning(
            "Large file: %s bytes (filename=%s); consider MAX_FILE_SIZE_MB",
            len(raw),
            file.filename or "?",
        )

    try:
        content = raw.decode(encoding)
    except UnicodeDecodeError as e:
        logger.warning("Decode error for %s: %s", file.filename or "?", e)
        raise HTTPException(status_code=400, detail=f"Invalid encoding: {e}") from e

    filename_lower = (file.filename or "").lower()
    is_csv = filename_lower.endswith(".csv")

    if is_csv:
        try:
            rows = csv_content_to_rows(content)
        except CSVColumnError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        account = ""
    else:
        rows, account = content_to_rows(content, encoding)

    if not rows:
        logger.info("No transactions in file: %s", file.filename or "?")
        if format == "csv":
            return Response(content="", status_code=200, media_type="text/csv")
        return ConvertResponse(
            success=False,
            account=account,
            row_count=0,
            rows=[],
            csv="",
        )

    total_rows = len(rows)
    truncated = False
    if MAX_ROWS and total_rows > MAX_ROWS:
        rows = rows[:MAX_ROWS]
        truncated = True
        logger.info(
            "Truncated to %d rows (max_rows=%d, total=%d), file=%s",
            len(rows),
            MAX_ROWS,
            total_rows,
            file.filename or "?",
        )
    else:
        logger.info(
            "Converted %s: %d rows, account=%s",
            file.filename or "?",
            total_rows,
            account or "?",
        )

    csv_string = rows_to_csv_string(rows, delimiter=delimiter, decimal_sep=decimal_sep)
    summary_dict = compute_financial_summary(rows)
    summary = FinancialSummary.model_validate(summary_dict) if summary_dict else None

    if format == "csv":
        filename = (file.filename or "statement").rsplit(".", 1)[0] + ".csv"
        return Response(
            content=csv_string.encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return ConvertResponse(
        success=True,
        account=account,
        row_count=len(rows),
        rows=rows,
        csv=csv_string,
        truncated=truncated,
        total_rows=total_rows if truncated else None,
        summary=summary,
    )


@router.post("/export", response_model=None)
async def export_csv(
    body: ExportRequest,
    format: str | None = Query(None, alias="format", description="Set to 'csv' for file download"),
) -> ExportResponse | Response:
    """
    Re-export existing rows to CSV with different delimiter/decimal.
    Use after /api/convert to change options without re-uploading.
    """
    csv_string = rows_to_csv_string(
        body.rows,
        delimiter=body.delimiter,
        decimal_sep=body.decimal_sep,
    )
    if format == "csv":
        return Response(
            content=csv_string.encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="export.csv"'},
        )
    return ExportResponse(csv=csv_string)
