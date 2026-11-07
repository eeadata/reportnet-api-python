#!/usr/bin/env bash
# Regenerate docs/reference/*.md from the code, spec/api-docs.json and
# scripts/docs_caveats.py.
#
# Never hand-edit the generated pages — running this script is the only way
# their contents should change. Generated files are never hand-edited.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

uv run python3 scripts/generate_docs.py
