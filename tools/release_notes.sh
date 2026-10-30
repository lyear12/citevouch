#!/usr/bin/env bash
# Print the release notes for one tag.
#
# This lived inline in release.yml until the seventh review found that the
# "tag does not exist yet" path - the documented way to release by hand - died
# on `git describe` and took the whole release with it. Inline shell cannot be
# run by a test without transplanting the YAML, so it lives here: the workflow
# calls it, and tests/test_release_notes.py runs it in both tag states.
#
# Usage: tools/release_notes.sh <tag>
#
# Three cases, and all three have to exit 0:
#   * tag exists and has an earlier tag behind it  -> the range between them
#   * tag exists and is the first tag              -> that whole tag
#   * tag does not exist yet (workflow_dispatch)   -> HEAD, which is the
#     commit about to be tagged by the caller
set -euo pipefail

tag="${1:?usage: release_notes.sh <tag>}"

if git rev-parse -q --verify "refs/tags/${tag}" >/dev/null; then
    previous=$(git describe --tags --abbrev=0 "${tag}^" 2>/dev/null || true)
    if [ -n "$previous" ]; then
        range="${previous}..${tag}"
    else
        # The first release has nothing to compare against, and the whole
        # history is the honest answer.
        range="${tag}"
    fi
else
    # Not tagged yet. The workflow passes an explicit version on this path,
    # and the checkout is the commit that release will point at.
    range="HEAD"
fi

notes=$(git log --pretty=format:'- %s' "$range" -- . | grep -v '^- Release ' | head -60 || true)
if [ -z "$notes" ]; then
    notes="No commits in ${range} (the tag itself carries the change)."
fi
printf '%s\n' "$notes"
