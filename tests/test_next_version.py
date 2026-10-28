"""Tests for tools/next_version.py - the script that decides whether to release.

This is the file that replaces "a human looks at the changelog and types a tag".
It earns tests for the same reason the release workflow does: it runs
unattended, and its failure mode is publishing the wrong number into a package
registry, where incorrect versions cannot be withdrawn.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent.parent / "tools" / "next_version.py"


def _load():
    spec = importlib.util.spec_from_file_location("next_version", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["next_version"] = module
    spec.loader.exec_module(module)
    return module


nv = _load()


HEADER = """# Changelog

## [Unreleased]

{body}
"""


def changelog(body: str) -> str:
    return HEADER.format(body=body)


# --------------------------------------------------------------------------
# Deciding whether there is anything to release


def test_an_empty_unreleased_section_releases_nothing():
    bump, sections = nv.classify(changelog(""))
    assert bump == "none"
    assert sections == []


def test_a_heading_with_no_bullets_is_not_a_release():
    """An empty ### Added is a leftover from a template, not a claim."""
    bump, sections = nv.classify(changelog("### Added\n\n"))
    assert bump == "none"
    assert sections == []


def test_prose_without_bullets_is_not_a_release():
    bump, _ = nv.classify(changelog("Some thoughts about the next version.\n"))
    assert bump == "none"


def test_a_fixed_section_is_a_patch():
    bump, sections = nv.classify(
        changelog("### Fixed\n\n- A crash when the page hint is zero.\n")
    )
    assert bump == "patch"
    assert sections == ["Fixed"]


def test_a_security_section_is_a_patch():
    bump, _ = nv.classify(changelog("### Security\n\n- Escape the path in the SARIF URI.\n"))
    assert bump == "patch"


def test_an_added_section_is_a_minor():
    bump, sections = nv.classify(changelog("### Added\n\n- A `--since` flag.\n"))
    assert bump == "minor"
    assert sections == ["Added"]


def test_a_changed_section_is_a_minor():
    """Changed must not ride in on a patch: a pinned 0.1.* must not lose a feature."""
    bump, _ = nv.classify(changelog("### Changed\n\n- The JSON report nests the summary.\n"))
    assert bump == "minor"


def test_a_removed_section_is_a_minor():
    bump, _ = nv.classify(changelog("### Removed\n\n- The `report` verb.\n"))
    assert bump == "minor"


def test_the_heaviest_section_wins():
    body = "### Fixed\n\n- a\n\n### Added\n\n- b\n"
    bump, sections = nv.classify(changelog(body))
    assert bump == "minor"
    assert sections == ["Fixed", "Added"]


def test_an_unknown_section_name_still_counts_as_nothing():
    """Keep a Changelog allows custom names; this project does not, and silence
    about an unrecognised name would let a change ship as a patch."""
    bump, sections = nv.classify(changelog("### Whimsy\n\n- a\n"))
    assert bump == "none"
    assert sections == ["Whimsy"]


def test_the_body_stops_at_the_next_release_heading():
    text = (
        "## [Unreleased]\n\n"
        "## [0.1.0] - 2026-10-29\n\n"
        "### Added\n\n"
        "- this one is already released\n"
    )
    bump, _ = nv.classify(text)
    assert bump == "none"


def test_a_missing_unreleased_heading_is_an_error():
    with pytest.raises(nv.ChangelogError, match="Unreleased"):
        nv.classify("# Changelog\n\nnothing here\n")


# --------------------------------------------------------------------------
# Choosing the number


def test_patch_bump():
    assert nv.bump_version("0.1.0", "patch") == "0.1.1"


def test_minor_bump_resets_patch():
    assert nv.bump_version("0.1.7", "minor") == "0.2.0"


def test_none_keeps_the_version():
    assert nv.bump_version("1.4.2", "none") == "1.4.2"


def test_major_is_bumpable_by_hand():
    """0.x is the whole current life of this project, but the code must not
    pretend major bumps are impossible."""
    assert nv.bump_version("0.9.9", "minor") == "0.10.0"


@pytest.mark.parametrize("bad", ["1.0", "v1.0.0", "1.0.0-rc1", ""])
def test_a_malformed_current_version_is_an_error(bad):
    with pytest.raises(nv.ChangelogError):
        nv.bump_version(bad, "patch")


