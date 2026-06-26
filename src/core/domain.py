"""
Domain constants: CSV schema and description tags.
"""

DEFAULT_BANK_PROFILE = "auto"
DEFAULT_DESCRIPTION_STYLE = "sepa_overboeking_with_description"

BANK_PROFILES = ("auto", "ing", "abn", "rabo", "knab", "raw")
DESCRIPTION_STYLES = (
    "counterparty",
    "counterparty_with_description",
    "sepa_overboeking_with_description",
)

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
    "bank_transaction_label",
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
    "card_terminal_id",
    "card_sequence_number",
    "card_transaction_number",
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
