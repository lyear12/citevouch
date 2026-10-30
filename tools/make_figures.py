"""Render the two README figures from the demo project.

Run:  PYTHONPATH=src python tools/make_figures.py

`docs/img/verify.png` is the real output of `citevouch verify manuscript.md` in
`demo/`, captured by running it - not a mock-up. `docs/img/page.png` is the page
that first line is talking about, rendered from the real PDF with the quoted
sentence highlighted.

Two consequences worth stating, because both are easy to break:

- The images are generated, so they can go stale. `tests/test_figures.py` fails
  when the recorded output of the demo no longer matches the text burned into the
  terminal image, which is the only part of a PNG we can compare mechanically.
- The page image is a short excerpt of one paragraph, not a whole paper, and
  `docs/img/README.md` records where it came from and under what licence.

Needs `pymupdf` to rasterise the PDF. That is a figure tool's dependency, not the
tool's: `src/citevouch` never imports it.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pymupdf
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
IMG = ROOT / "docs" / "img"
MONO = "C:/Windows/Fonts/consola.ttf"
BG = (30, 30, 32)
FG = (220, 220, 220)
DIM = (140, 140, 145)
INFO = (120, 190, 255)
HIGH = (255, 120, 120)
OK = (140, 220, 150)

# The figure is about one paragraph, so it shows one paragraph.  Rendering the
# whole page would make the paragraph unreadable at README width and would put a
# paper's figures and captions in this repository for no reason.
PAGE = 6
NEEDLE = "The resulting grammar consists"
PDF = "demo/papers/2026_VanEecke-Beuls_CoNLL2026_large-scale-CxG.pdf"


def wrap(text: str, limit: int) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        line = raw
        while len(line) > limit:
            cut = line.rfind(" ", 0, limit)
            cut = limit if cut <= 0 else cut
            out.append(line[:cut])
            line = " " * 2 + line[cut:].lstrip()
        out.append(line)
    return out


def terminal(lines: list[str], width: int = 96) -> Image.Image:
    body = wrap("\n".join(lines), width)
    font = ImageFont.truetype(MONO, 15)
    pad, lh, title_h = 26, 24, 36
    height = title_h + pad * 2 + lh * len(body)
    img = Image.new("RGB", (pad * 2 + int(font.getlength("M" * width)), height), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, img.width, title_h], fill=(45, 45, 48))
    for index, colour in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        draw.ellipse([16 + index * 22, 12, 28 + index * 22, 24], fill=colour)
    draw.text((96, 10), "citevouch demo/", font=ImageFont.truetype(MONO, 14), fill=DIM)
    y = title_h + pad
    for line in body:
        colour = FG
        if line.startswith("[info]"):
            colour = INFO
        elif line.startswith("[high]"):
            colour = HIGH
        elif line.startswith(("citevouch:", "worst")):
            colour = OK
        elif line.startswith("$"):
            colour = DIM
        draw.text((pad, y), line, font=font, fill=colour)
        y += lh
    return img


def demo_output() -> list[str]:
    verify = subprocess.run(
        [sys.executable, "-m", "citevouch", "verify", "manuscript.md"],
        cwd=ROOT / "demo",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        # Starts from the real environment: a figure that drops PATH loses
        # `pdftotext` and draws a picture of a broken install instead of the demo.
        env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"},
        timeout=180,
    )
    if verify.returncode != 1:
        raise SystemExit(f"the demo must still exit 1, got {verify.returncode}")
    lines = ["$ citevouch verify manuscript.md", *verify.stdout.rstrip().splitlines()]
    if verify.stderr.strip():
        lines += verify.stderr.rstrip().splitlines()
    return lines


def page_excerpt(margin: int = 22) -> Image.Image:
    doc = pymupdf.open(ROOT / PDF)
    page = doc[PAGE - 1]
    anchor = page.search_for(NEEDLE)
    if not anchor:
        raise SystemExit(f"{NEEDLE!r} is not on page {PAGE} of {PDF}")
    for rect in page.search_for("40,688"):
        page.add_highlight_annot(rect)
    page.add_highlight_annot(anchor[0])
    # Crop by whole lines around the highlight.  A two-column page has two
    # paragraph shapes side by side, so neither "the block containing it" nor a
    # fixed pixel height ends on a paragraph boundary - both left a half-line of
    # text hanging off the bottom.  Six lines of context, snapped to real line
    # boxes, ends where the eye expects and keeps the image short enough to read
    # at README width.
    body = anchor[0]
    lines = [
        pymupdf.Rect(line["bbox"])
        for block in page.get_text("dict")["blocks"]
        if block["type"] == 0
        for line in block["lines"]
    ]
    line_height = min(rect.height for rect in lines)
    wanted_top = body.y0 - 6 * line_height
    wanted_bottom = body.y1 + 7 * line_height
    # Snap *inside* the window.  Selecting by overlap instead pulled in a
    # neighbour whose bbox is tall for its own reasons (a footnote superscript
    # stretches one line box past its baseline), and that line then appeared
    # sliced at the top edge of the image.
    tops = [rect.y0 for rect in lines if rect.y0 >= wanted_top]
    ends = [rect.y1 for rect in lines if rect.y1 <= wanted_bottom]
    if not tops or not ends:
        raise SystemExit("the window holds no whole line")
    top = min(tops)
    bottom = max(ends)
    dpi = 170
    scale = dpi / 72
    pix = page.get_pixmap(dpi=dpi)
    raw = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    cropped = raw.crop(
        (
            int(40 * scale),
            int(top * scale),
            int((page.rect.width - 40) * scale),
            int(bottom * scale),
        )
    )
    framed = Image.new(
        "RGB", (cropped.width + margin * 2, cropped.height + margin * 2), (232, 232, 235)
    )
    framed.paste(cropped, (margin, margin))
    return framed


def main() -> None:
    IMG.mkdir(parents=True, exist_ok=True)
    lines = demo_output()
    terminal(lines).save(IMG / "verify.png")
    # The PNG cannot be diffed, but the text burned into it can: the same lines
    # go to a sidecar file, and `tests/test_figures.py` compares that file with a
    # fresh run of the demo. Without it the figure would rot silently while every
    # test stayed green.
    (IMG / "verify.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    page_excerpt().save(IMG / "page.png")
    for name in ("verify.png", "verify.txt", "page.png"):
        print(f"docs/img/{name} {(IMG / name).stat().st_size} bytes")


if __name__ == "__main__":
    main()
