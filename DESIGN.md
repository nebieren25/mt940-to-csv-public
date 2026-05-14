# Design notes: MT940 → CSV extensions

Short note on key design decisions for the Financial Summary, CSV upload, and preview column order.

## Financial summary: backend vs frontend

- **Summary is computed on the backend** (in `src/core/summary.py`) and included in the `POST /api/convert` JSON response when rows are present. This keeps a single source of truth and avoids duplicating business logic in the frontend; the UI only formats and displays the values (e.g. DD-MM-YYYY, decimal separator).
- **Decimal** is used for all amount calculations in the summary to avoid floating-point errors. Results are converted to float only for the JSON payload.
- If no data is loaded, the summary section is hidden in the UI; the API omits or sets `summary` to `null` when there are no rows.

## CSV parsing and 422 handling

- **CSV parsing** is implemented in core as a pure function (`src/core/csv_parse.csv_content_to_rows`): it takes a content string and optional delimiter, and returns a list of row dicts with keys matching `CSV_HEADERS`. No I/O; the route decodes the uploaded file bytes using the selected encoding and passes the string to the parser.
- **File type** is detected by filename extension (e.g. `.csv`). For CSV files, the MT940 conversion is skipped and the CSV is parsed instead. The same response shape (rows, csv, summary) is returned so the UI works unchanged.
- **Required columns**: the parser expects at least one date column (`value_date` or `entry_date`) and one amount column (`signed_amount` or `amount`). If the CSV headers are missing or invalid, the core raises `CSVColumnError`; the route catches it and returns **422** with a clear message (e.g. “CSV columns missing or invalid. Required: …”). The frontend shows this message in the error area.
- **Delimiter**: if not provided, the parser tries comma, semicolon, and tab and validates that the resulting headers include the required columns. The form’s delimiter is used for *output* CSV (and for MT940 conversion); CSV *upload* parsing uses auto-detection (or could be extended later with a form field for CSV delimiter).
- The system remains **stateless**: uploaded file content is not written to disk; it is held in memory for the request only.

## Preview table column order

- Only the **preview** table column order in the UI was changed: **Description** is shown immediately after **Account (IBAN)** (order: Row # | Date | Account (IBAN) | Description | Amount | CCY | Ref. ID). This affects only the HTML table headers and the JS that builds the table body in `web-ui/mt940-api.js`.
- **Export CSV column order** is unchanged: `CSV_HEADERS` in `src/core/domain.py` is not modified, so downloaded CSV files keep the existing column order and remain compatible with existing tools or workflows.
