"""Entry point for hosts that run Python bundles: starts the published server with uvx."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

PACKAGE = "ng-postcode-mcp==0.6.0"
USUAL_PLACES = (Path.home() / ".local/bin", Path("/opt/homebrew/bin"), Path("/usr/local/bin"))

# A host fills unset options with an empty string; the server reads that as "not set".
for name in ("NG_POSTCODE_API_KEY", "NG_POSTCODE_MAX_LEVEL"):
    if not os.environ.get(name, "").strip():
        os.environ.pop(name, None)

uvx = shutil.which("uvx") or next(
    (str(place / "uvx") for place in USUAL_PLACES if (place / "uvx").exists()), None
)
if uvx is None:
    sys.exit("ng-postcode needs uv to run: https://docs.astral.sh/uv/")
sys.exit(subprocess.call([uvx, PACKAGE]))
