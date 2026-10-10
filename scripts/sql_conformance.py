"""Run the cases in `spec/vectors.json` against the SQL in `sql/`.

    python3 scripts/sql_conformance.py postgres   # through psql, using PG* from the environment
    python3 scripts/sql_conformance.py duckdb     # needs the duckdb package

SQL has no error values, so a rejected input is NULL. Each case becomes one expression that
is true when the SQL agrees with the spec. For PostgreSQL, the examples in `sql/README.md` are
run as well.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(value: str | None) -> str:
    return "NULL" if value is None else "'" + value.replace("'", "''") + "'"


def checks(engine: str) -> list[tuple[str, str]]:
    """A name and an expression per case, comparing with a NULL-safe test."""
    spec = json.loads((ROOT / "spec" / "vectors.json").read_text(encoding="utf-8"))

    def same(expression: str, expected: str | None) -> str:
        return f"({expression}) IS NOT DISTINCT FROM {text(expected)}"

    found: list[tuple[str, str]] = []
    for case in spec["parse"]["valid"]:
        parsed = f"ng_postcode_parse({text(case['input'])})"
        found.append((f"parse {case['input']!r}", same(parsed, case["compact"])))
        found.append((f"format {case['input']!r}", same(f"ng_postcode_format({parsed})", case["canonical"])))
    for case in spec["parse"]["invalid"]:
        found.append((f"reject {case['input'][:30]!r}", same(f"ng_postcode_parse({text(case['input'])})", None)))
    for case in spec["prefix"]:
        cut = f"ng_postcode_truncate(ng_postcode_parse({text(case['input'])}), {text(case['through'])})"
        found.append((f"truncate {case['through']}", same(f"ng_postcode_format({cut})", case["prefix"])))
    for case in spec["parse_prefix"]["valid"]:
        parsed = f"ng_postcode_prefix_parse({text(case['input'])})"
        found.append((f"prefix {case['input']!r}", same(parsed, case["compact"])))
        found.append((f"prefix format {case['input']!r}", same(f"ng_postcode_format({parsed})", case["canonical"])))
    for case in spec["parse_prefix"]["invalid"]:
        parsed = f"ng_postcode_prefix_parse({text(case['input'])})"
        found.append((f"prefix reject {case['input']!r}", same(parsed, None)))
    for case in spec["prefix_contains"]:
        code, prefix = (f"ng_postcode_{kind}({text(case[key])})" for kind, key in (("parse", "code"), ("prefix_parse", "prefix")))
        inside = "true" if case["contains"] else "false"
        found.append((f"{case['prefix']} contains", f"ng_postcode_within({code}, {prefix}) IS NOT DISTINCT FROM {inside}"))
    for case in spec["prefix_parent"]:
        parent = f"ng_postcode_format(ng_postcode_parent(ng_postcode_prefix_parse({text(case['prefix'])})))"
        found.append((f"parent of {case['prefix']}", same(parent, case["parent"])))
    # Inputs that a locale-aware upper() or a Unicode-aware class would let through.
    for sneaky in ("ek01a03fk0ı", "EK01A03FK01", "EK０１A03FK01", "EK01A03FK01\n"):
        found.append((f"reject {sneaky!r}", same(f"ng_postcode_parse({text(sneaky)})", None)))
    found.append(("unknown segment", same("ng_postcode_truncate(ng_postcode_parse('EK01A03FK01'), 'zone')", None)))
    found.append(("version", same("ng_postcode_version()", version(engine))))
    return found


def version(engine: str) -> str:
    """The version a SQL file states in its header, which its version function must repeat."""
    header = (ROOT / "sql" / f"{engine}.sql").read_text(encoding="utf-8")
    return re.search(r"^-- Version (\S+)$", header, re.MULTILINE)[1]


def readme() -> str:
    """The SQL in `sql/README.md`, in order: its examples must run as written."""
    text = (ROOT / "sql" / "README.md").read_text(encoding="utf-8")
    return "\n".join(re.findall(r"```sql\n(.*?)```", text, re.DOTALL))


def postgres(expressions: list[str]) -> list[bool]:
    script = (ROOT / "sql" / "postgres.sql").read_text(encoding="utf-8")
    # In a transaction that is rolled back, so the database is left as it was found.
    queries = "".join(f"SELECT {expression};\n" for expression in expressions)
    run = subprocess.run(
        ["psql", "-X", "-q", "-At", "-v", "ON_ERROR_STOP=1"],
        input=f"BEGIN;\n{script}\n{queries}ROLLBACK;\n",
        capture_output=True,
        text=True,
        check=False,
    )
    if run.returncode != 0:
        sys.exit(run.stderr)
    examples = subprocess.run(
        ["psql", "-X", "-q", "-At", "-v", "ON_ERROR_STOP=1", "-o", os.devnull],
        input=f"BEGIN;\n{script}\n{readme()}\nROLLBACK;\n",
        capture_output=True,
        text=True,
        check=False,
    )
    if examples.returncode != 0:
        sys.exit("sql/README.md does not run as written:\n" + examples.stderr)
    return [line == "t" for line in run.stdout.splitlines()]


def duckdb(expressions: list[str]) -> list[bool]:
    import duckdb as engine

    with engine.connect() as db:
        db.execute((ROOT / "sql" / "duckdb.sql").read_text(encoding="utf-8"))
        return [bool(db.execute(f"SELECT {expression}").fetchone()[0]) for expression in expressions]


def main() -> None:
    engine = {"postgres": postgres, "duckdb": duckdb}[sys.argv[1]]
    cases = checks(sys.argv[1])
    answers = engine([expression for _, expression in cases])
    if len(answers) != len(cases):
        sys.exit(f"{sys.argv[1]}: {len(answers)} answers for {len(cases)} cases")
    failed = [name for (name, _), agreed in zip(cases, answers, strict=True) if not agreed]
    if failed:
        sys.exit(f"{sys.argv[1]} disagrees with spec/vectors.json:\n  " + "\n  ".join(failed))
    print(f"{sys.argv[1]}: {len(cases)} cases agree")


if __name__ == "__main__":
    main()
