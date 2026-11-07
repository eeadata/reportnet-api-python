"""Build the reportnet-api logo (concept A, "Table three") as SVG + PNG files.

Usage: uv run --with fonttools --with cairosvg python scripts/make_logo.py <font.ttf> <out_dir>

The font is IBM Plex Mono SemiBold (SIL Open Font License), not kept in this repo:
https://github.com/google/fonts/raw/main/ofl/ibmplexmono/IBMPlexMono-SemiBold.ttf
Text is converted to paths so the SVGs need no font installed. Copy the files you need
from <out_dir> into docs/assets/.
"""

import sys
from pathlib import Path

import cairosvg
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

FONT, OUT = Path(sys.argv[1]), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)

# Python's blue (#3776AB) and yellow (#FFD43B); colours only, not the Python logo
LIGHT = {"ink": "#3776ab", "acc": "#ffd43b", "ghost": "#e4ebf2", "text": "#1e3f66",
         "api": "#3776ab", "muted": "#5b6876", "bg": "#ffffff"}
DARK = {"ink": "#5a9fd4", "acc": "#ffd43b", "ghost": "#22364d", "text": "#e9eef4",
        "api": "#ffd43b", "muted": "#9aa7b4", "bg": "#0d1b2e"}

# 3x5 table: '#' = ink cell, '*' = accent cell, '.' = empty (ghost) cell
GRID = ["###", "..#", ".*#", "..#", "###"]
CELL, GAP, X0, Y0 = 9, 3, 15.5, 3.5


def mark(c: dict, ghosts: bool = True) -> str:
    out = []
    for r, row in enumerate(GRID):
        for k, ch in enumerate(row):
            if ch == "." and not ghosts:
                continue
            fill = {"#": c["ink"], "*": c["acc"], ".": c["ghost"]}[ch]
            x, y = X0 + k * (CELL + GAP), Y0 + r * (CELL + GAP)
            out.append(f'<rect x="{x:g}" y="{y:g}" width="{CELL}" height="{CELL}" '
                       f'rx="2" fill="{fill}"/>')
    return "".join(out)


font = TTFont(FONT)
glyphs = font.getGlyphSet()
cmap = font.getBestCmap()
UPM = font["head"].unitsPerEm


def text_path(s: str, x: float, baseline: float, size: float) -> tuple[str, float]:
    """Return (path d, advance width) for s set at size px."""
    scale = size / UPM
    pen = SVGPathPen(glyphs)
    cursor = 0.0
    for ch in s:
        name = cmap[ord(ch)]
        tpen = TransformPen(pen, (scale, 0, 0, -scale, x + cursor, baseline))
        glyphs[name].draw(tpen)
        cursor += glyphs[name].width * scale
    return pen.getCommands(), cursor


def svg(w: float, h: float, body: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:g} {h:g}" '
            f'width="{w:g}" height="{h:g}" role="img" aria-label="reportnet-api">{body}</svg>\n')


def lockup(c: dict, size: float = 36) -> tuple[str, float]:
    d1, w1 = text_path("reportnet", 78, 36, size)
    d2, w2 = text_path("-api", 78 + w1, 36, size)
    d3, _ = text_path("for Python", 80, 59, 14)
    width = 78 + w1 + w2 + 4
    body = (f'{mark(c)}<path d="{d1}" fill="{c["text"]}"/><path d="{d2}" fill="{c["api"]}"/>'
            f'<path d="{d3}" fill="{c["muted"]}"/>')
    return body, width


def write(name: str, content: str) -> None:
    (OUT / name).write_text(content, encoding="utf-8")


# marks
write("logo-mark.svg", svg(64, 64, mark(LIGHT)))
write("logo-mark-dark.svg", svg(64, 64, mark(DARK)))
# favicon: no ghost cells (they turn to noise at 16 px)
write("favicon.svg", svg(64, 64, mark(LIGHT, ghosts=False)))

# lockups
for name, c in (("logo.svg", LIGHT), ("logo-dark.svg", DARK)):
    body, w = lockup(c)
    write(name, svg(w, 64, body))

# social preview 1280x640 (GitHub recommends this size)
c = LIGHT
body, w = lockup(c)
scale = 2.6
tx, ty = (1280 - w * scale) / 2, 230
tag, tw = text_path("Client for the Reportnet 3 REST API", 0, 0, 30)
social = (f'<rect width="1280" height="640" fill="{c["bg"]}"/>'
          f'<g transform="translate({tx:.1f} {ty}) scale({scale})">{body}</g>'
          f'<path d="{tag}" fill="{c["muted"]}" transform="translate({(1280 - tw) / 2:.1f} 470)"/>')
write("social-preview.svg", svg(1280, 640, social))

# PNG exports
for src, dst, wpx in [
    ("favicon.svg", "favicon-16.png", 16),
    ("favicon.svg", "favicon-32.png", 32),
    ("favicon.svg", "favicon-48.png", 48),
    ("logo-mark.svg", "logo-mark-512.png", 512),
    ("logo.svg", "logo.png", 1200),
    ("logo-dark.svg", "logo-dark.png", 1200),
    ("social-preview.svg", "social-preview.png", 1280),
]:
    cairosvg.svg2png(url=str(OUT / src), write_to=str(OUT / dst), output_width=wpx)

print("\n".join(sorted(p.name for p in OUT.iterdir())))
