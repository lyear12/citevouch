"""The five fields a human types into PyPI have to still describe this repo.

`docs/maintenance.md` tells the owner what to enter on pypi.org for the trusted
publisher, and names two facts about the workflow that make the entry work:
`release.yml` grants `id-token: write`, and its publish step pins no
`environment:`.  Both are true today and neither is checked by anything.  The
day someone adds `environment: release` to the job for tidiness, the documented
fields become wrong in a way that produces a *failed publish* rather than a
skipped one - and the person reading the failure has just done the account
action and has no reason to suspect the file it is talking about.

The rest of this repository removes that class of defect by making the claim
and the fact the same thing; this does the same for the one step no test can
perform.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
MAINTENANCE = ROOT / "docs" / "maintenance.md"


def _workflow() -> dict:
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(RELEASE.read_text(encoding="utf-8"))


def _publish_step() -> dict:
    for job in _workflow()["jobs"].values():
        for step in job.get("steps", []):
            if "pypi" in str(step.get("uses", "")).lower():
                return step
    raise AssertionError("release.yml has no PyPI publish step")


def _documented_fields() -> dict[str, str]:
    """The table in maintenance.md: `| field | value |` rows, in order.

    The table sits indented inside a numbered list, so each row is stripped of
    its leading whitespace before the pipe test.  Reading only unindented rows
    collected the header and stopped, which would have made every value
    assertion below silently skip its subject.
    """
    text = MAINTENANCE.read_text(encoding="utf-8")
    start = text.index("| PyPI Project Name |")
    rows: dict[str, str] = {}
    for line in text[start:].splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            break
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) == 2 and cells[0] and not set(cells[0]) <= set("-: "):
            rows[cells[0]] = cells[1]
    return rows


class TestTheWorkflowGrantsWhatThePublisherNeeds:
    def test_the_workflow_asks_for_an_oidc_token(self) -> None:
        permissions = _workflow().get("permissions") or {}
        assert permissions.get("id-token") == "write", (
            "a trusted publisher is authenticated by the OIDC token; without "
            f"`permissions: id-token: write` the publish cannot be authorised: {permissions!r}"
        )

    def test_the_job_pins_no_environment(self) -> None:
        for name, job in _workflow()["jobs"].items():
            assert "environment" not in job, (
                f"job {name!r} names an environment; PYPY's trusted publisher "
                "form tells the owner to leave the environment field empty, and "
                "a job that pins one here makes the OIDC subject disagree - the "
                "publish fails instead of being skipped"
            )

    def test_the_publish_step_pins_no_environment(self) -> None:
        assert "environment" not in _publish_step()


class TestTheDocumentedFieldsStillDescribeThisRepository:
    def test_the_project_name_matches_the_package(self) -> None:
        package = re.search(
            r'^name\s*=\s*"([^"]+)"',
            (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
            re.M,
        )
        assert package is not None, "pyproject.toml has no name"
        assert _documented_fields()["PyPI Project Name"].strip("`") == package.group(1), (
            "the trusted publisher is registered against a project name; if the "
            "package is renamed, the documented form registers it against the "
            "wrong one"
        )

    def test_the_owner_and_repository_match_the_project_urls(self) -> None:
        urls = re.search(
            r'^Homepage\s*=\s*"https://github\.com/([^/]+)/([^"/]+)"',
            (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
            re.M,
        )
        assert urls is not None, "pyproject.toml has no GitHub Homepage"
        fields = _documented_fields()
        assert fields["Owner"].strip("`") == urls.group(1)
        assert fields["Repository name"].strip("`") == urls.group(2)

    def test_the_documented_workflow_is_the_one_that_publishes(self) -> None:
        assert _documented_fields()["Workflow name"].strip("`") == RELEASE.name

    def test_the_environment_field_is_documented_as_empty(self) -> None:
        value = _documented_fields()["Environment name"]
        assert "empty" in value.lower(), (
            f"the environment field tells the owner to enter {value!r}; the form "
            "must stay empty while the job pins none"
        )


class TestTheDocsSayWhatToDoAndWhatItProves:
    def test_the_click_path_names_a_verification_that_does_not_need_a_release(self) -> None:
        text = MAINTENANCE.read_text(encoding="utf-8")
        start = text.index("| PyPI Project Name |")
        section = text[start : start + 2000]
        assert "pypi.org/pypi/citevouch/json" in section, (
            "the section has to carry the command that answers 'did it work' "
            "without cutting a release, or the owner has to guess"
        )

    def test_the_verification_says_what_both_answers_mean(self) -> None:
        """Both status codes, each on a console line, not merely mentioned.

        The first version of this test asked whether ``404`` and ``200`` appear
        anywhere in the section, and a paragraph below the code block explains
        that ``404`` is not a failure - so deleting the ``404`` line from the
        output still passed.  A guard that accepts the word wherever it is is
        not measuring the code block.
        """
        text = MAINTENANCE.read_text(encoding="utf-8")
        start = text.index("| PyPI Project Name |")
        section = text[start : start + 2000]
        console = section[
            section.index("```console") : section.index("```", section.index("```console") + 3)
        ]
        for code in ("404", "200"):
            assert any(line.strip().startswith(code) for line in console.splitlines()), (
                f"the console block does not show a {code} line: {console!r}"
            )
