"""CV-009: the publish workflow, and the three outcomes it must tell apart.

The defect this guards is not a crash.  `docs/maintenance.md` used to tell the
Owner to register `release.yml` as the trusted publisher, and PyPI cannot accept
that name: it refuses reusable workflows outright, and `release.yml` is only
ever reached through `workflow_call`.  Run 43395199793 measured the consequence:

    workflow_ref     = .../auto-release.yml@refs/heads/main
    job_workflow_ref = .../release.yml@refs/heads/main
    invalid-publisher: valid token, but no corresponding publisher

So the one account action the project asks of a human was pointing at a file that
could never work, and nothing in the repository noticed, because the old test
compared two strings that both said `release.yml`.

These tests hold four things: that the workflow which publishes is one PyPI can
register, that it uploads the bytes the release already recorded, that its
summary separates the failures that need different repairs, and that the
documented form names the file that is actually triggered.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
PUBLISH = WORKFLOWS / "publish.yml"
RELEASE = WORKFLOWS / "release.yml"
AUTO = WORKFLOWS / "auto-release.yml"
MAINTENANCE = ROOT / "docs" / "maintenance.md"


def _yaml() -> object:
    return pytest.importorskip("yaml")


def _load(path: Path) -> dict:
    return _yaml().safe_load(path.read_text(encoding="utf-8"))


def _steps(path: Path) -> list[dict]:
    data = _load(path)
    steps: list[dict] = []
    for job in data["jobs"].values():
        steps.extend(job.get("steps", []))
    return steps


def _step(name_prefix: str) -> dict:
    for step in _steps(PUBLISH):
        if str(step.get("name", "")).startswith(name_prefix):
            return step
    raise AssertionError(f"publish.yml has no step starting with {name_prefix!r}")


def _triggers() -> dict:
    data = _load(PUBLISH)
    # PyYAML reads a bare `on:` as the boolean True.
    return data.get("on", data.get(True)) or {}


def _documented_fields() -> dict[str, str]:
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


def _bash() -> str:
    for candidate in (
        shutil.which("bash"),
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        "/bin/bash",
        "/usr/bin/bash",
    ):
        if candidate and Path(candidate).is_file():
            return candidate
    pytest.fail("no bash on this machine, so no step body could be run")


def _run_step(
    step_name: str, tmp_path: Path, *, tag: str = "", inputs_tag: str = ""
) -> tuple[int, str]:
    """Run one step's shell body with the GitHub expressions substituted.

    A step body is the only place the behaviour lives; asserting on YAML keys
    would pass while the script did the opposite.
    """
    body = _step(step_name)["run"]
    body = body.replace("${{ inputs.tag }}", inputs_tag)
    body = body.replace("${{ github.event.workflow_run.head_branch }}", tag)
    body = body.replace("${{ steps.v.outputs.tag }}", "v9.9.9")
    body = body.replace("${{ steps.v.outputs.version }}", "9.9.9")
    body = body.replace("${{ steps.pypi.outcome }}", "success")
    script = tmp_path / "step.sh"
    script.write_text(body, encoding="utf-8", newline=chr(10))
    outputs = tmp_path / "outputs.txt"
    summary = tmp_path / "summary.md"
    env = {
        **os.environ,
        "GITHUB_OUTPUT": str(outputs),
        "GITHUB_STEP_SUMMARY": str(summary),
        "PYTHONIOENCODING": "utf-8",
    }
    done = subprocess.run(
        [_bash(), str(script)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    printed = done.stdout + done.stderr
    if summary.is_file():
        printed += summary.read_text(encoding="utf-8")
    return done.returncode, printed


class TestThePublisherIsAWorkflowPyPIWillAccept:
    def test_the_publishing_workflow_is_never_called_by_another(self) -> None:
        for other in WORKFLOWS.glob("*.yml"):
            text = other.read_text(encoding="utf-8")
            if other == PUBLISH:
                continue
            assert "./.github/workflows/publish.yml" not in text, (
                f"{other.name} calls publish.yml; a reusable workflow cannot be a "
                "trusted publisher, which is the whole reason publish.yml exists"
            )
            assert "publish.yml" not in text or other.name in {
                "release.yml",
                "auto-release.yml",
            }, f"{other.name} references publish.yml in a way this test does not expect"

    def test_nothing_in_release_yml_still_publishes(self) -> None:
        for step in _steps(RELEASE):
            assert "pypi-publish" not in str(step.get("uses", "")), (
                "release.yml still publishes to PyPI; it is reached through "
                "workflow_call, so that upload can never be registered"
            )
        assert "id-token" not in (_load(RELEASE).get("permissions") or {}), (
            "release.yml still asks for an OIDC token it has no use for; the "
            "permission is what made the old arrangement look possible"
        )

    def test_the_publish_workflow_asks_for_an_oidc_token_and_nothing_else(self) -> None:
        permissions = _load(PUBLISH).get("permissions") or {}
        assert permissions.get("id-token") == "write", (
            "a trusted publisher is authenticated by the OIDC token; without "
            f"`permissions: id-token: write` the upload cannot be authorised: {permissions!r}"
        )
        assert permissions.get("contents") == "read", (
            "publishing reads a release; writing to the repository is not part of it"
        )

    def test_no_job_pins_an_environment(self) -> None:
        for name, job in _load(PUBLISH)["jobs"].items():
            assert "environment" not in job, (
                f"job {name!r} names an environment; the trusted publisher form "
                "tells the Owner to leave that field empty, and a job that pins "
                "one here makes the OIDC subject disagree - the upload fails "
                "instead of being skipped"
            )

    def test_the_workflow_can_be_started_without_the_automatic_trigger(self) -> None:
        triggers = _triggers()
        assert "workflow_dispatch" in triggers, (
            "a GITHUB_TOKEN push does not start a workflow, and whether "
            "workflow_run survives that suppression is unproven here; without a "
            "manual door the Owner has no path that does not depend on the answer"
        )
        tag = triggers["workflow_dispatch"]["inputs"]["tag"]
        assert tag["required"] is True, "a manual publish must name the tag it publishes"

    def test_the_concurrency_group_is_the_same_one_the_release_uses(self) -> None:
        publish = _load(PUBLISH)["concurrency"]
        release = _load(RELEASE)["concurrency"]
        assert publish["group"] == release["group"], (
            "two uploads of the same version race on an immutable index; the "
            "loser's failure is indistinguishable from a real defect"
        )
        assert publish["cancel-in-progress"] is False


class TestItUploadsWhatTheReleaseRecorded:
    def test_the_bytes_are_checked_before_the_upload(self) -> None:
        names = [str(step.get("name", "")) for step in _steps(PUBLISH)]
        check = next(i for i, n in enumerate(names) if "must be the bytes" in n)
        upload = next(i for i, n in enumerate(names) if "Publish to PyPI" in n)
        assert check < upload, "the digest check has to run before the upload, not after"

    def test_the_check_is_the_candidate_record_tool(self) -> None:
        body = _step("The bytes about to be uploaded")["run"]
        assert "release_candidate.py check" in body, (
            "recomputing the digests is the only thing that makes the uploaded "
            "bytes the built bytes"
        )

    def test_the_assets_come_from_the_release_and_not_from_a_rebuild(self) -> None:
        body = _step("Download the assets")["run"]
        assert "gh release download" in body
        assert "build" not in body.split("gh release download")[0], (
            "nothing may be built here; a rebuild is a different set of bytes"
        )

    def test_a_release_without_assets_fails_loudly(self) -> None:
        code, printed = _run_step("Download the assets", _fake_path())
        assert code != 0
        assert "has no release assets to publish" in printed

    def test_the_upload_is_not_allowed_to_fail_quietly(self) -> None:
        step = _step("Publish to PyPI")
        assert "continue-on-error" not in step, (
            "this workflow exists only to publish; a swallowed failure here is "
            "an output-free run that looks like success"
        )
        assert step["with"]["packages-dir"] == "dist"


class TestTheThreeOutcomesAreDistinguishable:
    def test_a_successful_run_says_published_and_names_the_check(self) -> None:
        code, printed = _run_step("Summarise", _fake_path())
        assert code == 0
        assert "Published `9.9.9` to PyPI." in printed
        assert "pypi.org/pypi/citevouch/json" in printed

    def test_a_bad_publisher_and_a_bad_token_are_told_apart(self) -> None:
        body = _step("Summarise")["run"]
        assert "invalid-publisher" in body, (
            "the most likely failure is a form that does not match this "
            "workflow; the summary has to say so"
        )
        assert "invalid-payload" in body and "invalid-token" in body, (
            "a failed token exchange is a different repair from a mismatched "
            "form, and the summary must not merge them"
        )
        assert "publish.yml" in body and "lyear12/citevouch" in body, (
            "the form values belong in the summary; the person reading it has "
            "just done the account action"
        )

    def test_the_summary_explains_that_the_release_still_installs(self) -> None:
        body = _step("Summarise")["run"]
        assert "GitHub release still carries" in body, (
            "a failed publish is not a failed release; saying so prevents the "
            "Owner from re-cutting a tag that is already correct"
        )


class TestTheTagIsResolvedRatherThanAssumed:
    def test_a_manual_publish_takes_the_tag_it_is_given(self) -> None:
        path = _fake_path()
        code, _printed = _run_step("Resolve the tag", path, inputs_tag="v9.9.9")
        assert code == 0
        assert "tag=v9.9.9" in (path / "outputs.txt").read_text(encoding="utf-8")

    def test_a_branch_name_is_not_a_tag(self) -> None:
        code, printed = _run_step("Resolve the tag", _fake_path(), inputs_tag="main")
        assert code != 0
        assert "could not resolve a v-prefixed tag" in printed

    def test_an_empty_tag_is_refused(self) -> None:
        code, printed = _run_step("Resolve the tag", _fake_path())
        assert code != 0
        assert "could not resolve a v-prefixed tag" in printed

    def test_the_version_drops_the_v(self) -> None:
        path = _fake_path()
        _run_step("Resolve the tag", path, inputs_tag="v1.2.3")
        written = (path / "outputs.txt").read_text(encoding="utf-8")
        assert "version=1.2.3" in written


class TestTheDocumentedFormNamesTheFileThatRuns:
    def test_the_documented_workflow_is_the_triggered_one(self) -> None:
        documented = _documented_fields()["Workflow name"].strip("`")
        assert documented == PUBLISH.name, (
            f"maintenance.md tells the Owner to register {documented!r}; the file "
            "that is actually triggered is publish.yml, and registering a "
            "called workflow produces invalid-publisher no matter what is typed"
        )

    def test_the_page_says_why_the_old_name_could_not_work(self) -> None:
        text = MAINTENANCE.read_text(encoding="utf-8")
        assert "Reusable workflows cannot currently be used" in text, (
            "the page quotes PyPI's own rule; without it the next reader will "
            "'tidy' the publish step back into release.yml"
        )
        assert "warehouse#11096" in text
        assert "job_workflow_ref" in text and "workflow_ref" in text

    def test_the_page_offers_the_door_that_does_not_depend_on_an_unproven_trigger(self) -> None:
        text = MAINTENANCE.read_text(encoding="utf-8")
        assert "gh workflow run publish.yml -f tag=v" in text, (
            "workflow_run firing after a GITHUB_TOKEN release is unproven here; "
            "the page has to give the command that works regardless"
        )

    def test_the_page_does_not_claim_the_automatic_trigger_is_proven(self) -> None:
        text = MAINTENANCE.read_text(encoding="utf-8")
        # The sentence carries Markdown emphasis around "not", so the mark
        # characters have to go before the words can be compared.
        flat = " ".join(text.replace("*", "").split())
        assert "not verified by anything in this repository" in flat or (
            "not verified" in flat and "workflow_run" in flat
        ), (
            "if the trigger were proven, this sentence would be stale; while it "
            "is not, silence here reads as a promise"
        )


def _fake_path() -> Path:
    """A scratch directory shaped like GH_OUTPUT/GH_SUMMARY need."""
    import tempfile

    return Path(tempfile.mkdtemp())
