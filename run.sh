#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec uv run --frozen python tools/web_port.py "$@"
