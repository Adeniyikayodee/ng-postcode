"""Build `docs/llms-full.txt`: the agent summary followed by every package's README.

python3 scripts/llms_full.py            # write the file
python3 scripts/llms_full.py --check    # fail if the file is out of date
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs" / "llms-full.txt"
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
]


def build() -> str:
    parts = [
        f"<!-- {name} -->\n\n{(ROOT / name).read_text(encoding='utf-8').strip()}"
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
