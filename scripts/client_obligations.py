"""Fail when a client's tests do not name every obligation in `spec/client.json`.

    python3 scripts/client_obligations.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    spec = json.loads((ROOT / "spec" / "client.json").read_text(encoding="utf-8"))
    missing = [
        f"{client}: {name}"
        for client in spec["clients"]
        for name in spec["obligations"].keys() - proven(ROOT / client)
    ]
    if missing:
        sys.exit("client obligations without a test:\n  " + "\n  ".join(sorted(missing)))


def proven(tests: Path) -> set[str]:
    """The obligations a test file names in `spec/client.json: a, b` comments."""
    lines = re.findall(r"spec/client\.json: ([a-z_, ]+)", tests.read_text(encoding="utf-8"))
    return {name.strip() for line in lines for name in line.split(",")}


if __name__ == "__main__":
    main()
