"""Build `docs/llms-full.txt`: the agent summary followed by every package's README.

python3 scripts/llms_full.py            # write the file
python3 scripts/llms_full.py --check    # fail if the file is out of date
"""

from __future__ import annotations

import posixpath
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs" / "llms-full.txt"
REPO = "https://github.com/Adeniyikayodee/ng-postcode"
LINK = re.compile(r"\]\((?!https?:|#|mailto:)([^)#\s]+)(#[^)\s]*)?\)")
SOURCES = [
    "docs/llms.txt",
    "README.md",
    "docs/api-differences.md",
    "docs/address-record.md",
    "python/README.md",
    "CRATE.md",
    "js/packages/ng-postcode-js/README.md",
    "java/README.md",
    "mcp/README.md",
    "js/packages/ng-postcode-mcp/README.md",
    "agent/README.md",
    "native/polars/README.md",
    "native/pg/README.md",
    "sql/README.md",
]


def absolute(text: str, name: str) -> str:
    """Point repo-relative links at GitHub, since the file is read outside the repo."""

    def repl(m: re.Match[str]) -> str:
        path = posixpath.normpath(posixpath.join(posixpath.dirname(name), m[1]))
        kind = "tree" if (ROOT / path).is_dir() else "blob"
        return f"]({REPO}/{kind}/main/{path}{m[2] or ''})"

    return LINK.sub(repl, text)


def build() -> str:
    parts = [
        f"<!-- {name} -->\n\n{absolute((ROOT / name).read_text(encoding='utf-8').strip(), name)}"
        for name in SOURCES
    ]
    return "\n\n---\n\n".join(parts) + "\n"


def main() -> None:
    if "--check" not in sys.argv:
        TARGET.write_text(build(), encoding="utf-8")
    elif TARGET.read_text(encoding="utf-8") != build():
        sys.exit("docs/llms-full.txt is out of date: run python3 scripts/llms_full.py")


if __name__ == "__main__":
    main()
