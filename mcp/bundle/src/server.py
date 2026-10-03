"""Entry point for the MCPB bundle: runs the published server over stdio."""

import os

from ng_postcode_mcp.server import main

# A host fills unset options with an empty string; the server reads that as "not set".
for name in ("NG_POSTCODE_API_KEY", "NG_POSTCODE_MAX_LEVEL"):
    if not os.environ.get(name, "").strip():
        os.environ.pop(name, None)

main()
