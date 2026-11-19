"""Generate the markdown reference under docs/reference/.

Introspects the sync resource classes on `ReportnetClient`, `reportnet_api.easy`
and `reportnet_api.jobs` (signatures and docstrings), enriches generated
methods from spec/api-docs.json (HTTP verb + path, parameter descriptions) and
adds the hand-kept live-tested notes from `scripts/docs_caveats.py`.

Output is deterministic (no timestamps), so rerunning without a change produces
no diff. Run via scripts/regen_docs.sh; never hand-edit the output.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "docs" / "reference"
SCRIPTS_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(REPO_ROOT))


def _load_script(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolve annotations via sys.modules
    spec.loader.exec_module(module)
    return module


gen = _load_script("generate_resources")
CAVEATS: dict[str, list[tuple[str, str]]] = _load_script("docs_caveats").CAVEATS

from reportnet_api import easy, handles, jobs  # noqa: E402
from reportnet_api.client import ReportnetClient  # noqa: E402

# (page name, attribute on ReportnetClient, title)
RESOURCE_PAGES = [
    ("dataflow", "Dataflow (hand-written)"),
    ("dataset_schema", "Dataset Schema"),
    ("datasets", "Datasets"),
    ("dataset_snapshot", "Dataset Snapshot"),
    ("eu_datasets", "EU Datasets"),
    ("release_receipts", "Release receipts"),
    ("reference_dataset", "Reference dataset (hand-written)"),
    ("representative", "Representative (hand-written)"),
    ("user", "User (hand-written)"),
    ("validation", "Validation (hand-written)"),
]
HANDLES_TITLE = "Handles (`reportnet_api.handles`)"
MODULE_PAGES = [
    ("easy", easy, "Notebook helpers (`reportnet_api.easy`)"),
    ("jobs", jobs, "Job polling (`reportnet_api.jobs`)"),
]

# Handle classes (page name "handles"): (class, variable used in the Call line)
HANDLE_CLASSES = [(handles.Dataflow, "flow"), (handles.Dataset, "ds")]

_VERB_PATH_RE = re.compile(r"^(GET|POST|PUT|DELETE|PATCH)\s+(/(?:[^\s{]|\{[^}]*\})*)")
_ROLE_VALUE_RE = re.compile(r"[A-Z][A-Z _,]*")
NO_ROLES = "Not stated in the API spec."


@dataclass
class SpecInfo:
    verb: str
    path: str
    summary: str
    param_docs: dict[str, str]


@dataclass
class ArgRow:
    name: str
    type: str
    required: bool
    default: str
    description: str


@dataclass
class MethodDoc:
    name: str
    verb_path: str | None
    has_spec: bool
    summary: str
    details: list[str]
    roles: list[tuple[str, str]] | None
    args: list[ArgRow]
    returns: str
    caveats: list[tuple[str, str]] = field(default_factory=list)
    call: str | None = None  # overrides the generated "Call" text (handle methods)


def load_spec_index() -> dict[tuple[str, str], SpecInfo]:
    """(resource page, method name) -> verb/path/param docs, /private/ routes skipped."""
    spec = json.loads(gen.SPEC_PATH.read_text())
    index: dict[tuple[str, str], SpecInfo] = {}
    for path, methods in spec["paths"].items():
        if gen.EXCLUDED_PATH_SEGMENT in path:
            continue
        for verb, op in methods.items():
            tag = op["tags"][0]
            if tag in gen.EXCLUDED_TAGS:
                continue
            page = gen.TAG_TO_MODULE[tag][0]
            docs: dict[str, str] = {}
            for p in op.get("parameters", []):
                desc = " ".join(p.get("description", "").split())
                if desc and desc.lower() != p["name"].lower():
                    docs[gen.to_snake_case(p["name"])] = desc
            index[(page, gen.method_name_for(op["operationId"]))] = SpecInfo(
                verb.upper(), path, op.get("summary", ""), docs
            )
    return index


def clean_type(annotation: object) -> str:
    text = "-" if annotation is inspect.Signature.empty else str(annotation)
    return text.replace("generated.", "")


def split_paragraphs(doc: str) -> list[str]:
    paragraphs = []
    for chunk in re.split(r"\n\s*\n", inspect.cleandoc(doc)):
        lines = [ln.strip() for ln in chunk.strip().splitlines() if ln.strip()]
        if lines:
            paragraphs.append("\n".join(lines))
    return paragraphs


def parse_roles(paragraphs: list[str]) -> tuple[list[tuple[str, str]] | None, list[str]]:
    """Pull an 'Allowed roles:' block out of the paragraphs. Returns (rows, rest)."""
    for i, para in enumerate(paragraphs):
        if para.split("\n")[0].strip().lower() != "allowed roles:":
            continue
        rows: list[tuple[str, str]] = []
        j = i + 1
        while j < len(paragraphs):
            m = re.fullmatch(r"([^:\n]{1,40}):\s*(.+)", paragraphs[j])
            if not m or not _ROLE_VALUE_RE.fullmatch(m.group(2).strip()):
                break
            roles = ", ".join(r.strip() for r in m.group(2).split(",") if r.strip())
            rows.append((m.group(1).strip(), roles))
            j += 1
        return rows, paragraphs[:i] + paragraphs[j:]
    return None, paragraphs


def build_method_doc(
    name: str,
    func: Any,
    spec: SpecInfo | None,
    caveat_keys: list[str],
    *,
    with_roles: bool,
    skip_first: bool,
) -> MethodDoc:
    paragraphs = split_paragraphs(inspect.getdoc(func) or "")
    roles_first = (
        bool(paragraphs) and paragraphs[0].split("\n")[0].strip().lower() == "allowed roles:"
    )
    roles, paragraphs = parse_roles(paragraphs)

    verb_path = f"{spec.verb} {spec.path}" if spec else None
    if paragraphs:
        m = _VERB_PATH_RE.match(" ".join(paragraphs[0].split()))
        if m:
            if verb_path is None:
                verb_path = f"{m.group(1)} {m.group(2).rstrip(':').replace(', ', ',')}"
            # Drop the "VERB /path:" prefix from the first paragraph.
            flat = " ".join(paragraphs[0].split())
            rest = flat[m.end() :].lstrip(": ").strip()
            if flat[m.end() - 1 : m.end()] == ":":
                rest = flat[m.end() :].strip()
            paragraphs = ([rest] if rest else []) + paragraphs[1:]
    if spec and (roles_first or not paragraphs):
        # The docstring is only a roles block (+ generator notes): use the spec's summary.
        summary, details = spec.summary, paragraphs
    else:
        summary = paragraphs[0].replace("\n", " ") if paragraphs else ""
        details = paragraphs[1:]

    sig = inspect.signature(func)
    params = list(sig.parameters.values())
    if skip_first:
        params = params[1:]
    args = []
    for p in params:
        required = p.default is inspect.Parameter.empty and p.kind not in (
            p.VAR_POSITIONAL,
            p.VAR_KEYWORD,
        )
        args.append(
            ArgRow(
                name=(
                    "*" if p.kind is p.VAR_POSITIONAL else "**" if p.kind is p.VAR_KEYWORD else ""
                )
                + p.name,
                type=clean_type(p.annotation),
                required=required,
                default="" if p.default is inspect.Parameter.empty else repr(p.default),
                description=spec.param_docs.get(p.name, "") if spec else "",
            )
        )
    caveats: list[tuple[str, str]] = []
    for key in caveat_keys:
        if key in CAVEATS:
            caveats = CAVEATS[key]
            break
    return MethodDoc(
        name=name,
        verb_path=verb_path,
        has_spec=spec is not None,
        summary=summary,
        details=details,
        roles=(roles if roles else None) if with_roles else None,
        args=args,
        returns=clean_type(sig.return_annotation),
        caveats=caveats,
    )


def esc(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_method(doc: MethodDoc, call_prefix: str, *, resource: bool, with_roles: bool) -> str:
    out = [f"### {doc.name}", ""]
    if doc.summary:
        out += [doc.summary, ""]
    if doc.verb_path:
        out += [f"**HTTP:** `{doc.verb_path}`", ""]
    if doc.call:
        out += [f"**Call:** `{doc.call}`", ""]
    elif resource:
        out += [
            f"**Call:** `{call_prefix}.{doc.name}(...)` "
            f"(async client: `await a_{call_prefix}.{doc.name}(...)`)",
            "",
        ]
    else:
        out += [f"**Call:** `{call_prefix}{doc.name}(...)`", ""]
    if doc.args:
        out += ["| Argument | Type | Required | Default | Description |", "|---|---|---|---|---|"]
        for a in doc.args:
            default = f"`{esc(a.default)}`" if a.default else ""
            out.append(
                f"| `{a.name}` | `{esc(a.type)}` | {'yes' if a.required else 'no'} "
                f"| {default} | {esc(a.description)} |"
            )
        out.append("")
    else:
        out += ["No arguments.", ""]
    out += [f"**Returns:** `{doc.returns}`", ""]
    if with_roles:
        out += ["**Allowed roles:**", ""]
        if doc.roles:
            out += ["| Dataset type | Roles |", "|---|---|"]
            out += [f"| {esc(t)} | {esc(r)} |" for t, r in doc.roles]
        elif doc.verb_path or doc.has_spec:
            out.append(NO_ROLES)
        else:
            out.append("Not an endpoint of its own; the rights are those of the underlying calls.")
        out.append("")
    if doc.details:
        for para in doc.details:
            out += [para, ""]
    if doc.caveats:
        out += ["**Live-tested notes:**", ""]
        out += [f"- {note}" for note, _source in doc.caveats]
        out.append("")
    return "\n".join(out)


def resource_class(client: ReportnetClient, attr: str) -> type:
    return type(getattr(client, attr))


def public_functions(cls: type) -> list[tuple[str, Any]]:
    return sorted(
        (n, f) for n, f in inspect.getmembers(cls, inspect.isfunction) if not n.startswith("_")
    )


def page_header(title: str, intro: str) -> list[str]:
    return [
        f"# {title}",
        "",
        "> Generated by `scripts/generate_docs.py` (`scripts/regen_docs.sh`). Do not edit by hand.",
        "",
        intro,
        "",
        "[Back to index](index.md)",
        "",
    ]


def build_pages() -> tuple[dict[str, str], dict[str, list[MethodDoc]]]:
    spec_index = load_spec_index()
    client = ReportnetClient("https://example.invalid", "docs")
    pages: dict[str, str] = {}
    docs_by_page: dict[str, list[MethodDoc]] = {}

    for page, title in RESOURCE_PAGES:
        cls = resource_class(client, page)
        docs = [
            build_method_doc(
                n,
                f,
                spec_index.get((page, n)),
                [f"{page}.{n}", n],
                with_roles=True,
                skip_first=True,
            )
            for n, f in public_functions(cls)
        ]
        docs_by_page[page] = docs
        intro = (
            f"Methods of `client.{page}` (`{cls.__module__}.{cls.__name__}`). Every method also "
            f"exists on `AsyncReportnetClient` as `await a_client.{page}.<name>(...)` with the "
            "same arguments. Roles are copied from the API spec; where it states none, this page "
            "says so rather than guessing."
        )
        lines = page_header(title, intro)
        lines += ["## Methods", ""] + [f"- [{d.name}](#{d.name})" for d in docs] + [""]
        lines += [render_method(d, f"client.{page}", resource=True, with_roles=True) for d in docs]
        pages[page] = "\n".join(lines).rstrip("\n") + "\n"

    for page, module, title in MODULE_PAGES:
        funcs = sorted(
            (n, f)
            for n, f in inspect.getmembers(module, inspect.isfunction)
            if not n.startswith("_") and f.__module__ == module.__name__
        )
        docs = [
            build_method_doc(n, f, None, [f"{page}.{n}", n], with_roles=False, skip_first=False)
            for n, f in funcs
        ]
        docs_by_page[page] = docs
        intro = (
            f"Hand-written helpers in `{module.__name__}`. They are plain functions, not methods "
            "of a resource, and make no endpoint of their own: the ReportNet rights needed are "
            "those of the underlying API calls (see the resource pages)."
        )
        lines = page_header(title, intro)
        lines += ["## Functions", ""] + [f"- [{d.name}](#{d.name})" for d in docs] + [""]
        prefix = f"{page}."
        lines += [render_method(d, prefix, resource=False, with_roles=False) for d in docs]
        pages[page] = "\n".join(lines).rstrip("\n") + "\n"

    docs = []
    for cls, var in HANDLE_CLASSES:
        for n, member in sorted(vars(cls).items()):
            if n.startswith("_") or not (
                isinstance(member, property) or inspect.isfunction(member)
            ):
                continue
            prop = isinstance(member, property)
            func = member.fget if isinstance(member, property) else member
            d = build_method_doc(
                f"{cls.__name__}.{n}",
                func,
                None,
                [f"handles.{cls.__name__}.{n}", f"{cls.__name__}.{n}"],
                with_roles=False,
                skip_first=True,
            )
            d.call = f"{var}.{n}" if prop else f"{var}.{n}(...)"
            if prop:
                d.args = []
            docs.append(d)
    docs_by_page["handles"] = docs
    intro = (
        "Handles are frozen dataclasses from `reportnet_api.handles` that delegate to the "
        "`easy` functions and add no endpoint, so the ReportNet rights needed are those of "
        "those calls. Get one with `easy.find_dataflow(client, id_or_name)` "
        "(`flow`), then `flow.dataset(id, country code or name)` (`ds`). A handle is a snapshot: "
        "`flow.refresh()` returns a new one."
        "Properties are written without brackets."
    )
    lines = page_header(HANDLES_TITLE, intro)
    lines += (
        ["## Members", ""]
        + [f"- [{d.name}](#{d.name.lower().replace('.', '')})" for d in docs]
        + [""]
    )
    lines += [render_method(d, "", resource=False, with_roles=False) for d in docs]
    pages["handles"] = "\n".join(lines).rstrip("\n") + "\n"

    pages["index"] = render_index(docs_by_page)
    return pages, docs_by_page


INDEX_INTRO = """\
# Reportnet API Python client: reference

