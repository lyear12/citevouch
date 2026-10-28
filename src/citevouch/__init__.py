"""citevouch — bind claims to the page that proves them, then keep them honest.

A citation checker answers "does this reference exist?".  citevouch answers a
different question: "can I still find, in *this* copy of the source, the words
my manuscript points at — and did the sentence that makes the claim change
since I last looked?"

The public surface is deliberately small: the CLI in :mod:`citevouch.cli` and
the dataclasses in :mod:`citevouch.model`.
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["__version__"]
