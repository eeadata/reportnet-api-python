import json
from pathlib import Path
from typing import Any

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
NOTEBOOKS = sorted(EXAMPLES.glob("*.ipynb"))


def _code_cells(path: Path) -> tuple[dict[str, Any], list[str]]:
    nb = json.loads(path.read_text(encoding="utf-8"))
    return nb, ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_notebooks_are_clean(path: Path) -> None:
    nb, _ = _code_cells(path)
    assert nb["nbformat"] == 4
    for cell in nb["cells"]:
        assert cell.get("id"), "every cell needs an id (nbformat 4.5)"
        if cell["cell_type"] == "code":
            assert cell["outputs"] == [] and cell["execution_count"] is None
    text = path.read_text(encoding="utf-8")
    assert "eeadata/reportnet-api-python" in text  # the install and badge links


def test_demo_notebook_runs_offline_from_start_to_finish() -> None:
    _, cells = _code_cells(EXAMPLES / "try_it_demo.ipynb")
    namespace: dict[str, Any] = {}
    for source in cells:
        code = "\n".join(line for line in source.splitlines() if not line.startswith("%pip"))
        exec(compile(code, "try_it_demo", "exec"), namespace)  # noqa: S102
    assert namespace["both"].groupby("country").size().to_dict() == {"AT": 3, "BE": 2}
    assert str(namespace["austria"]["Id"].dtype) == "Int64"
