# API

The API is served by FastAPI. Start the application first:

```bash
PYTHONPATH=. uvicorn src.web_app:app --reload --host 127.0.0.1 --port 8181
```

Interactive documentation is available at:

```text
http://127.0.0.1:8181/docs
```

## GET `/api/options`

Returns allowed conversion settings and configured limits.

Example response fields:

- `encodings`
- `delimiters`
- `decimal_separators`
- `max_upload_mb`
- `max_rows`

## POST `/api/convert`

Converts an uploaded MT940 file, or parses a compatible CSV upload.

Form fields:

- `file`: uploaded file
- `encoding`: input encoding
- `delimiter`: output CSV delimiter
- `decimal_sep`: output decimal separator
- `bank_profile`: `auto` (default), `ing`, `abn`, `rabo`, `knab`, or `raw`
- `description_style`: `sepa_overboeking_with_description` (default), `counterparty`, or `counterparty_with_description`

`auto` recognizes Knab account identifiers or statement headers. The Knab parser separates counterparty fields and remittance information, preserves wrapped descriptions, and assigns signed opening/closing balances from each statement page, including intermediate `60M`/`62M` pages. `date` and `value_date` remain the value date; `entry_date` remains the separately supplied month/day.

Response fields:

- `success`
- `rows`
- `csv`
- `account`
- `row_count`
- `summary`
- `truncated` and `total_rows` when row limiting is active

Use `?format=csv` to receive CSV directly.

## POST `/api/export`

Regenerates CSV from rows already parsed by the client.

JSON fields:

- `rows`
- `delimiter`
- `decimal_sep`
- `description_style`

Export formats existing rows; it does not reparse the source. To change the bank profile, call `/api/convert` again with the original file.

Use `?format=csv` to receive CSV directly.

## Errors

- `422`: invalid parameters or invalid CSV columns
- `413`: upload exceeds `MAX_UPLOAD_MB`
- `500`: unexpected server error
