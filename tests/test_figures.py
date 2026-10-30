"""The README figures have to be pictures of this program.

A PNG cannot be diffed, so the text that was rendered into `docs/img/verify.png`
is written beside it as `docs/img/verify.txt`, and this file runs the demo again
and compares. Without that comparison the figure would rot silently: the tests
stay green, the picture keeps showing a summary line from three versions ago,
and the first person to notice is a reader who runs the command and gets
different output than the image promised.

The other half is the sidecar itself. A generated file that nobody regenerates
is a file that describes the past, so the image and the sidecar must name the
same lines - if someone edits one by hand, this fails.
"""

import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
IMG = ROOT / "docs" / "img"
SIDECAR = IMG / "verify.txt"
PNG = IMG / "verify.png"
PAGE = IMG / "page.png"


def _demo_output() -> list[str]:
    """The demo run, exactly as `tools/make_figures.py` captures it."""
    result = subprocess.run(
        [sys.executable, "-m", "citevouch", "verify", "manuscript.md"],
        cwd=ROOT / "demo",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"},
        timeout=180,
    )
    assert result.returncode == 1, f"the demo must still exit 1, got {result.returncode}"
    lines = ["$ citevouch verify manuscript.md", *result.stdout.rstrip().splitlines()]
    if result.stderr.strip():
        lines += result.stderr.rstrip().splitlines()
    return lines


def test_the_sidecar_exists() -> None:
    assert SIDECAR.is_file(), "docs/img/verify.txt is missing; run tools/make_figures.py"


def test_the_figure_files_are_where_the_readme_points() -> None:
    for path in (PNG, PAGE):
        assert path.is_file(), f"{path.name} is missing; run tools/make_figures.py"
        assert path.stat().st_size > 5_000, f"{path.name} is too small to be a figure"


def test_the_text_in_the_figure_is_what_the_demo_prints_today() -> None:
    """The only mechanical check a PNG allows.

    The picture is rasterised text, so the text is the part that can be compared.
    If this fails, the figure is stale: regenerate it, do not edit the sidecar.
    """
    recorded = SIDECAR.read_text(encoding="utf-8").rstrip("\n").split("\n")
    current = _demo_output()
    assert recorded == current, (
        "docs/img/verify.png shows output the demo no longer produces;"
        " run `PYTHONPATH=src python tools/make_figures.py`"
    )


def test_the_sidecar_starts_with_the_command_it_illustrates() -> None:
    first = SIDECAR.read_text(encoding="utf-8").split("\n", 1)[0]
    assert first == "$ citevouch verify manuscript.md", first


def _png_size(path: pathlib.Path) -> tuple[int, int]:
    """Read width and height out of the PNG header.

    Deliberately not `Pillow`: this test runs in CI, where the dependencies are
    the tool's and the test runner's. Pulling an image library into `dev` to
    read eight bytes would be a dependency bought for one assertion. PNG puts
    the dimensions in the IHDR chunk, which always starts at byte 16.
    """
    header = path.read_bytes()[:24]
    assert header[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a PNG"
    assert header[12:16] == b"IHDR", f"{path.name}: first chunk is not IHDR"
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    return width, height


def test_the_page_figure_is_an_excerpt_not_a_whole_page() -> None:
    """A screenshot of the whole page would be unreadable at README width.

    The crop is bounded by the paragraph the highlighted sentence is in, so the
    image has to be short. This asserts the property rather than the exact
    height, which changes with dpi and would make the test a nuisance.
    """
    width, height = _png_size(PAGE)
    assert height < 400, (
        f"page.png is {width}x{height}; the crop grew back into a whole-page"
        " screenshot, which is unreadable at README width"
    )
    assert width > 800, "page.png is too narrow to show a two-column page"


def test_the_licence_and_origin_are_written_down() -> None:
    """Both figures come from someone else's paper; that has to be stated."""
    text = (IMG / "README.md").read_text(encoding="utf-8")
    assert "ACL" in text, "the excerpt's origin is not recorded"
    assert "removed" in text, "there is no stated response if a rights holder objects"
