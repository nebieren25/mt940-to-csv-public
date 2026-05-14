# MT940 → CSV

MT940 (SWIFT) banka ekstre dosyalarını CSV’ye dönüştüren uygulama: **core kütüphane**, **CLI** ve **web arayüzü**.  
Mimari: Hexagonal (core’da I/O yok; CLI ve web adaptör).

- **Eski proje** (değiştirilmez): `old-project/`, ayrıntı için `old-README.md`.
- **Yeni kod**: `src/` (core + adaptörler + CLI + web) ve `web-ui/` (HTML + JS).

---

## Kurulum

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # pytest, pytest-cov
```

---

## Testler

Proje kökünden:

```bash
PYTHONPATH=. pytest tests/unit -v -m unit
PYTHONPATH=. pytest tests/unit --cov=src/core --cov-report=term-missing
PYTHONPATH=. pytest tests -v   # tüm testler (unit + integration)
```

---

## CLI

Eski script ile aynı parametreler: `input`, `-o`, `-d`/`--folder`, `--encoding`, `--delimiter`, `--decimal`.

```bash
PYTHONPATH=. python -m src.cli.main path/to/file.txt -o out.csv
PYTHONPATH=. python -m src.cli.main path/to/folder -d -o output_dir
```

---

## Web uygulaması

```bash
PYTHONPATH=. uvicorn src.web_app:app --reload --host 127.0.0.1 --port 8000
```

- **Ana sayfa:** http://127.0.0.1:8000 → `/ui/web-ui-1-v3.html` adresine yönlendirir (yeni UI v3).
- **Yeni UI v3:** http://127.0.0.1:8000/ui/web-ui-1-v3.html — upload, convert, financial summary (drill-down), preview, download.
- **Arayüz 1:** http://127.0.0.1:8000/ui/web-ui-1.html — üstte dosya + ayar paneli, altta önizleme tablosu.
- **Arayüz 2:** http://127.0.0.1:8000/ui/web-ui-2.html — solda sidebar (dosya + ayarlar), sağda önizleme.
- **API dokümanı:** http://127.0.0.1:8000/docs

Akış: MT940 dosyası seç → dönüştür → tabloda önizleme → Encoding/Delimiter/Decimal değiştirip “Download CSV” ile indir (yeniden yükleme gerekmez).

---

## API özeti

| Endpoint | Açıklama |
|---------|----------|
| GET `/api/options` | İzin verilen encoding, delimiter, decimal_sep ve limitler (max_upload_mb, max_rows). |
| POST `/api/convert` | Multipart: `file` + form alanları `encoding`, `delimiter`, `decimal_sep`. JSON: `rows`, `csv`, `account`, `row_count`; isteğe `truncated`, `total_rows`. `?format=csv` ile doğrudan CSV dosyası. |
| POST `/api/export` | JSON body: `rows`, `delimiter`, `decimal_sep`. Yeniden CSV üretir; `?format=csv` ile dosya cevabı. |

Geçersiz parametreler → **422**. Hatalar → `{"detail": "..."}`.

---

## Ortam değişkenleri

| Değişken | Varsayılan | Açıklama |
|----------|------------|----------|
| `LOG_LEVEL` | INFO | Log seviyesi. |
| `LOG_FILE` | (yok) | Dosya yolu; verilirse log dosyaya yazılır. |
| `MAX_FILE_SIZE_MB` | 0 | > 0 ise bu boyutu aşan yüklemelerde uyarı loglanır. |
| `MAX_UPLOAD_MB` | 0 | > 0 ise bu boyutu aşan yüklemeler **413** ile reddedilir. |
| `MAX_ROWS` | 0 | > 0 ise JSON cevabı ilk N satırla sınırlanır; `truncated`, `total_rows` döner. |

---

## Proje yapısı

```
mt-copy/
├── old-project/          # Eski proje (dokunulmaz)
├── old-README.md
├── src/
│   ├── core/             # Domain: parsing, convert (I/O yok)
│   │   ├── domain.py     # CSV_HEADERS, DESCRIPTION_TAGS
│   │   ├── parsing.py    # parse_mt940_custom, yardımcılar
│   │   ├── library_adapter.py   # mt-940 wrapper (content → rows)
│   │   └── convert.py    # content_to_rows, rows_to_csv_string
│   ├── adapters/
│   │   ├── file_io.py    # Dosya okuma/yazma (CLI)
│   │   └── web/          # FastAPI: routes, schemas, logging_config
│   ├── cli/main.py       # CLI giriş noktası
│   └── web_app.py        # FastAPI app, /ui mount, / → redirect
├── web-ui/               # Arayüz (StaticFiles ile /ui’de sunulur)
│   ├── web-ui-1.html
│   ├── web-ui-2.html
│   └── mt940-api.js      # API bağlantısı (upload, preview, download)
├── tests/
│   ├── unit/             # Core unit testleri
│   └── integration/     # Web API testleri
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml
```

---

## Tamamlanan aşamalar (milestone)

- **M0–M1:** Core çıkarımı, pytest, unit testler.
- **M2:** Minimal web app (upload, convert, JSON/CSV).
- **M3:** CSV önizleme; ayar değiştirip yeniden export (POST `/api/export`).
- **M4:** Ayar paneli + validasyon (Pydantic, 422).
- **M5:** Hata yönetimi + logging (LOG_LEVEL, LOG_FILE, 500 handler).
- **M6:** Limitler (MAX_UPLOAD_MB, MAX_ROWS; 413, truncation).
- **Web UI:** `web-ui/` HTML’leri ana arayüz; `/` → `/ui/web-ui-1.html`.

**Sonraki:** M7 — Docker hazırlık (ENV tabanlı config, stateless).
