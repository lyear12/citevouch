"""The third review: what the strict resolver still got wrong.

Every test here failed before the change it defends.  A regression test that
would have passed anyway records a fix; it does not defend one.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import ClassVar

import pytest

from citevouch.errors import UsageError
from citevouch.model import Ledger
from citevouch.sources import (
    discover_sources,
    near_misses,
    page_hint_is_valid,
    resolve_source,
)

# --- N1: a key that exists nowhere must not bind to something that exists ---


class TestNoInferenceByPrefix:
    """Binding is exact or case-exact. Nothing else, ever.

    The prefix loops lived in ``resolve_source`` rather than in discovery, so
    the changelog entry that claimed they were gone was describing the wrong
    file.  A typo silently bound to a real PDF and produced a confident
    ``quote-found`` on a paper the author had not named.
    """

    KNOWN: ClassVar[dict[str, str]] = {
        "vaneecke2026cxn": "papers/2026_VanEecke-Beuls_CoNLL2026_large-scale-CxG.pdf",
        "smith2020": "papers/smith2020.pdf",
    }

    def test_an_exact_key_resolves(self):
        assert resolve_source("smith2020", self.KNOWN) == "papers/smith2020.pdf"

    def test_case_only_differences_resolve(self):
        assert resolve_source("Smith2020", self.KNOWN) == "papers/smith2020.pdf"

    @pytest.mark.parametrize(
        "key",
        [
            "vaneecke2026",
            "vaneecke2026cxnWRONGSUFFIX",
            "smith2020sec3",
            "vane",
            "smith2020.pdf",
        ],
    )
    def test_a_key_that_is_a_prefix_or_a_superset_does_not_resolve(self, key):
        """Each of these bound to a real file under the old prefix rule."""
        assert resolve_source(key, self.KNOWN) is None

    def test_an_empty_key_resolves_to_nothing(self):
        assert resolve_source("", self.KNOWN) is None

    def test_a_typo_reaches_the_reader_as_a_missing_source_not_a_match(self, project):
        """The end-to-end consequence, through the real scanner."""
        manuscript = project / "m.md"
        manuscript.write_text(
            "```claim id=c1 source=smith2026cxnWRONGSUFFIX page=1\n"
            "quote: |\n"
            "  154,391 sentences\n"
            "```\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "citevouch",
                "check",
                str(manuscript),
                "--root",
                str(project),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            env=_env(),
        )
        assert result.returncode == 1, result.stdout + result.stderr
        assert "quote-found" not in result.stdout


# --- N2: the suggestion list has to survive real filenames ------------------

REAL_NAMES = [
    "papers/2026_VanEecke-Beuls_CoNLL2026_large-scale-CxG.pdf",
    "papers/2020_TayyarMadabushi-etal_CxGBERT.pdf",
    "papers/1994_Goldberg_Constructions.pdf",
]


class TestNearMisses:
    """The error message is the feature; a strict resolver with no candidates
    turns a typo into a dead end that only grep can solve."""

    def test_a_real_key_finds_its_real_file(self):
        assert near_misses("vaneecke2026cxn", REAL_NAMES) == [REAL_NAMES[0]]

    def test_a_truncated_key_finds_it_too(self):
        assert near_misses("vaneecke2026", REAL_NAMES) == [REAL_NAMES[0]]

    def test_an_author_name_finds_the_file_it_names(self):
        assert near_misses("VanEecke", REAL_NAMES) == [REAL_NAMES[0]]

    def test_a_paper_acronym_finds_its_file(self):
        assert near_misses("cxgbert", REAL_NAMES) == [REAL_NAMES[1]]

    def test_unrelated_keys_get_no_suggestion(self):
        assert near_misses("zzz999", REAL_NAMES) == []
        assert near_misses("完全无关的键", REAL_NAMES) == []

    def test_a_key_that_is_only_a_year_does_not_name_every_paper(self):
        """1994 appears in a filename, but a two-token file should not be
        suggested on the strength of its year alone against a three-token key
        with nothing else in common."""
        assert (
            near_misses("2026", REAL_NAMES) == [] or len(near_misses("2026", REAL_NAMES)) == 1
        )

    def test_the_limit_is_respected(self):
        assert len(near_misses("paper", REAL_NAMES, limit=1)) <= 1


# --- N3: the same page rule on both sides -----------------------------------


class TestPageHintIsValid:
    @pytest.mark.parametrize(
        ("page", "count", "expected"),
        [
            (None, 10, True),
            (1, 10, True),
            (10, 10, True),
            (0, 10, False),
            (-1, 10, False),
            (11, 10, False),
            (1, 0, True),
            (99, 0, True),
        ],
    )
    def test_the_rule(self, page, count, expected):
        assert page_hint_is_valid(page, count) is expected

    def test_a_zero_page_in_the_ledger_is_reported_as_out_of_range(self, project, manuscript):
        """verify used to report `quote-moved` here: true sentence, false
        premise, author sent hunting for a restructuring that never happened."""
        _record(project)
        ledger_path = project / "citevouch.lock.json"
        raw = json.loads(ledger_path.read_text(encoding="utf-8"))
        raw["claims"][0]["page"] = 0
        ledger_path.write_text(json.dumps(raw), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "citevouch",
                "verify",
                str(manuscript),
                "--root",
                str(project),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            env=_env(),
        )
        assert result.returncode == 1
        assert "page-out-of-range" in result.stdout
        assert "quote-moved" not in result.stdout

    def test_a_ledger_page_beyond_the_document_is_not_a_move_either(self, project, manuscript):
        _record(project)
        ledger_path = project / "citevouch.lock.json"
        raw = json.loads(ledger_path.read_text(encoding="utf-8"))
        raw["claims"][0]["page"] = 99
        ledger_path.write_text(json.dumps(raw), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "citevouch",
                "verify",
                str(manuscript),
                "--root",
                str(project),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            env=_env(),
        )
        assert result.returncode == 1
        assert "page-out-of-range" in result.stdout


# --- N4: a directory is not a source, and an exception is not an exit code --


class TestUsageMistakesStayInsideTheExitContract:
    def test_a_directory_passed_as_a_source_is_refused_not_ignored(self, project):
        """It used to be dropped from the map in silence.

        Silence reads as "no such key was needed", so the claim the caller
        meant to bind reported `source-missing` and the author went looking
        for a PDF that was on disk the whole time. A path the caller named
        and this tool cannot use is a usage error.
        """
        (project / "adir").mkdir(exist_ok=True)
        with pytest.raises(UsageError) as caught:
            discover_sources(project, [str(project / "adir")])
        assert "is a directory, not a file" in str(caught.value)

    def test_a_directory_in_the_manifest_is_ignored_too(self, project):
        (project / "adir").mkdir(exist_ok=True)
        (project / "sources.toml").write_text(
            '[sources]\np = "papers/2026_smith_networks.txt"\nother = "adir"\n',
            encoding="utf-8",
        )
        found = discover_sources(project, [])
        assert "other" not in found
        assert "p" in found

    def test_init_demo_on_a_file_exits_two_with_a_sentence(self, tmp_path):
        target = tmp_path / "already-a-file.txt"
        target.write_text("x\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-m", "citevouch", "init-demo", str(target)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            env=_env(),
        )
        assert result.returncode == 2
        assert "is a file, not a directory" in result.stderr
        assert "Traceback" not in result.stderr

    def test_scan_with_a_directory_source_does_not_traceback(self, project, manuscript):
        (project / "adir").mkdir(exist_ok=True)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "citevouch",
                "scan",
                str(manuscript),
                "--root",
                str(project),
                "--source",
                str(project / "adir"),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            env=_env(),
        )
        assert "Traceback" not in result.stderr
        # 2 is the usage-error code. It used to be 0 or 1 because the
        # directory was dropped silently; 1 would also have read as a
        # verdict about the manuscript, which this is not.
        assert result.returncode == 2
        assert "is a directory, not a file" in result.stderr


# --- N5: the documents must describe the code that exists ------------------


class TestTheDocumentsDescribeThisRepository:
    def test_no_document_says_the_version_lives_in_pyproject(self):
        """The version moved to src/citevouch/_version.py; a file that still
        sends an agent to edit pyproject.toml sends it to edit nothing.

        This used to match a list of known-wrong phrasings, which only ever
        catches the sentences someone already thought of. It now checks the
        other way round: every line that mentions pyproject.toml has to say
        what pyproject.toml actually does (declares the version as dynamic, or
        hands the reader to _version.py). A sentence that describes it as the
        place the version is written is stale no matter how it is worded.

        The workflows are scanned too. The first version of this test covered
        only AGENTS.md, the READMEs and docs/, and both workflow headers went
        on saying "writes it into CHANGELOG.md and pyproject.toml" for the two
        releases after the version moved - the guard excluded the files it had
        never been pointed at.
        """
        allowed = ("declares", "reads it", "dynamic", "attr", "older checkouts", "--pyproject")
        repo = _repo()
        files = ["AGENTS.md", "README.md", "README.zh-CN.md"]
        files += [f"docs/{p.name}" for p in sorted((repo / "docs").glob("*.md"))]
        files += [
            f".github/workflows/{p.name}"
            for p in sorted((repo / ".github/workflows").glob("*.yml"))
        ]
        stale = []
        for name in files:
            path = repo / name
            if not path.exists():
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if "pyproject.toml" not in line:
                    continue
                if any(marker in line for marker in allowed):
                    continue
                stale.append(f"{name}:{number}: {line.strip()}")
        assert stale == [], (
            "these lines describe pyproject.toml as the place the version is written, "
            "but it reads the version from src/citevouch/_version.py:\n" + "\n".join(stale)
        )

    def test_the_version_file_is_named_in_the_agent_contract(self):
        text = (_repo() / "AGENTS.md").read_text(encoding="utf-8")
        assert "_version.py" in text


# --- helpers ---------------------------------------------------------------


def _env() -> dict[str, str]:
    import os

    env = dict(os.environ)
    src = str(_repo() / "src")
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _repo():
    from pathlib import Path

    return Path(__file__).resolve().parent.parent


def _record(project) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "citevouch",
            "scan",
            str(project / "manuscript.md"),
            "--root",
            str(project),
            "--quiet",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        env=_env(),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert Ledger.from_json(json.loads((project / "citevouch.lock.json").read_text("utf-8")))
