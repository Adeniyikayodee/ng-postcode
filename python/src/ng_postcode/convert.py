"""Convert a CSV column of postcodes to the compact form, and say what is wrong with the rest.

    python -m ng_postcode orders.csv --column postcode --out checked.csv

Offline unless `--confirm` is given, which asks NIPOST whether each well-formed code is
assigned, with the key in `NG_POSTCODE_API_KEY`. Nothing is corrected silently: a code
that only parses after look-alike characters are swapped is reported as a suggestion.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import os
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import Literal, TextIO

from ._postcode import WHITE_SPACE, Corrected, Postcode, parse, parse_lenient

Status = Literal["valid", "suggested", "invalid", "empty"]
Confirm = Callable[[Postcode], bool | None]
"""Whether NIPOST reports a code as assigned, or None when it could not be asked."""


@dataclass(frozen=True, slots=True)
class Converted:
    compact: str
    """The form to store, or empty when the value is not a well-formed code."""
    status: Status
    suggestion: str
    """A code the value may have meant, for a person to confirm. Never applied."""
    error: str


def convert(text: str) -> Converted:
    """What one cell holds. Pure: no I/O."""
    if not text.strip(WHITE_SPACE):
        return Converted("", "empty", "", "")
    code = parse(text)
    if isinstance(code, Postcode):
        return Converted(code.compact, "valid", "", "")
    fixed = parse_lenient(text)
    if isinstance(fixed, Corrected):
        return Converted("", "suggested", str(fixed.postcode), str(code))
    return Converted("", "invalid", "", str(code))


def rows(
    source: Iterable[dict[str, str]], column: str, confirm: Confirm | None
) -> Iterator[dict[str, str]]:
    """Each row with the new columns added. One row is held at a time."""
    asked: dict[str, bool | None] = {}
    for row in source:
        found = convert(row.get(column) or "")
        added = {
            f"{column}_compact": found.compact,
            f"{column}_status": found.status,
            f"{column}_suggestion": found.suggestion,
            f"{column}_error": found.error,
        }
        if confirm is not None:
            if found.compact and found.compact not in asked:
                asked[found.compact] = confirm(Postcode(found.compact))
            answer = asked.get(found.compact)
            added[f"{column}_assigned"] = "" if answer is None else str(answer).lower()
        yield row | added


def read(source: TextIO, column: str) -> csv.DictReader[str]:
    """The rows of `source`, once its header is known to hold `column`."""
    reader = csv.DictReader(source)
    if column not in (reader.fieldnames or []):
        sys.exit(f"ng-postcode: no column named {column!r}; found {reader.fieldnames}")
    names = list(reader.fieldnames or [])
    repeated = [name for name in names if names.count(name) > 1]
    if repeated:
        sys.exit(f"ng-postcode: the header names {repeated[0]!r} more than once")
    taken = [name for name in names if name in new_columns(column, True)]
    if taken:
        sys.exit(f"ng-postcode: the file already has a column named {taken[0]!r}")
    return reader


def new_columns(column: str, confirming: bool) -> list[str]:
    """The columns a run adds, which the file must not already hold."""
    names = ["compact", "status", "suggestion", "error", *(["assigned"] if confirming else [])]
    return [f"{column}_{name}" for name in names]


def write(
    reader: csv.DictReader[str], target: TextIO, column: str, confirm: Confirm | None
) -> Counter[str]:
    """Convert the rows of `reader` to `target` and count them by status."""
    names = [*(reader.fieldnames or []), *new_columns(column, confirm is not None)]
    writer = csv.DictWriter(target, fieldnames=names, lineterminator="\n")
    # Written before any row, so a file with none keeps its header.
    writer.writeheader()
    counts: Counter[str] = Counter()
    for row in rows(reader, column, confirm):
        # The reader files cells past the header under None, and no column can take them.
        if None in row:
            sys.exit(f"ng-postcode: line {reader.line_num} has more cells than the header")
        writer.writerow(row)
        counts[row[f"{column}_status"]] += 1
    return counts


def nipost(key: str) -> Confirm:
    """Level 1 lookups with the caller's own key. After the first failure NIPOST is not
    asked again, and the remaining rows are left unconfirmed."""
    try:
        from .api import Lookup, lookup
        from .client import Client
    except ImportError:
        sys.exit('ng-postcode: --confirm needs the client: pip install "ng-postcode[client]"')
    client = Client(key)
    failed: list[str] = []

    def confirm(code: Postcode) -> bool | None:
        if failed:
            return None
        answer = client.send(lookup(code))
        if isinstance(answer, Lookup):
            return answer.valid
        failed.append(str(answer))
        print(f"ng-postcode: stopped confirming: {answer}", file=sys.stderr)
        return None

    return confirm


def main(argv: list[str] | None = None) -> None:
    cli = argparse.ArgumentParser(prog="ng-postcode", description=__doc__.split("\n\n")[0])
    cli.add_argument("file", help="CSV file to read, or - for standard input.")
    cli.add_argument("--column", required=True, help="Name of the column that holds postcodes.")
    cli.add_argument("--out", help="CSV file to write. Defaults to standard output.")
    cli.add_argument("--confirm", action="store_true", help="Ask NIPOST whether each code exists.")
    args = cli.parse_args(argv)
    key = os.environ.get("NG_POSTCODE_API_KEY", "").strip()
    if args.confirm and not key:
        cli.error("--confirm needs a NIPOST API key in NG_POSTCODE_API_KEY")
    confirm = nipost(key) if args.confirm else None
    with contextlib.ExitStack() as files:
        # utf-8-sig drops the byte order mark that spreadsheet exports begin with.
        source = (
            sys.stdin
            if args.file == "-"
            else files.enter_context(open(args.file, newline="", encoding="utf-8-sig"))
        )
        reader = read(source, args.column)
        # Opening the output empties it, so it waits until the input is known to be usable.
        same = args.out and args.file != "-" and os.path.exists(args.out)
        if same and os.path.samefile(args.file, args.out):
            sys.exit("ng-postcode: --out is the input file, which writing would empty")
        target = (
            files.enter_context(open(args.out, "w", newline="", encoding="utf-8"))
            if args.out
            else sys.stdout
        )
        counts = write(reader, target, args.column, confirm)
    parts = [
        f"{counts[status]:,} {status}" for status in ("valid", "suggested", "invalid", "empty")
    ]
    print(f"ng-postcode: {sum(counts.values()):,} rows: {', '.join(parts)}", file=sys.stderr)
