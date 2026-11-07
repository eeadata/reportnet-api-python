#!/usr/bin/env bash
# Regenerate reportnet_api/resources/*.py from spec/api-docs.json.
#
# Never hand-edit these files — running this script is the only way their
# contents should change. Generated files are never hand-edited.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

uv run python3 scripts/generate_resources.py
