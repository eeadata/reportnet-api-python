"""Search the client's methods and helpers by keyword.

`find("export")` lists every resource method, `easy` helper and handle member whose
name or first docstring line contains each word of the text, as a small table you can
print or iterate. It reads the live classes, so it never goes stale; the per-function
details (arguments, required rights, live-tested caveats) are in `docs/reference/`.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from types import FunctionType
from typing import Any

from . import easy, jobs
from .client import ReportnetClient
from .handles import Dataflow, Dataset

_RESOURCES = (
    "dataflow",
    "dataset_schema",
    "datasets",
    "dataset_snapshot",
    "eu_datasets",
    "release_receipts",
    "reference_dataset",
    "representative",
    "user",
    "validation",
)
_REFERENCE_PAGES = {"jobs": "jobs", "easy": "easy"}


@dataclass(frozen=True)
class Match:
    """One searchable function: how to call it and what it does."""

    call: str  # e.g. "client.datasets.import_file_data" or "easy.read_table"
    summary: str  # first docstring line, may be empty
    page: str  # docs/reference page name

    @property
    def doc_link(self) -> str:
        return f"docs/reference/{self.page}.md#{self.call.rsplit('.', 1)[-1].lower()}"


class Matches(list[Match]):
    """A list of `Match` that prints as an aligned table."""

    def __str__(self) -> str:
        if not self:
            return "No match. Try a shorter or different word, e.g. find('export')."
        width = max(len(m.call) for m in self)
        return "\n".join(f"{m.call.ljust(width)}  {m.summary}".rstrip() for m in self)

    __repr__ = __str__


def _first_line(obj: Any, name: str = "") -> str:
    """First docstring line; generated methods start with a roles table, so for those
    (and for no docstring) the method name in plain words is the summary."""
    line = (inspect.getdoc(obj) or "").split("\n", 1)[0].strip()
    if not line or line.lower().startswith("allowed roles"):
        return name.replace("_", " ")
    return line


def _catalog() -> list[Match]:
    out: list[Match] = []
    client = ReportnetClient("https://example.invalid", "x")
    try:
        for attr in _RESOURCES:
            res = getattr(client, attr)
            for name, fn in inspect.getmembers(type(res), inspect.isfunction):
                if not name.startswith("_"):
                    out.append(Match(f"client.{attr}.{name}", _first_line(fn, name), attr))
    finally:
        client.close()
    for page, module in (("easy", easy), ("jobs", jobs)):
        for name, fn in inspect.getmembers(module, inspect.isfunction):
            if not name.startswith("_") and fn.__module__ == module.__name__:
                out.append(Match(f"{page}.{name}", _first_line(fn, name), _REFERENCE_PAGES[page]))
    for cls, var in ((Dataflow, "flow"), (Dataset, "ds")):
        for name, member in vars(cls).items():
            if name.startswith("_") or not isinstance(member, property | FunctionType):
                continue
            out.append(Match(f"{var}.{name}", _first_line(member, name), "handles"))
    return sorted(out, key=lambda m: m.call)


def find(text: str) -> Matches:
    """Search method names and one-line summaries for every word in `text`.

    Case-insensitive; `_` and spaces both separate words, so `find("import file")`
    matches `import_file_data`. Returns a printable list of `Match`.
    """
    words = text.lower().replace("_", " ").split()
    hits = Matches()
    if not words:
        return hits
    for m in _catalog():
        hay = f"{m.call} {m.summary}".lower().replace("_", " ")
        if all(w in hay for w in words):
            hits.append(m)
    return hits
