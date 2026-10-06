# The MCP server, built from this repository. Runs over stdio unless
# NG_POSTCODE_TRANSPORT=http, which also needs NG_POSTCODE_HOST=0.0.0.0.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim@sha256:531f855bda2c73cd6ef67d56b733b357cea384185b3022bd09f05e002cd144ca

WORKDIR /app
COPY python python
COPY agent agent
COPY mcp mcp
RUN uv sync --project mcp --locked --no-dev --no-cache \
    && useradd --system app

USER app
EXPOSE 8000
ENTRYPOINT ["/app/mcp/.venv/bin/ng-postcode-mcp"]
