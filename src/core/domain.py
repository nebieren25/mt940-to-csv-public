"""
Domain constants: CSV schema and description tags.
"""

# CSV column headers (order used for output). Keep the first three columns
# optimized for review/accounting; keep the remaining columns detailed enough
# to avoid going back to the MT940 source for normal checks.
CSV_HEADERS = [
    "date",
    "description",
    "amount",
    "value_date",
    "entry_date",
    "currency",
    "debit_credit",
    "transaction_type",
    "customer_ref",
    "bank_ref",
    "counterparty_name",
    "counterparty_account",
    "counterparty_iban",
    "counterparty_bic",
    "payment_reference",
    "mandate_reference",
    "creditor_id",
    "purpose_code",
    "return_reason",
    "payment_description",
    "ultimate_creditor",
    "card_terminal",
    "description_format",
    "supplementary",
    "account",
    "statement_number",
    "transaction_reference",
    "opening_balance",
    "closing_balance",
    "original_amount",
    "signed_amount",
    "reference",
    "cleared_description",
    "raw_61",
    "raw_86",
    "raw_all_together",
]

# Tags to strip from description for cleared_description (MT940 subfield markers)
DESCRIPTION_TAGS = (
    "/REMI/",
    "/CNTP/",
    "/EREF/",
    "/USTD/",
    "/TRCD/",
    "/MARF/",
    "/CSID/",
    "/SUM/",
    "/AB/",
    "/ORDPTY/",
    "/BENEF/",
)
