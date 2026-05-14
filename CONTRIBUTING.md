# Contributing

Thanks for considering a contribution. This project is intentionally small, so contributions should stay focused and easy to review.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Before Opening a Pull Request

- Keep changes scoped to one clear problem.
- Add or update tests when behavior changes.
- Run the full test suite:

```bash
PYTHONPATH=. pytest tests -q
```

## Data Safety

Do not commit real bank statements, exported CSV files, account numbers, IBANs, customer names, transaction descriptions, or screenshots containing financial data. Use small synthetic examples only.

## Code Style

- Keep core logic free from file and web I/O.
- Prefer small pure functions for parsing and conversion behavior.
- Keep CLI and web behavior in adapter layers.
- Avoid broad refactors unless they directly support the change.
