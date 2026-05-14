"""
Domain constants: CSV schema and description tags.
"""

# CSV column headers (order used for output)
CSV_HEADERS = [
    "entry_date",
    "debit_credit",
    "amount",
    "currency",
    "reference",
    "description",
    "raw_61",
    "raw_86",
    "raw_all_together",
    "account",
    "opening_balance",
    "closing_balance",
    "value_date",
    "cleared_description",
    "signed_amount",
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
