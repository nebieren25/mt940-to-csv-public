# Security Policy

## Supported Versions

Security fixes are handled on the `main` branch.

## Reporting a Vulnerability

If you find a security issue, please open a private security advisory on GitHub or contact the maintainer directly. Avoid posting sensitive details in a public issue.

## Sensitive Financial Data

This repository must not contain real MT940 files, exported bank CSV files, IBANs, account numbers, customer names, transaction references, or screenshots of bank data.

If sensitive data is accidentally committed:

1. Stop pushing new commits.
2. Rotate or protect any affected credentials or accounts if needed.
3. Rewrite git history to remove the data.
4. Force-push the cleaned history.
5. Treat already-published data as exposed.

## Runtime Behavior

The web application processes uploaded files in memory for the request. It does not intentionally store uploaded statements on disk.
