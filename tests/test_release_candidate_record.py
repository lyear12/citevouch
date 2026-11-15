"""The release has to say which commit produced which bytes, and prove it.

Two things had no durable answer before this file. A person downloading a wheel
could learn the tag and nothing else: not the commit that built it, not the
digests of the other files in the same release, not whether the file in their
hand was still the file that was published. And a resumed release could only
*assume* the rebuild was the same build - the digest guard added in v0.24.5
would stop a different build, but nothing said what the same build was.

`tools/release_candidate.py` writes that down into `dist/release-candidate.json`,
so the record is uploaded with the artefacts it describes, and `check`
recomputes every digest from whatever directory it is pointed at. The workflow
runs `check` against a directory it has just downloaded from the release, which
is the only place in the pipeline where the published thing is read back.

The determinism is load-bearing rather than tidy: a record carrying a timestamp
or a set iteration order would differ between two honest runs of the same tag,
and the digest guard in the recovery step would then refuse the second run's
record. Sorted keys and sorted artefacts make an honest resume byte-identical,
so the guard's refusal means what it says.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
TOOL = REPO / "tools" / "release_candidate.py"
WORKFLOW = REPO / ".github" / "workflows" / "release.yml"

sys.path.insert(0, str(REPO / "tools"))
import release_candidate  # noqa: E402  (path set just above)


def _artefacts(
    dist: Path, wheel: bytes = b"wheel bytes\n", sdist: bytes = b"sdist bytes\n"
) -> None:
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "citevouch-9.9.9-py3-none-any.whl").write_bytes(wheel)
    (dist / "citevouch-9.9.9.tar.gz").write_bytes(sdist)


def _record(dist: Path, **overrides: str) -> Path:
    fields = {
        "version": "9.9.9",
        "tag": "v9.9.9",
        "candidate": "b" * 40,
        "source_sha": "b" * 40,
        "release_sha": "c" * 40,
    }
    fields.update(overrides)
    return release_candidate.write(dist, **fields)


def _run(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), *argv],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


class TestTheRecordSaysWhatBuiltWhat:
    def test_it_names_the_files_and_their_digests(self, tmp_path: Path) -> None:
        _artefacts(tmp_path / "dist")
        _record(tmp_path / "dist")
        payload = json.loads((tmp_path / "dist" / "release-candidate.json").read_text("utf-8"))
        names = [entry["name"] for entry in payload["artifacts"]]
        assert names == sorted(names)
        assert "citevouch-9.9.9-py3-none-any.whl" in names
        assert payload["release_sha"] == "c" * 40
        assert payload["version"] == "9.9.9"

    def test_the_digest_is_the_bytes(self, tmp_path: Path) -> None:
        _artefacts(tmp_path / "dist")
        _record(tmp_path / "dist")
        payload = json.loads((tmp_path / "dist" / "release-candidate.json").read_text("utf-8"))
        entry = next(e for e in payload["artifacts"] if e["name"].endswith(".whl"))
        assert entry["sha256"] == release_candidate.digest_of(tmp_path / "dist" / entry["name"])
        assert entry["size"] == (tmp_path / "dist" / entry["name"]).stat().st_size

    def test_the_record_does_not_describe_itself(self, tmp_path: Path) -> None:
        # It cannot: writing its own digest into itself changes the digest. The
        # absence is explicit, not an oversight, and `check` demands the file
        # separately.
        _artefacts(tmp_path / "dist")
        _record(tmp_path / "dist")
        payload = json.loads((tmp_path / "dist" / "release-candidate.json").read_text("utf-8"))
        assert all(entry["name"] != release_candidate.RECORD for entry in payload["artifacts"])

    def test_a_second_run_does_not_start_describing_the_record(self, tmp_path: Path) -> None:
        # The record cannot contain its own digest: writing one changes it. The
        # first run is trivially safe because the file does not exist yet, so
        # the interesting case is a re-run over an existing `dist/` - the resumed
        # release this whole task is about.
        _artefacts(tmp_path / "dist")
        _record(tmp_path / "dist")
        _record(tmp_path / "dist")
        payload = json.loads((tmp_path / "dist" / release_candidate.RECORD).read_text("utf-8"))
        assert [entry["name"] for entry in payload["artifacts"]] == [
            "citevouch-9.9.9-py3-none-any.whl",
            "citevouch-9.9.9.tar.gz",
        ]
        assert release_candidate.check(tmp_path / "dist") == []

    def test_two_honest_runs_of_one_tag_write_the_same_bytes(self, tmp_path: Path) -> None:
        # This is why the recovery step's digest guard can refuse a second
        # record: an honest resume produces the same one.
        first = tmp_path / "first"
        second = tmp_path / "second"
        _artefacts(first)
        _artefacts(second)
        _record(first)
        _record(second)
        assert (first / release_candidate.RECORD).read_bytes() == (
            second / release_candidate.RECORD
        ).read_bytes()


class TestACheckRecomputesRatherThanTrusts:
    def test_an_intact_directory_passes(self, tmp_path: Path) -> None:
        _artefacts(tmp_path / "dist")
        _record(tmp_path / "dist")
        assert release_candidate.check(tmp_path / "dist") == []

    def test_a_changed_byte_is_reported_with_both_digests(self, tmp_path: Path) -> None:
        # Same length, different content: the size check cannot speak here, so
        # a single sentence about the digest is what an honest report looks
        # like. The truncated-file case below covers the other complaint.
        _artefacts(tmp_path / "dist")
        _record(tmp_path / "dist")
        (tmp_path / "dist" / "citevouch-9.9.9.tar.gz").write_bytes(b"SDIST BYTES\n")
        problems = release_candidate.check(tmp_path / "dist")
        assert len(problems) == 1, problems
        assert "citevouch-9.9.9.tar.gz" in problems[0]
        assert "the record says" in problems[0]

    def test_a_missing_file_is_named(self, tmp_path: Path) -> None:
        _artefacts(tmp_path / "dist")
        _record(tmp_path / "dist")
        (tmp_path / "dist" / "citevouch-9.9.9.tar.gz").unlink()
        problems = release_candidate.check(tmp_path / "dist")
        assert any("which is not here" in problem for problem in problems)

    def test_an_unrecorded_file_is_named(self, tmp_path: Path) -> None:
        # The dangerous direction: an extra asset that no record vouches for
        # would otherwise ride along in a release whose paperwork looks complete.
        _artefacts(tmp_path / "dist")
        _record(tmp_path / "dist")
        (tmp_path / "dist" / "extra.bin").write_bytes(b"nobody recorded me")
        problems = release_candidate.check(tmp_path / "dist")
        assert len(problems) == 1
        assert "extra.bin" in problems[0]

    def test_a_truncated_file_fails_on_size_too(self, tmp_path: Path) -> None:
        _artefacts(tmp_path / "dist")
        _record(tmp_path / "dist")
        path = tmp_path / "dist" / "citevouch-9.9.9-py3-none-any.whl"
        path.write_bytes(b"short")
        problems = release_candidate.check(tmp_path / "dist")
        assert any("bytes but the record says" in problem for problem in problems)


class TestARecordThatDoesNotSayWhatItIsIsRefused:
    def test_a_missing_record_is_refused(self, tmp_path: Path) -> None:
        _artefacts(tmp_path / "dist")
        with pytest.raises(SystemExit) as raised:
            release_candidate.check(tmp_path / "dist")
        assert "carries no record of what built it" in str(raised.value)

    def test_unreadable_json_is_refused(self, tmp_path: Path) -> None:
        _artefacts(tmp_path / "dist")
        (tmp_path / "dist" / release_candidate.RECORD).write_text("{not json", encoding="utf-8")
        with pytest.raises(SystemExit) as raised:
            release_candidate.check(tmp_path / "dist")
        assert "not readable JSON" in str(raised.value)

    def test_a_missing_field_is_named(self, tmp_path: Path) -> None:
        _artefacts(tmp_path / "dist")
        _record(tmp_path / "dist")
        path = tmp_path / "dist" / release_candidate.RECORD
        payload = json.loads(path.read_text("utf-8"))
        del payload["release_sha"]
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(SystemExit) as raised:
            release_candidate.check(tmp_path / "dist")
        assert "release_sha" in str(raised.value)

    def test_an_unknown_schema_is_refused(self, tmp_path: Path) -> None:
        _artefacts(tmp_path / "dist")
        _record(tmp_path / "dist")
        path = tmp_path / "dist" / release_candidate.RECORD
        payload = json.loads(path.read_text("utf-8"))
        payload["schema"] = 99
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(SystemExit) as raised:
            release_candidate.check(tmp_path / "dist")
        assert "schema 99" in str(raised.value)


class TestTheCommandLineSaysItToo:
    def test_check_reports_the_identity_on_success(self, tmp_path: Path) -> None:
        _artefacts(tmp_path / "dist")
        _record(tmp_path / "dist")
        done = _run("check", str(tmp_path / "dist"))
        assert done.returncode == 0, done.stderr
        assert "9.9.9" in done.stdout
        assert "2 artefact(s)" in done.stdout

    def test_check_exits_one_and_writes_a_github_error_on_a_mismatch(
        self, tmp_path: Path
    ) -> None:
        _artefacts(tmp_path / "dist")
        _record(tmp_path / "dist")
        (tmp_path / "dist" / "citevouch-9.9.9.tar.gz").write_bytes(b"different\n")
        done = _run("check", str(tmp_path / "dist"))
        assert done.returncode == 1
        assert "::error::" in done.stdout

    def test_show_prints_one_field(self, tmp_path: Path) -> None:
        _artefacts(tmp_path / "dist")
        _record(tmp_path / "dist")
        done = _run("show", str(tmp_path / "dist"), "release_sha")
        assert done.returncode == 0
        assert done.stdout.strip() == "c" * 40

    def test_write_says_what_it_recorded(self, tmp_path: Path) -> None:
        _artefacts(tmp_path / "dist")
        done = _run(
            "write",
            str(tmp_path / "dist"),
            "--version",
            "9.9.9",
            "--tag",
            "v9.9.9",
            "--candidate",
            "b" * 40,
            "--source-sha",
            "b" * 40,
            "--release-sha",
            "c" * 40,
        )
        assert done.returncode == 0, done.stderr
        assert "sha256:" in done.stdout
        assert "recorded 2 artefact(s)" in done.stdout


class TestTheWorkflowUsesIt:
    def _steps(self) -> list[dict]:
        import yaml

        data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        return data["jobs"]["release"]["steps"]

    def _named(self, name: str) -> dict:
        for step in self._steps():
            if step.get("name") == name:
                return step
        raise AssertionError(f"no step named {name!r}")

    def test_the_record_is_written_after_the_build_and_before_smoke_test(self) -> None:
        names = [step.get("name") for step in self._steps()]
        build = names.index("Build")
        record = names.index("Record which commit produced these bytes")
        smoke = names.index("Smoke-test the built wheel in a clean directory")
        assert build < record < smoke

    def test_neither_new_step_is_conditional(self) -> None:
        # `if:` on either step would make the record optional or the retrieval
        # check optional, and an optional proof is not a proof. This catches the
        # shape a careless edit takes: adding a condition to quiet a failure.
        for name in (
            "Record which commit produced these bytes",
            "Fetch the published assets back and check them against the record",
        ):
            assert "if" not in self._named(name), name

    def test_the_record_carries_the_three_commits_and_the_version(self) -> None:
        body = self._named("Record which commit produced these bytes")["run"]
        for token in ("--version", "--tag", "--candidate", "--source-sha", "--release-sha"):
            assert token in body, token
        assert "steps.tree.outputs.source_sha" in body

    def test_a_tag_push_falls_back_to_the_tree_it_releases(self) -> None:
        # `steps.tree` writes its outputs only on the candidate path. An empty
        # `source_sha` must not reach the record, where it would read as a fact
        # that is missing rather than a fact that does not apply.
        body = self._named("Record which commit produced these bytes")["run"]
        assert 'if [ -z "$source_sha" ]' in body
        assert 'source_sha="$release_sha"' in body

    def test_the_published_assets_are_downloaded_and_checked(self) -> None:
        body = self._named("Fetch the published assets back and check them against the record")[
            "run"
        ]
        assert "gh release download" in body
        assert "release_candidate.py check retrieved" in body

    def test_the_check_runs_after_the_upload(self) -> None:
        names = [step.get("name") for step in self._steps()]
        recovery = names.index("Re-attach artefacts if the release already existed")
        check = names.index("Fetch the published assets back and check them against the record")
        assert recovery < check