> Generated by `scripts/generate_docs.py` (`scripts/regen_docs.sh`). Do not edit by hand;
> change the code, `scripts/docs_caveats.py` or the generator and regenerate.

Look up any function to see its arguments, the ReportNet rights it needs and the caveats found
by live testing. Argument lists and roles come from the code and `spec/api-docs.json`; the
"Live-tested notes" come from a small hand-kept file (`scripts/docs_caveats.py`) that only repeats
facts recorded in `docs/live_testing_notes.md`.

## ApiKey or Bearer?

ReportNet accepts two kinds of credential, and they are not interchangeable:

- **ApiKey**: a dataflow-scoped key issued to a reporting provider. It carries Reporter-level
  access only and works only for its own dataflow (403 elsewhere). It cannot satisfy a rule that
  needs a user-level dataflow role such as `DATAFLOW_CUSTODIAN` or `DATAFLOW_STEWARD`.
- **Bearer**: the JWT of a logged-in user. It carries that user's actual roles on each dataflow.

A higher role is not always better: the ETL endpoints returned 403 for a Custodian/Steward Bearer
credential while an ApiKey worked (see the notes on those methods). A dead or revoked ApiKey shows
up as a `500` "401 UNAUTHORIZED" on any call; `list_datasets` is a quick way to check.

