"""The one place that decides a source file is not the manuscript."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .model import Finding

# Why this is a function rather than two lines in each caller.
#
# `scan` resolves a claim's source through `resolve_source`, and so does
# `verify`; `--source` is read by `read_source_table` and handed to both.  A
# check written into one of those three would leave the other two, which is how
# this defect survived: the manifest route, the `--source` route and the
# recorded-ledger route each opened the file and none of them asked what it was.
#
# Measured on a project whose `sources.toml` maps `paper` to the manuscript:
#
#     citevouch check paper.md --root .   ->  0, [info] quote-found
#
# for a sentence that exists nowhere except inside the claim block asserting it.
# The quote was searched for on "page 1" of the file that contains it, so the
# tool certified its own input as independent evidence.


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_the_manuscript(
    source: str | Path, manuscript: str | Path, manuscript_digest: str = ""
) -> bool:
    """Is this source file the manuscript, or a byte-for-byte copy of it?

    Path identity alone is not enough. A manuscript is often copied to a
    staging name inside the same project (``paper.md`` duplicated as ``p.md``
    before a build), and the copy has exactly the same problem the original
    has: the sentence in the claim block is on its page because the claim block
    is on its page.

    The digest is passed in by callers that already computed it, so a normal
    run does not hash the manuscript a second time. Empty means "not computed
    here", in which case only the path comparison runs.
    """
    left = Path(source)
    right = Path(manuscript)
    try:
        if left.resolve() == right.resolve():
            return True
    except OSError:
        # A path that cannot be resolved cannot be the file we are reading, so
        # this is the safe answer: let the ordinary source checks speak.
        return False
    if manuscript_digest and left.is_file():
        try:
            if sha256_bytes(left.read_bytes()) == manuscript_digest:
                return True
        except OSError:
            return False
    return False


def source_is_manuscript_finding(
    key: str, source: str | Path, claim_id: str = "", path: str = "", line: int = 0
) -> Finding:
    """The finding, spelled once so the three callers say the same sentence."""
    return Finding(
        code="source-is-manuscript",
        message=(
            f"source {key!r} is {Path(source).name}, the manuscript this claim "
            "is written in - a file cannot be the evidence for its own sentences"
        ),
        claim_id=claim_id,
        path=path,
        line=line,
    )
