"""Lift Swagger 2.0 `definitions` into a synthetic OpenAPI 3 document.

datamodel-code-generator's OpenAPI parser only reads `components/schemas`,
not Swagger 2.0's `definitions`. This produces a minimal OpenAPI 3 doc with
the definitions moved (and their $refs rewritten) so the generator's
`schemas` scope picks them up. Used by regen_models.sh; not part of the
public package.
"""

import json
import sys
from pathlib import Path


def _rewrite_refs(obj: object) -> object:
    if isinstance(obj, dict):
        return {
            k: (
                v.replace("#/definitions/", "#/components/schemas/")
                if k == "$ref"
                else _rewrite_refs(v)
            )
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_rewrite_refs(item) for item in obj]
    return obj


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    with Path(src).open() as f:
        spec = json.load(f)

    schemas = _rewrite_refs(spec.get("definitions", {}))
    doc = {
        "openapi": "3.0.0",
        "info": spec.get("info", {"title": "generated", "version": "1.0"}),
        "paths": {},
        "components": {"schemas": schemas},
    }
    with Path(dst).open("w") as f:
        json.dump(doc, f)


if __name__ == "__main__":
    main()