"Allowed roles" tables are what the API spec declares per dataset type; for methods whose spec
states none (including hand-written ones) the page says "Not stated in the API spec". The
`/private/*` operations in the spec are not on this client (they are unreachable through the
gateway), see [removed private endpoints](../removed_private_endpoints.md).

Every resource method also exists on `AsyncReportnetClient`, called with `await`.

## Pages

"""


_SUMMARY_WIDTH = 110  # index entries longer than this are cut with "..."


def render_index(docs_by_page: dict[str, list[MethodDoc]]) -> str:
    titles = dict(RESOURCE_PAGES) | {p: t for p, _m, t in MODULE_PAGES}
    titles["handles"] = HANDLES_TITLE
    lines = [INDEX_INTRO.rstrip("\n"), ""]
    order = [p for p, _ in RESOURCE_PAGES] + [p for p, _m, _t in MODULE_PAGES] + ["handles"]
    for page in order:
        docs = docs_by_page[page]
        lines += [f"### [{titles[page]}]({page}.md)", ""]
        for d in docs:
            summary = (
                d.summary
                if len(d.summary) <= _SUMMARY_WIDTH
                else d.summary[: _SUMMARY_WIDTH - 3].rstrip() + "..."
            )
            anchor = d.name.lower().replace(".", "")
            lines.append(f"- [`{d.name}`]({page}.md#{anchor}): {esc(summary)}")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def write_docs(out_dir: Path = OUT_DIR) -> dict[str, list[MethodDoc]]:
    pages, docs_by_page = build_pages()
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in pages.items():
        (out_dir / f"{name}.md").write_text(text)
    return docs_by_page


def main() -> None:
    docs_by_page = write_docs()
    resource_docs = [d for p, _ in RESOURCE_PAGES for d in docs_by_page[p]]
    with_roles = sum(1 for d in resource_docs if d.roles)
    noted = sum(1 for docs in docs_by_page.values() for d in docs if d.caveats)
    total = sum(len(v) for v in docs_by_page.values())
    print(
        f"wrote {len(docs_by_page) + 1} pages to {OUT_DIR.relative_to(REPO_ROOT)}: "
        f"{total} entries ({len(resource_docs)} resource methods, {with_roles} with roles, "
        f"{len(resource_docs) - with_roles} 'not stated'), {noted} with live-tested notes"
    )


if __name__ == "__main__":
    main()
