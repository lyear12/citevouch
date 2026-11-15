# Protecting `main`: what the settings are today, and what should change

**Status: a proposal waiting for one Owner decision.** Nothing in this document
has been applied. This file records what the repository actually enforces today,
what the two honest options are, and what each one costs. The decision itself is
not an engineering decision, because every option either lets the tool publish
without a human or requires a second human account to exist.

## What is true today, measured

The three facts below were read from the GitHub API on 2026-11-15, not inferred
from files in this repository. A `CODEOWNERS` file or a pull-request template
would say nothing about enforcement; these calls do.

```text
$ gh api repos/lyear12/citevouch/branches/main --jq '{name,protected,protection}'
{"name":"main","protected":false,"protection":{"enabled":false,
 "required_status_checks":{"checks":[],"contexts":[],"enforcement_level":"off"}}}

$ gh api repos/lyear12/citevouch/branches/main/protection
{"message":"Branch not protected", ... "status":"404"}

$ gh api repos/lyear12/citevouch/rulesets
[]

$ gh api repos/lyear12/citevouch/collaborators --jq 'length'
1
```

So: `main` accepts a direct push from any collaborator, with no status check, no
review and no force-push restriction, and there is exactly one collaborator (the
Owner, with `admin`). Everything this project says about "CI gates the release"
is enforced by the *workflow*, not by the branch: `Test` runs after the push, and
`auto-release` decides whether to publish. A bad commit reaches `main` first and
is graded afterwards.

That matters for one specific reason: `auto-release.yml` publishes a tag *after*
CI is green, so the sequence today is "push, then find out". If a red commit is
force-pushed over before the run finishes, nothing anywhere records that it
happened.

## The eleven checks that exist

A required status check has to name a job that actually reports. The `Test`
workflow currently reports these eleven, measured from run `43716789622`:

| job name | what it covers |
| --- | --- |
| `lint` | full suite, `ruff check`, `ruff format --check`, repository rules |
| `acceptance (the documented first run)` | the documented first run, offline, from a clean tree |
| `sdist (the archive as published, unpacked and tested)` | the sdist's own suite, outside the checkout |
| `test (ubuntu-latest, 3.10)` | the matrix cell with the oldest interpreter this project supports |
| `test (ubuntu-latest, 3.12)` | |
| `test (ubuntu-latest, 3.13)` | |
| `test (windows-latest, 3.10)` | |
| `test (windows-latest, 3.12)` | |
| `test (windows-latest, 3.13)` | |
| `test (macos-latest, 3.12)` | |
| `test (macos-latest, 3.13)` | |

(MacOS 3.10 is deliberately absent: `macos-latest` is arm64 and no CPython 3.10
build exists for it, so that cell is excluded in `test.yml` rather than left to
fail forever.)

**Do not require all eleven by name.** Two of them are structural rather than
substantive: `acceptance` and `sdist` re-run the same suite the matrix already
ran, and a required check that duplicates another one doubles the cost of every
red run while telling nobody anything new. The three that answer questions
nothing else can are:

1. `lint` - it is the only job that runs `ruff` and the repository rules.
2. `test (ubuntu-latest, 3.10)` - the oldest supported interpreter; `tomllib`,
   `match`, `X | Y` annotations and `str.removeprefix` all break here first.
3. `test (windows-latest, 3.12)` - the platform where this project's actual bugs
   live: CRLF, subprocess encoding, `PermissionError` on read-only files.

Requiring those three is the smallest set that would have caught the real
regressions this project has had. Requiring the rest is defensible; requiring
none is what happens today.

## Alternative A - require status checks only

Settings: branch protection on `main` with "Require status checks to pass before
merging", the three checks above, "Require branches to be up to date", and
"Allow force pushes" off.

- **What it enforces**: no pull request can merge while those three fail.
- **What it does not enforce**: a direct `git push` to `main` still lands.
  Required status checks gate merges, not pushes. This project pushes directly to
  `main` (every commit in its history is a direct push, including the release
  commit that `auto-release` makes), so the practical coverage is close to zero
  until a second person exists.
- **Cost**: zero workflow changes, zero new accounts, nothing to break. But it
  would let this document say "protected" while the actual risk is unchanged,
  which is the kind of statement this project has spent effort deleting.

## Alternative B - require a pull request, checks, and no bypass

Settings: the same, plus "Require a pull request before merging", plus
"Restrict who can push to matching branches" limited to the release bot's
identity, plus "Do not allow bypassing the above settings".

- **What it enforces**: every change to `main` arrives as a reviewed pull
  request; the eleven-job `Test` run must be green on the head commit.
- **The blocker**: this repository has **one** collaborator. "Require one
  approving review" cannot be satisfied by the author, so every pull request
  would be unmergeable. The honest variants are (a) require a pull request but
  *zero* approvals - so the PR exists as a record and the checks gate it, and the
  Owner merges their own PR; or (b) add a second GitHub account purely as a
  reviewer, which is a real account, not a bot with a synthetic approval.
- **The second blocker**: `auto-release.yml` pushes its bump commit directly to
  `main` (`git push origin HEAD:main`) and then tags. Under B that push is
  rejected unless the release identity is on the bypass list - and a bypass list
  is exactly the "no bypass" clause being contradicted. The two workable shapes
  are: let the release job open a pull request and merge it (more moving parts,
  and a failed merge leaves a bump commit on a branch), or exempt the release
  token and write down that the exemption exists. Exempting it silently would be
  worse than not protecting the branch, because the document would then be
  claiming coverage it does not have.
- **Cost**: either a second account, or a documented exemption, or a redesigned
  release path.

## What this proposal will not do

- It will not turn on protection that a single-account repository cannot honour,
  and then describe the repository as protected.
- It will not add a bot whose "approval" is a workflow step wearing a human's
  name. An approval that cannot be refused is not a review.
- It will not change `auto-release.yml` to work around whichever option is
  chosen. If the release path has to change, that is a separate bounded task with
  its own tests - the release path is the part of this project that has already
  produced three production incidents.

## The decision

**Question (one, for the Owner): do we turn on real branch protection for
`main` - which needs either a second GitHub account as reviewer or an explicitly
documented exemption for the release token - or do we keep pushing directly and
say so in the README?**

- **Answer A** (recommended if no second account will exist): apply Alternative
  A, and add one sentence to `docs/maintenance.md` saying that required checks
  gate pull requests only, that this project pushes directly, and that the real
  gate is the `Test` workflow plus `auto-release`. Cheap, honest, and it stops
  anyone reading "there is a CI gate" as "main cannot take a bad commit".
- **Answer B**: apply Alternative B with a second account, or with the release
  token on the bypass list and that exemption written down where the settings
  are described. More work, and the first option needs an account only the Owner
  can create.
- **Answer C**: leave `main` unprotected and write that down in the README next
  to the CI section, so the tool's own documentation does not imply a control
  that does not exist.

Whichever is chosen, the acceptance is the same: read the setting back from the
API afterwards (`gh api repos/lyear12/citevouch/branches/main`) and record what
it actually returns, not what was clicked. A settings page screenshot proves
nothing about enforcement; the API answer does.
