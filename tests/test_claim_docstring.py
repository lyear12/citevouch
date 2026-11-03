"""The docstring on ``Claim`` described a behaviour that does not exist.

It said the ledger stores the quote's fingerprint so a later run can tell "the
quote is gone" from "the quote moved".  Nothing reads ``quote_fingerprint``
back: ``quote-moved`` is decided from the page numbers the current run found.
That is the fourth entry in this project's most frequent defect family - a
comment promising an implementation that was never written - and it is worth a
test because the docstring is the only place that claim is made.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from citevouch import model

SOURCE = "src/citevouch/model.py"


def _claim_docstring() -> str:
    return inspect.getdoc(model.Claim) or ""


class TestTheDocstringDescribesThisCode:
    def test_it_does_not_claim_the_fingerprint_decides_anything(self) -> None:
        """The load-bearing sentence.  A reader who believes the fingerprint
        separates "gone" from "moved" will look for that comparison in
        ``verify`` and not find it, then doubt the code instead of the note."""
        text = _claim_docstring()
        assert "can tell" not in text
        assert "record, not a decider" in text

    def test_it_still_explains_what_the_field_is_for(self) -> None:
        text = _claim_docstring()
        assert "quote_fingerprint" in text
        assert "digest" in text

    def test_it_names_the_property_that_actually_matters(self) -> None:
        """``--allow-stale`` exists so an edited manuscript is still checked.
        Saying that in the field's own docstring is what stops the next reader
        from re-introducing the "gone vs moved" story."""
        text = _claim_docstring()
        assert "--allow-stale" in text


class TestNothingReadsTheFingerprintBack:
    def test_the_only_writer_is_the_parser(self) -> None:
        """One place computes it - the parser, when it reads a claim block.

        If this fails, something new produces fingerprints and the docstring
        above has to say what they are for; the listing is the point, so the
        failure names what changed rather than a bare mismatch.
        """
        root = Path(__file__).resolve().parent.parent
        producers: list[str] = []
        for path in sorted((root / "src" / "citevouch").glob("*.py")):
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                stripped = line.strip()
                if "quote_fingerprint" not in stripped:
                    continue
                if "=fingerprint(" in stripped:
                    producers.append(f"{path.name}:{number}")
        # The *file* is the claim; the line number is not.  Pinning the number
        # made this test fail every time an unrelated edit moved the parser's
        # fingerprint call down the file, which is a red that says nothing about
        # whether a second writer appeared.  The listing in the message stays,
        # so a real change still names the place that changed.
        assert [place.split(":")[0] for place in producers] == ["manuscript.py"], (
            "the set of places that compute a quote fingerprint changed: "
            + ", ".join(producers)
        )

    def test_no_module_decides_anything_from_the_digest(self) -> None:
        """The claim the docstring makes is about verdicts, so this checks
        verdicts: no comparison against a stored fingerprint anywhere."""
        root = Path(__file__).resolve().parent.parent
        suspects: list[str] = []
        for path in sorted((root / "src" / "citevouch").glob("*.py")):
            if path.name == "model.py":
                continue
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                # Writing it is not deciding on it: the parser fills the field
                # and model.py's own serialiser writes it to the ledger.  What
                # the docstring rules out is a *comparison*.
                if "quote_fingerprint" not in line:
                    continue
                if "=fingerprint(" in line or "quote_fingerprint=" in line:
                    continue
                suspects.append(f"{path.name}:{number}: {line.strip()}")
        assert suspects == [], (
            "a module outside model.py mentions quote_fingerprint; the Claim "
            "docstring says it is a record, so say why it is read there: " + "; ".join(suspects)
        )
