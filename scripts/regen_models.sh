#!/usr/bin/env bash
# Regenerate reportnet_api/models/generated.py from spec/api-docs.json.
#
# Never hand-edit generated.py — running this script is the only way its
# contents should change.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Swagger 2.0's `definitions` isn't read by the generator's OpenAPI parser
# (it only reads `components/schemas`), so lift them into a temp OpenAPI 3
# doc first.
tmp_spec="$(mktemp -t reportnet-openapi-XXXXXX.json)"
trap 'rm -f "$tmp_spec"' EXIT
uv run python3 scripts/_swagger_defs_to_openapi.py spec/api-docs.json "$tmp_spec"

uv run datamodel-codegen \
    --input "$tmp_spec" \
    --input-file-type openapi \
    --output reportnet_api/models/generated.py \
    --output-model-type pydantic_v2.BaseModel \
    --target-python-version 3.11 \
    --use-schema-description \
    --use-field-description \
    --field-constraints \
    --use-standard-collections \
    --use-union-operator \
    --collapse-root-models \
    --enum-field-as-literal one \
    --use-subclass-enum \
    --disable-timestamp \
    --custom-file-header "# Generated from spec/api-docs.json by scripts/regen_models.sh — do not edit by hand."

# Format with the project's ruff settings so a rerun without a spec change gives no diff.
uv run ruff format --quiet reportnet_api/models/generated.py
