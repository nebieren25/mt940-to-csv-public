# Changelog

All notable changes to this project will be documented here.

## Unreleased

- Add dedicated Knab MT940 parsing and Auto detection for counterparty fields, wrapped descriptions, and signed statement page balances.
- Reconvert the retained upload when the bank profile changes; ignore outdated conversion/export responses and clear pending work on Reset.
- Add synthetic Knab parser, conversion, API, and file adapter regression tests.
- Public repository cleanup.
- English documentation.
- Synthetic test statement examples.

## 0.1.0

- Initial public release.
- MT940 to CSV conversion through core library, CLI, and FastAPI.
- Static web UI for upload, preview, summary, and CSV download.
- Unit and integration test coverage for core and web behavior.
