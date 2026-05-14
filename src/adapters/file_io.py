"""
File I/O adapter: read MT940 from path, write CSV to path.
Used by CLI; keeps core free of I/O.
"""

from pathlib import Path

from src.core.convert import content_to_rows, rows_to_csv_string


def read_file(path: Path, encoding: str = "utf-8") -> str:
    """Read file content as string. Raises on error."""
    return path.read_text(encoding=encoding)


def write_csv(
    path: Path,
    csv_string: str,
    encoding: str = "utf-8",
) -> None:
    """Write CSV string to file."""
    path.write_text(csv_string, encoding=encoding)


def convert_one_file(
    input_path: Path,
    output_path: Path,
    encoding: str = "utf-8",
    delimiter: str = ",",
    decimal_sep: str = ",",
) -> tuple[bool, int]:
    """
    Convert a single MT940 file to CSV (adapter: reads file, calls core, writes file).
    Returns (success, transaction_count).
    """
    try:
        content = read_file(input_path, encoding)
    except Exception:
        return False, 0

    rows, _ = content_to_rows(content, encoding)
    if not rows:
        return False, 0

    csv_string = rows_to_csv_string(rows, delimiter=delimiter, decimal_sep=decimal_sep)
    try:
        write_csv(output_path, csv_string, encoding)
    except Exception:
        return False, 0

    return True, len(rows)
