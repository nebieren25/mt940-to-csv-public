# API

The API is served by FastAPI. Start the application first:

```bash
PYTHONPATH=. uvicorn src.web_app:app --reload --host 127.0.0.1 --port 8000
```

Interactive documentation is available at:

```text
http://127.0.0.1:8000/docs
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

Use `?format=csv` to receive CSV directly.

## Errors

- `422`: invalid parameters or invalid CSV columns
- `413`: upload exceeds `MAX_UPLOAD_MB`
- `500`: unexpected server error
