# MT940 to CSV

MT940 to CSV is a small Python application for converting SWIFT MT940 bank statement files into CSV. It includes a reusable core library, a command-line interface, a FastAPI backend, and static web interfaces.

The project follows a hexagonal-style layout: the core package contains parsing and conversion logic without file or web I/O, while CLI and web modules act as adapters around it.

## Features

- Convert a single MT940 file or a folder of MT940 files to CSV.
- Upload MT940 or compatible CSV files through a web interface.
- Preview converted transactions in the browser.
- Export CSV with configurable encoding, delimiter, and decimal separator.
- Compute financial summary data for uploaded statements.
- Enforce optional upload and row limits through environment variables.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # pytest, pytest-cov
```

## Tests

Run tests from the project root:

```bash
PYTHONPATH=. pytest tests/unit -v -m unit
PYTHONPATH=. pytest tests/unit --cov=src/core --cov-report=term-missing
PYTHONPATH=. pytest tests -v   # all tests: unit + integration
```

## Documentation

- [Design notes](DESIGN.md)
- [API reference](docs/API.md)
- [Privacy notes](docs/PRIVACY.md)
- [Security policy](SECURITY.md)
- [Contributing guide](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)
- [License](LICENSE.md)

## CLI

The CLI accepts an input file or folder, an output path, optional folder mode, encoding, delimiter, and decimal separator settings.

```bash
PYTHONPATH=. python -m src.cli.main path/to/file.txt -o out.csv
PYTHONPATH=. python -m src.cli.main path/to/folder -d -o output_dir
```

## Web Application

Start the FastAPI application with Uvicorn:

```bash
PYTHONPATH=. uvicorn src.web_app:app --reload --host 127.0.0.1 --port 8181
```

- **Home:** http://127.0.0.1:8181 redirects to `/ui/web-ui-1-v3.html`.
- **Main UI v3:** http://127.0.0.1:8181/ui/web-ui-1-v3.html provides upload, conversion, financial summary, preview, and download.
- **UI 1:** http://127.0.0.1:8181/ui/web-ui-1.html uses a top settings panel and a lower preview table.
- **UI 2:** http://127.0.0.1:8181/ui/web-ui-2.html uses a sidebar settings panel and a right-side preview area.
- **API docs:** http://127.0.0.1:8181/docs

Typical flow: select an MT940 file, convert it, review the preview table, adjust encoding, delimiter, or decimal options, then download the CSV.

## Docker

Build and run the production container:

```bash
docker build -t mt-copy .
docker run --rm -p 8181:8181 mt-copy
```

The container starts Uvicorn with:

```bash
uvicorn src.web_app:app --host 0.0.0.0 --port 8181
```

For Coolify, use the Dockerfile build pack and set the application port to `8181`.

## API Summary

| Endpoint | Description |
|---------|-------------|
| GET `/api/options` | Returns allowed encodings, delimiters, decimal separators, and configured limits such as `max_upload_mb` and `max_rows`. |
| POST `/api/convert` | Accepts multipart form data with `file`, `encoding`, `delimiter`, and `decimal_sep`. Returns JSON with `rows`, `csv`, `account`, and `row_count`; may also include `truncated` and `total_rows`. Use `?format=csv` to receive a CSV file directly. |
| POST `/api/export` | Accepts JSON with `rows`, `delimiter`, and `decimal_sep`, then regenerates CSV output. Use `?format=csv` to receive a CSV file directly. |

Invalid parameters return **422**. Runtime errors return a JSON response such as `{"detail": "..."}`.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | INFO | Logging level. |
| `LOG_FILE` | unset | Optional log file path. When set, logs are also written to this file. |
| `MAX_FILE_SIZE_MB` | 0 | If greater than 0, uploads above this size are logged as warnings. |
| `MAX_UPLOAD_MB` | 0 | If greater than 0, uploads above this size are rejected with **413**. |
| `MAX_ROWS` | 0 | If greater than 0, JSON responses are limited to the first N rows and include `truncated` and `total_rows`. |

## Privacy and Data Safety

Do not commit real MT940 files, exported CSV files, account numbers, IBANs, customer names, transaction descriptions, or screenshots containing financial data. Use synthetic examples only.

Uploaded files are processed in memory for the request. The application does not intentionally store uploaded statements on disk.

## Project Structure

```text
mt-copy-public/
├── docs/                 # API and privacy documentation
├── src/
│   ├── core/             # Domain logic: parsing, conversion, summaries
│   │   ├── domain.py     # CSV headers and MT940 description tags
│   │   ├── parsing.py    # Custom MT940 parser and parsing helpers
│   │   ├── library_adapter.py   # mt-940 library wrapper
│   │   ├── convert.py    # Content-to-rows and rows-to-CSV helpers
│   │   ├── csv_parse.py  # CSV upload parsing
│   │   ├── insights.py   # Financial insight aggregations
│   │   └── summary.py    # Financial summary calculations
│   ├── adapters/
│   │   ├── file_io.py    # File reading and writing for the CLI
│   │   └── web/          # FastAPI routes, schemas, and logging config
│   ├── cli/main.py       # CLI entry point
│   └── web_app.py        # FastAPI app, static UI mount, and redirects
├── web-ui/               # Static HTML and JavaScript served under /ui
├── tests/
│   ├── unit/             # Core unit tests
│   └── integration/      # Web API integration tests
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
├── .dockerignore
├── pyproject.toml
├── CHANGELOG.md
├── CONTRIBUTING.md
├── DESIGN.md
├── LICENSE.md
├── SECURITY.md
└── README.md
```

## Milestones

- **M0-M1:** Core extraction, pytest setup, and unit tests.
- **M2:** Minimal web application for upload, conversion, JSON, and CSV responses.
- **M3:** CSV preview and export regeneration through `POST /api/export`.
- **M4:** Settings panel and request validation with Pydantic.
- **M5:** Error handling and logging through `LOG_LEVEL`, `LOG_FILE`, and a 500 handler.
- **M6:** Upload and row limits with `MAX_UPLOAD_MB`, `MAX_ROWS`, 413 handling, and truncation metadata.
- **Web UI:** Static browser interfaces served from `web-ui/`.
