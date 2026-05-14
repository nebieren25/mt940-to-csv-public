"""
Pytest fixtures: sample MT940 content and expected values.
"""

import pytest


@pytest.fixture
def sample_mt940_content() -> str:
    """README example: one transaction, ING format."""
    return """{1:F01INGBNL2ABXXX0000000000}
{2:I940INGBNL2AXXXN}
{4:
:20:P250210000000001
:25:NL00TEST0123456789EUR
:28C:00000
:60F:C241031EUR387,07
:61:2501310131D22,85NTRFNONREF//25031594984537
/TRCD/02002/
:86:/REMI/USTD//SAMPLE MERCHANT AMSTERDAM NLD 30-01-2025 20:22 ...
:62F:C250131EUR6,12
}
"""


@pytest.fixture
def minimal_mt940_with_one_tx() -> str:
    """Minimal valid MT940 with exactly one transaction."""
    return """{1:F01INGBNL2ABXXX0000000000}
{2:I940INGBNL2AXXXN}
{4:
:20:REF001
:25:NL00TEST0123456789EUR
:60F:C250101EUR100,00
:61:2501310131D22,85NTRFNONREF//25031594984537
:86:/REMI/USTD//Test payment
:62F:C250131EUR77,15
}
"""


@pytest.fixture
def expected_row_count_sample() -> int:
    """Number of transactions in sample_mt940_content."""
    return 1


@pytest.fixture
def sample_mt940_three_rows() -> str:
    """MT940 with exactly 3 transactions (for MAX_ROWS truncation test)."""
    return """{1:F01INGBNL2ABXXX0000000000}
{2:I940INGBNL2AXXXN}
{4:
:20:REF001
:25:NL00TEST0123456789EUR
:60F:C250101EUR100,00
:61:2501310131D22,85NTRFNONREF//1
:86:/REMI/Test one
:61:2502010201C10,00NTRFNONREF//2
:86:/REMI/Test two
:61:2503010301D5,50NTRFNONREF//3
:86:/REMI/Test three
:62F:C250131EUR82,35
}
"""


@pytest.fixture
def app():
    """FastAPI app for integration tests."""
    from src.web_app import create_app
    return create_app()
