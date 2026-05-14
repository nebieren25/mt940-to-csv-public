#!/usr/bin/env python3
"""
CLI for MT940 → CSV conversion. Uses core and file_io adapter.
"""

import argparse
import sys
from pathlib import Path

from src.adapters.file_io import convert_one_file


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert MT940 bank statement file(s) to CSV.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Path to MT940 file or folder (with --folder)",
    )
    parser.add_argument(
        "-i", "--input-file",
        dest="input_file",
        help="Path to MT940 file or folder (alternative to positional input)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output CSV path, or output folder when using --folder",
    )
    parser.add_argument(
        "-d", "--folder",
        action="store_true",
        dest="folder_mode",
        help="Convert all MT940 files in the given folder (each file → same name with .csv)",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="Input file encoding (default: utf-8)",
    )
    parser.add_argument(
        "--delimiter",
        default=",",
        help="CSV delimiter (default: ,)",
    )
    parser.add_argument(
        "--decimal",
        default=",",
        choices=(".", ","),
        help="Decimal separator in amount column (default: , for Excel)",
    )
    args = parser.parse_args()

    input_path = args.input or args.input_file
    if not input_path:
        parser.error("Either positional input or -i/--input-file is required")
    input_path = Path(input_path)
    if not input_path.exists():
        print(f"Error: path not found: {input_path}", file=sys.stderr)
        return 1

    if args.folder_mode or input_path.is_dir():
        if not input_path.is_dir():
            print(f"Error: not a folder: {input_path}", file=sys.stderr)
            return 1
        output_dir = Path(args.output) if args.output else input_path
        if args.output and not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)
        ok, total = 0, 0
        files = sorted(f for f in input_path.iterdir() if f.is_file())
        if not files:
            print(f"No files in folder: {input_path}", file=sys.stderr)
            return 1
        for f in files:
            out = output_dir / f.with_suffix(".csv").name
            success, count = convert_one_file(
                f, out, args.encoding, args.delimiter, args.decimal
            )
            if success:
                ok += 1
                total += count
                print(f"  {f.name} → {out.name} ({count} transactions)")
            else:
                print(f"  Error or no transactions: {f.name}", file=sys.stderr)
        print(f"Done: {ok} file(s) converted, {total} transaction(s) total.")
        return 0 if ok else 1

    output_path = Path(args.output) if args.output else input_path.with_suffix(".csv")
    success, count = convert_one_file(
        input_path, output_path, args.encoding, args.delimiter, args.decimal
    )
    if not success:
        print(f"Error: could not convert {input_path}", file=sys.stderr)
        return 1
    print(f"Wrote {count} transaction(s) to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
