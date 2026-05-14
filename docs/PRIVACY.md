# Privacy

MT940 files and exported CSV files can contain sensitive financial data. Treat them as private by default.

## What the App Does

- Reads uploaded files during the request.
- Converts MT940 content to rows and CSV output.
- Builds preview and summary data from the parsed rows.
- Returns the result to the browser or API client.

## What the App Does Not Intentionally Do

- It does not save uploaded statements to disk.
- It does not create a database record.
- It does not send statement data to a third-party service.

## Local Files

Do not commit local input or output files. The repository ignores common data paths and file types, but you should still review changes before committing:

```bash
git status --short
git diff --cached
```

## Public Repository Rule

Only synthetic examples belong in this repository. Do not publish real bank statements, IBANs, customer names, transaction descriptions, account balances, or exported financial CSV files.
