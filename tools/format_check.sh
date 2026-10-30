#!/bin/sh
# Format-check exactly the files this repository tracks.
#
# `ruff format --check .` counts every file on the machine it runs on: untracked
# drafts, a scratch test being written, anything a .gitignore pattern missed.
# Three releases in a row quoted a file count that only held on the machine that
# wrote it - 58 here, 57 in CI, same tree - and each time the gate caught it
# after the fact, because the gate measures the claim and the claim was wrong.
#
# `git ls-files` is the same set on every clone, so the number in a commit
# message is a number whoever reads it can reproduce. That is the whole point of
# writing the number down.
set -eu

count=$(git ls-files -- '*.py' '*.md' '*.toml' | wc -l)
if [ "$count" -eq 0 ]; then
    # Not "0 files already formatted": no files is not a clean tree, it is a
    # checkout that could not be read, and reporting it as clean would be the
    # silence this gate exists to break.
    echo "no tracked files to check; is this a checkout?" >&2
    exit 2
fi

# xargs turns a child's exit 1 into 123. The gate only needs "not zero", but a
# person reading 123 learns nothing, so it is mapped back to ruff's own 1.
status=0
git ls-files -z -- '*.py' '*.md' '*.toml' | xargs -0 python -m ruff format --check -- || status=$?
[ "$status" -eq 123 ] && status=1
exit "$status"
