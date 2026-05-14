"""
Integration tests for web API (Milestone 2+).
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(app):
    """TestClient for FastAPI app."""
    return TestClient(app)


@pytest.mark.integration
class TestConvertEndpoint:
    """POST /api/convert: upload MT940, get JSON or CSV."""

    def test_convert_returns_200_and_json_with_rows(
        self, client: TestClient, sample_mt940_content: str
    ) -> None:
        response = client.post(
            "/api/convert",
            files={"file": ("test.mt940", sample_mt940_content.encode("utf-8"), "text/plain")},
            data={"encoding": "utf-8", "delimiter": ",", "decimal_sep": ","},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["account"] == "NL00TEST0123456789EUR"
        assert data["row_count"] >= 1
        assert len(data["rows"]) == data["row_count"]
        assert "entry_date" in data["rows"][0]
        assert data["csv"]
        assert "entry_date" in data["csv"]
        assert "summary" in data
        assert data["summary"] is not None
        s = data["summary"]
        assert "date_range" in s
        assert "from" in s["date_range"] or "from_" in s["date_range"]
        assert "to" in s["date_range"]
        assert "total_income" in s
        assert "total_expense" in s
        assert "net_change" in s
        assert "total_count" in s
        assert "income_count" in s
        assert "expense_count" in s

    def test_convert_format_csv_returns_csv_file(
        self, client: TestClient, sample_mt940_content: str
    ) -> None:
        response = client.post(
            "/api/convert?format=csv",
            files={"file": ("stmt.txt", sample_mt940_content.encode("utf-8"), "text/plain")},
            data={"encoding": "utf-8", "delimiter": ","},
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        assert "attachment" in response.headers.get("content-disposition", "")
        body = response.text
        assert "entry_date" in body
        assert "signed_amount" in body

    def test_convert_empty_file_returns_success_false(
        self, client: TestClient
    ) -> None:
        response = client.post(
            "/api/convert",
            files={"file": ("empty.txt", b"", "text/plain")},
            data={"encoding": "utf-8"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["row_count"] == 0
        assert data["rows"] == []

    def test_convert_csv_upload_returns_200_with_rows_and_summary(
        self, client: TestClient
    ) -> None:
        content = "value_date,account,signed_amount,currency,reference,description\n2024-01-15,NL00BANK,100.50,EUR,ref1,Pay\n2024-01-16,NL00BANK,-25.00,EUR,ref2,Fee"
        response = client.post(
            "/api/convert",
            files={"file": ("data.csv", content.encode("utf-8"), "text/csv")},
            data={"encoding": "utf-8", "delimiter": ",", "decimal_sep": ","},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["row_count"] == 2
        assert len(data["rows"]) == 2
        assert data["summary"] is not None
        assert data["summary"]["total_income"] == 100.5
        assert data["summary"]["total_expense"] == 25.0
        assert data["summary"]["net_change"] == 75.5
        assert data["summary"]["total_count"] == 2
        assert "entry_date" in data["csv"] or "value_date" in data["csv"]

    def test_convert_csv_missing_columns_returns_422(
        self, client: TestClient
    ) -> None:
        content = "foo,bar\n1,2"
        response = client.post(
            "/api/convert",
            files={"file": ("bad.csv", content.encode("utf-8"), "text/csv")},
            data={"encoding": "utf-8", "delimiter": ",", "decimal_sep": ","},
        )
        assert response.status_code == 422
        detail = response.json().get("detail", "")
        if isinstance(detail, list):
            detail = " ".join(str(d.get("msg", d)) for d in detail)
        assert "column" in detail.lower() or "missing" in detail.lower() or "required" in detail.lower()

    def test_export_after_csv_upload_works(
        self, client: TestClient
    ) -> None:
        content = "value_date,account,signed_amount,currency\n2024-01-01,NL,10.00,EUR"
        convert_resp = client.post(
            "/api/convert",
            files={"file": ("data.csv", content.encode("utf-8"), "text/csv")},
            data={"encoding": "utf-8", "delimiter": ",", "decimal_sep": ","},
        )
        assert convert_resp.status_code == 200
        rows = convert_resp.json()["rows"]
        export_resp = client.post(
            "/api/export",
            json={"rows": rows, "delimiter": ";", "decimal_sep": ","},
        )
        assert export_resp.status_code == 200
        assert "csv" in export_resp.json()
        assert "value_date" in export_resp.json()["csv"] or "entry_date" in export_resp.json()["csv"]
        assert ";" in export_resp.json()["csv"]

    def test_root_redirects_to_ui(self, client: TestClient) -> None:
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 302
        assert "/ui/web-ui-1-v3.html" in response.headers.get("location", "")

    def test_ui_1_returns_html(self, client: TestClient) -> None:
        response = client.get("/ui/web-ui-1.html")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "MT940" in response.text
        assert "Download CSV" in response.text
        assert "Source File" in response.text or "Conversion Settings" in response.text

    def test_ui_2_returns_html(self, client: TestClient) -> None:
        response = client.get("/ui/web-ui-2.html")
        assert response.status_code == 200
        assert "MT940" in response.text
        assert "Download CSV" in response.text


@pytest.mark.integration
class TestExportEndpoint:
    """POST /api/export: re-export rows with delimiter/decimal (reconvert without re-upload)."""

    def test_export_returns_csv_in_json(
        self, client: TestClient, sample_mt940_content: str
    ) -> None:
        convert_resp = client.post(
            "/api/convert",
            files={"file": ("x.txt", sample_mt940_content.encode("utf-8"), "text/plain")},
            data={"encoding": "utf-8", "delimiter": ",", "decimal_sep": ","},
        )
        assert convert_resp.status_code == 200
        rows = convert_resp.json()["rows"]
        export_resp = client.post(
            "/api/export",
            json={"rows": rows, "delimiter": ";", "decimal_sep": ","},
        )
        assert export_resp.status_code == 200
        data = export_resp.json()
        assert "csv" in data
        assert "entry_date" in data["csv"]
        assert ";" in data["csv"]

    def test_export_format_csv_returns_attachment(
        self, client: TestClient, sample_mt940_content: str
    ) -> None:
        convert_resp = client.post(
            "/api/convert",
            files={"file": ("x.txt", sample_mt940_content.encode("utf-8"), "text/plain")},
            data={"encoding": "utf-8"},
        )
        rows = convert_resp.json()["rows"]
        export_resp = client.post(
            "/api/export?format=csv",
            json={"rows": rows, "delimiter": ",", "decimal_sep": ","},
        )
        assert export_resp.status_code == 200
        assert "text/csv" in export_resp.headers.get("content-type", "")
        assert "attachment" in export_resp.headers.get("content-disposition", "")
        assert "entry_date" in export_resp.text


@pytest.mark.integration
class TestValidation422:
    """Invalid options return 422 (M4: ayar paneli + validasyon)."""

    def test_convert_invalid_encoding_returns_422(
        self, client: TestClient, sample_mt940_content: str
    ) -> None:
        response = client.post(
            "/api/convert",
            files={"file": ("x.txt", sample_mt940_content.encode("utf-8"), "text/plain")},
            data={"encoding": "invalid-encoding", "delimiter": ",", "decimal_sep": ","},
        )
        assert response.status_code == 422
        assert "encoding" in response.json().get("detail", "").lower() or "invalid" in response.json().get("detail", "").lower()

    def test_convert_invalid_delimiter_returns_422(
        self, client: TestClient, sample_mt940_content: str
    ) -> None:
        response = client.post(
            "/api/convert",
            files={"file": ("x.txt", sample_mt940_content.encode("utf-8"), "text/plain")},
            data={"encoding": "utf-8", "delimiter": "x", "decimal_sep": ","},
        )
        assert response.status_code == 422
        assert "delimiter" in response.json().get("detail", "").lower()

    def test_convert_invalid_decimal_sep_returns_422(
        self, client: TestClient, sample_mt940_content: str
    ) -> None:
        response = client.post(
            "/api/convert",
            files={"file": ("x.txt", sample_mt940_content.encode("utf-8"), "text/plain")},
            data={"encoding": "utf-8", "delimiter": ",", "decimal_sep": "x"},
        )
        assert response.status_code == 422
        assert "decimal" in response.json().get("detail", "").lower()

    def test_export_invalid_delimiter_returns_422(
        self, client: TestClient, sample_mt940_content: str
    ) -> None:
        convert_resp = client.post(
            "/api/convert",
            files={"file": ("x.txt", sample_mt940_content.encode("utf-8"), "text/plain")},
            data={"encoding": "utf-8"},
        )
        rows = convert_resp.json()["rows"]
        response = client.post(
            "/api/export",
            json={"rows": rows, "delimiter": "invalid", "decimal_sep": ","},
        )
        assert response.status_code == 422

    def test_get_options_returns_allowed_values(self, client: TestClient) -> None:
        response = client.get("/api/options")
        assert response.status_code == 200
        data = response.json()
        assert "encodings" in data
        assert "utf-8" in data["encodings"]
        assert "delimiters" in data
        assert "decimal_sep" in data


@pytest.mark.integration
class TestErrorHandling:
    """M5: Consistent error response and 500 handler."""

    def test_app_has_exception_handler_for_exception(self, app) -> None:
        """Global Exception handler is registered (returns 500 with consistent detail)."""
        assert hasattr(app, "exception_handlers")
        assert Exception in app.exception_handlers

    def test_400_decode_error_returns_consistent_detail(
        self, client: TestClient
    ) -> None:
        response = client.post(
            "/api/convert",
            files={"file": ("x.txt", b"\xff\xfe invalid", "text/plain")},
            data={"encoding": "utf-8", "delimiter": ",", "decimal_sep": ","},
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "encoding" in data["detail"].lower() or "decode" in data["detail"].lower()


@pytest.mark.integration
class TestLimitsM6:
    """M6: MAX_UPLOAD_MB and MAX_ROWS."""

    def test_413_when_file_exceeds_max_upload(
        self, client: TestClient, sample_mt940_content: str
    ) -> None:
        with patch("src.adapters.web.routes.MAX_UPLOAD_BYTES", 5):
            response = client.post(
                "/api/convert",
                files={"file": ("x.txt", sample_mt940_content.encode("utf-8"), "text/plain")},
                data={"encoding": "utf-8", "delimiter": ",", "decimal_sep": ","},
            )
        assert response.status_code == 413
        data = response.json()
        assert "detail" in data
        assert "large" in data["detail"].lower() or "size" in data["detail"].lower()

    def test_truncated_response_when_max_rows_set(
        self, client: TestClient, sample_mt940_three_rows: str
    ) -> None:
        with patch("src.adapters.web.routes.MAX_ROWS", 2):
            response = client.post(
                "/api/convert",
                files={"file": ("x.txt", sample_mt940_three_rows.encode("utf-8"), "text/plain")},
                data={"encoding": "utf-8", "delimiter": ",", "decimal_sep": ","},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["rows"]) == 2
        assert data["row_count"] == 2
        assert data["truncated"] is True
        assert data["total_rows"] == 3

    def test_options_includes_limits(self, client: TestClient) -> None:
        response = client.get("/api/options")
        assert response.status_code == 200
        data = response.json()
        assert "limits" in data
        assert "max_upload_mb" in data["limits"]
        assert "max_rows" in data["limits"]
