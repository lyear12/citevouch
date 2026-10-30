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

    found = _declared_version(repo)
    assert nv._VERSION.match(found), "the declared version is not MAJOR.MINOR.PATCH"


# --------------------------------------------------------------------------
# Keeping install pins in documents honest


def test_set_doc_pins_moves_every_pin():
    text = (
        'pip install "git+https://github.com/lyear12/citevouch@v0.1.0"\n'
        '- run: pip install "git+https://github.com/lyear12/citevouch@v0.1.0"\n'
    )
    out, count = nv.set_doc_pins(text, "0.3.1")
    assert count == 2
    assert "@v0.3.1" in out
    assert "@v0.1.0" not in out


def test_set_doc_pins_ignores_text_that_is_not_a_pin():
    """A version mentioned in prose stays prose."""
    text = "`0.2.0` is the first schema-affecting change; citevouch 0.1 is fine too.\n"
    out, count = nv.set_doc_pins(text, "0.3.0")
    assert count == 0
    assert out == text


def test_cli_readme_flag_rewrites_the_document(tmp_path):
    changelog_path = tmp_path / "CHANGELOG.md"
    changelog_path.write_text(changelog("### Fixed\n\n- x\n"), encoding="utf-8")
    readme = tmp_path / "README.md"
    readme.write_text("pip install .../citevouch@v0.9.9\n", encoding="utf-8")

    assert (
        nv.main(
            [
                str(changelog_path),
                "--current",
                "0.9.9",
                "--apply",
                "--readme",
                str(readme),
                "--date",
                "2026-11-01",
            ]
        )
        == 0
    )
    assert "citevouch@v0.9.10" in readme.read_text(encoding="utf-8")


def test_cli_readme_flag_is_optional_and_unkind_to_no_pins(tmp_path):
    changelog_path = tmp_path / "CHANGELOG.md"
    changelog_path.write_text(changelog("### Fixed\n\n- x\n"), encoding="utf-8")
    readme = tmp_path / "README.md"
    readme.write_text("pip install citevouch\n", encoding="utf-8")
    assert (
        nv.main(
            [
                str(changelog_path),
                "--current",
                "0.1.0",
                "--apply",
                "--readme",
                str(readme),
                "--date",
                "2026-11-01",
            ]
        )
        == 0
    )
    assert readme.read_text(encoding="utf-8") == "pip install citevouch\n"


# --------------------------------------------------------------------------
# The changelog's own link block stays true to its headings


def test_update_links_rebuilds_the_block_from_the_headings():
    text = (
        "# Changelog\n\n## [Unreleased]\n\n## [0.3.0] - x\n\nbody\n\n"
        "[Unreleased]: old/compare/v0.1.0...HEAD\n[0.1.0]: old/tag/v0.1.0\n"
    )
    out = nv.update_links(text, "0.3.0")
    assert "[Unreleased]: https://github.com/lyear12/citevouch/compare/v0.3.0...HEAD" in out
    assert "[0.3.0]: https://github.com/lyear12/citevouch/releases/tag/v0.3.0" in out
    assert "old/" not in out


def test_update_links_adds_a_block_when_there_is_none():
    out = nv.update_links("# Changelog\n\n## [0.1.0] - x\n\nbody\n", "0.1.0")
    assert out.rstrip().endswith(
        "[0.1.0]: https://github.com/lyear12/citevouch/releases/tag/v0.1.0"
    )
    assert "[Unreleased]: " in out


def test_update_links_keeps_every_released_heading_linked():
    text = (
        "## [Unreleased]\n\n## [0.2.1] - a\n\n## [0.2.0] - b\n\n## [0.1.0] - c\n\n"
        "body\n\n[Unreleased]: x\n"
    )
    out = nv.update_links(text, "0.2.1")
    for v in ("0.2.1", "0.2.0", "0.1.0"):
        assert f"[{v}]: " in out


def test_apply_keeps_links_consistent_on_a_real_shaped_changelog(tmp_path):
    """The promise a release makes: after --apply, every release heading has a
    link and the Unreleased comparison names the version just released.

    This test started life reading the repository's real CHANGELOG.md and
    computing its next version - and then asserted a patch bump while the file
    legitimately held an `Added`, so the moment the repository had something
    new to release, the test that checked the release machinery broke CI on
    every OS at once (run 40842840982, red on all three OSes for the same
    reason). A test that reads a file the release is about to change is a race
    with the repository itself; the synthetic file below has the same shape -
    stale link block, real-looking headings - and belongs to no one else.
    """
    source = (
        "# Changelog\n"
        "\n"
        "prose mentioning `## [Unreleased]` in backticks before the heading.\n"
        "\n"
        "## [Unreleased]\n"
        "\n"
        "### Fixed\n"
        "\n"
        "- Something that was wrong.\n"
        "\n"
        "## [0.4.1] - 2026-10-01\n"
        "\n"
        "- earlier work\n"
        "\n"
        "## [0.4.0] - 2026-09-01\n"
        "\n"
        "- older work\n"
        "\n"
        "[Unreleased]: https://example.invalid/compare/v0.1.0...HEAD\n"
        "[0.1.0]: https://example.invalid/releases/tag/v0.1.0\n"
    )
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(source, encoding="utf-8")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "0.4.1"\n', encoding="utf-8")

    assert (
        nv.main(
            [
                str(changelog),
                "--current",
                "0.4.1",
                "--apply",
                "--pyproject",
                str(pyproject),
                "--date",
                "2026-11-01",
            ]
        )
        == 0
    )
    out = changelog.read_text(encoding="utf-8")
    assert "## [0.4.2] — 2026-11-01" in out  # Fixed-only -> patch
    links = out[out.index("[Unreleased]:") :]
    assert "[Unreleased]: https://github.com/lyear12/citevouch/compare/v0.4.2...HEAD" in links
    for version in ("0.4.2", "0.4.1", "0.4.0"):
        assert (
            f"[{version}]: https://github.com/lyear12/citevouch/releases/tag/v{version}"
            in links
        )
    assert "example.invalid" not in links  # the stale block is gone, not amended


def _declared_version(repo: Path) -> str:
    """The version this checkout would build, read the way setuptools reads it.

    Added when the declaration moved out of ``pyproject.toml``: a test that
    greps a file for ``version = "..."`` stops testing anything the moment the
    file stops having one, and these two tests read the real repository. They
    now ask the package itself, which is the same attribute
    ``[tool.setuptools.dynamic]`` names.
    """
    import sys

    sys.path.insert(0, str(repo / "src"))
    from citevouch._version import __version__

    return __version__


def test_the_repository_changelog_and_pyproject_stay_consistent():
    """A guard on the real files that cannot break when they change: the
    declared version must name a release heading that exists in CHANGELOG.md,
    and the link block must carry a link for it. True before and after every
    release, because both halves move together by construction of `--apply`."""
    repo = Path(__file__).resolve().parent.parent
    declared = _declared_version(repo)
    text = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{declared}]" in text, f"{declared} is declared but not in the changelog"
    assert f"[{declared}]: {nv.REPO_URL}/releases/tag/v{declared}" in text
