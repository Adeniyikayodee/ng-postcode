"""Compare the live NIPOST API with what ng-postcode expects.

    cd python && uv run --group dev python ../scripts/live_check.py

Reads the key from NG_POSTCODE_API_KEY, or from the file ~/.nipost_key. Makes a
handful of free-tier calls (level 1 lookups, autocomplete, reverse, nearby) and
reports, for each, whether the library decodes the real response and which
fields differ from the documented ones. Pass --paid to add one level 2 lookup,
which consumes credits. The key is never printed.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

import httpx

from ng_postcode import Postcode
from ng_postcode.api import (
    BASE_URL,
    AdministrativeAddress,
    ApiError,
    Autocomplete,
    Coordinate,
    Lookup,
    NearbyUnit,
    NearestUnit,
    Request,
    Reverse,
    Suggestion,
    autocomplete,
    decode,
    lookup,
    nearby,
    reverse,
)

ADO_EKITI = Coordinate(lat=7.6211, lng=5.2214)
DOCUMENTED = ("EK01A03FK01", "LA11W06TC10", "FC03B06AG12")
UNASSIGNED = "ZZ99Z99ZZ99"

# Keys the library reads at each level of a response, beyond its dataclass fields.
EXTRA_KEYS = {Lookup: {"recent_house_address"}, Reverse: {"coordinate"}}
NESTED: dict[type, dict[str, type]] = {
    Lookup: {"administrative_address": AdministrativeAddress},
    Autocomplete: {"suggestions": Suggestion},
    Reverse: {"unit": NearestUnit},
}


def api_key() -> str | None:
    key = os.environ.get("NG_POSTCODE_API_KEY", "").strip()
    file = Path.home() / ".nipost_key"
    return key or (file.read_text().strip() if file.exists() else None)


def unmodelled(data: Any, model: type) -> list[str]:
    """Keys NIPOST sends that the library does not read, as dotted paths."""
    if isinstance(data, list):
        return sorted({k for item in data for k in unmodelled(item, model)})
    if not isinstance(data, dict) or not is_dataclass(model):
        return []
    known = {f.name for f in fields(model)} | EXTRA_KEYS.get(model, set())
    extra = [k for k in data if k not in known]
    nested = [
        f"{key}.{inner}"
        for key, child in NESTED.get(model, {}).items()
        for inner in unmodelled(data.get(key), child)
    ]
    return sorted(extra + nested)


def check(http: httpx.Client, label: str, request: Request[Any], model: type | None) -> bool:
    response = http.get(BASE_URL + request.path, params=request.params)
    limits = {k: v for k, v in response.headers.items() if k.lower().startswith("x-ratelimit")}
    print(f"\n{label}\n  GET {request.path} {dict(request.params)} -> HTTP {response.status_code} {limits}")
    try:
        body = response.json()
    except ValueError:
        print(f"  not JSON: {response.text[:200]!r}")
        return False
    decoded = decode(request, response.status_code, response.text)
    if isinstance(decoded, ApiError):
        print(f"  library: ApiError {decoded}")
        print(f"  raw: {json.dumps(body)[:300]}")
        return False
    data = body.get("data") if isinstance(body, dict) else None
    print(f"  raw data: {json.dumps(data, ensure_ascii=False)[:600]}")
    print(f"  library: {decoded!r}"[:700])
    extra = unmodelled(data, model) if model else []
    if extra:
        print(f"  fields NIPOST sends that the library ignores: {extra}")
    return True


def main() -> None:
    key = api_key()
    if key is None:
        sys.exit("No key: set NG_POSTCODE_API_KEY or save the key in ~/.nipost_key")
    kind = next((p for p in ("nipost_live_", "nipost_test_", "nipost_pk_") if key.startswith(p)), "unknown")
    print(f"Using a {kind.strip('_')} key against {BASE_URL}")
    with httpx.Client(headers={"X-API-Key": key}, timeout=20.0) as http:
        print(f"healthz -> HTTP {http.get(BASE_URL + '/healthz').status_code}")
        results = [
            check(http, f"lookup level 1, documented code {code}", lookup(Postcode(code), 1), Lookup)
            for code in DOCUMENTED
        ]
        results += [
            check(http, "lookup level 1, unassigned code", lookup(Postcode(UNASSIGNED), 1), Lookup),
            check(http, "autocomplete 'EK'", autocomplete("EK"), Autocomplete),
            check(http, "autocomplete 'EK 01 A'", autocomplete("EK 01 A"), Autocomplete),
            check(http, "reverse, central Ado Ekiti, 250 m", reverse(ADO_EKITI, 250), Reverse),
            check(http, "nearby, central Ado Ekiti", nearby(ADO_EKITI, 300), NearbyUnit),
        ]
        if "--paid" in sys.argv:
            results.append(
                check(http, "lookup level 2 (uses credits)", lookup(Postcode(DOCUMENTED[0]), 2), Lookup)
            )
    print(f"\n{sum(results)} of {len(results)} calls decoded by the library.")


if __name__ == "__main__":
    main()