# --------------------------------------------------------------------------
# Applying it


def test_apply_moves_the_body_under_a_dated_heading():
    text = changelog("### Fixed\n\n- a crash\n")
    out = nv.apply(text, "0.1.1", "2026-10-30")
    assert "## [Unreleased]\n\n## [0.1.1] — 2026-10-30\n### Fixed\n\n- a crash\n" in out
    # the old entry is gone from Unreleased: classifying again releases nothing
    assert nv.classify(out)[0] == "none"


def test_apply_keeps_the_released_history_untouched():
    text = changelog("### Fixed\n\n- a crash\n") + "\n## [0.1.0] — 2026-10-29\n\n- earlier\n"
    out = nv.apply(text, "0.1.1", "2026-10-30")
    assert "- earlier" in out
    assert out.index("## [0.1.1]") < out.index("## [0.1.0]")


def test_apply_refuses_an_empty_release():
    with pytest.raises(nv.ChangelogError, match="empty"):
        nv.apply(changelog(""), "0.1.1", "2026-10-30")


def test_set_version_replaces_only_the_project_version():
    text = 'name = "x"\nversion = "0.1.0"\n\n[tool.ruff]\ntarget-version = "py310"\n'
    out = nv.set_pyproject_version(text, "0.2.0")
    assert 'version = "0.2.0"' in out
    assert 'target-version = "py310"' in out


def test_set_version_is_an_error_when_there_is_no_version_line():
    with pytest.raises(nv.ChangelogError):
        nv.set_pyproject_version('name = "x"\n', "0.2.0")


# --------------------------------------------------------------------------
# The command line


def test_cli_prints_the_next_version_and_exits_zero(tmp_path, capsys):
    path = tmp_path / "CHANGELOG.md"
    path.write_text(changelog("### Added\n\n- a flag\n"), encoding="utf-8")
    assert nv.main([str(path), "--current", "0.1.0"]) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "0.2.0"
    assert "minor" in captured.err


def test_cli_says_nothing_to_release_and_exits_one(tmp_path, capsys):
    path = tmp_path / "CHANGELOG.md"
    path.write_text(changelog(""), encoding="utf-8")
    assert nv.main([str(path), "--current", "0.1.0"]) == 1
    captured = capsys.readouterr()
    assert captured.out.strip() == ""
    assert "no release" in captured.err


def test_cli_apply_rewrites_the_changelog_and_pyproject(tmp_path):
    changelog_path = tmp_path / "CHANGELOG.md"
    changelog_path.write_text(changelog("### Fixed\n\n- it crashed\n"), encoding="utf-8")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "citevouch"\nversion = "0.1.0"\n', encoding="utf-8")

    code = nv.main(
        [
            str(changelog_path),
            "--current",
            "0.1.0",
            "--apply",
            "--pyproject",
            str(pyproject),
            "--date",
            "2026-10-30",
        ]
    )

    assert code == 0
    assert "## [0.1.1] — 2026-10-30" in changelog_path.read_text(encoding="utf-8")
    assert 'version = "0.1.1"' in pyproject.read_text(encoding="utf-8")


def test_cli_bump_override_wins(tmp_path, capsys):
    """A person can always insist; the script just does not need them to."""
    path = tmp_path / "CHANGELOG.md"
    path.write_text(changelog("### Fixed\n\n- a\n"), encoding="utf-8")
    assert nv.main([str(path), "--current", "0.1.0", "--bump", "minor"]) == 0
    assert capsys.readouterr().out.strip() == "0.2.0"


# --------------------------------------------------------------------------
# This repository's own changelog has to satisfy the script


def test_this_repository_changelog_parses():
    """The script is only useful if the file it reads is shaped as it expects."""
    repo = Path(__file__).resolve().parent.parent
    text = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    bump, _sections = nv.classify(text)
    assert bump in {"none", "patch", "minor"}

    declared = (repo / "pyproject.toml").read_text(encoding="utf-8")
    import re

    found = re.search(r'(?m)^version\s*=\s*"([^"]+)"', declared)
    assert found, "pyproject.toml has no version"
    assert nv._VERSION.match(found.group(1)), "the declared version is not MAJOR.MINOR.PATCH"
