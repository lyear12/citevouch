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
#
# Two things this script used to get wrong, both found by CI failing on a
# commit message that quoted it:
#
# 1. It counted `*.toml` and handed the toml files to ruff, which declines
#    them - it formats Python and the code blocks in Markdown, nothing else.
#    So it reported 147 files while looking at 149, and `tests/test_format_check.py`
#    carried `declined = 2` with a comment explaining the gap. A count that
#    includes inputs the tool never judged is a count of something else; the gap
#    was documented instead of removed, which is how a wrong number stays alive.
#
# 2. Nothing checked that ruff had judged anything at all. Given only toml
#    files, ruff printed nothing and exited 0, and this script echoed that
#    silence as a clean tree - the same mistake as reading zero passing tests
#    out of a suppressed summary line. It now refuses to be green without a
#    summary line, and refuses to be green when the summary disagrees with the
#    number of files it handed over.
set -eu

# The extensions ruff actually formats. Adding one here without checking that
# ruff reports it back is how the count and the measurement drift apart again.
count=$(git ls-files -- '*.py' '*.md' | wc -l)
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
out=$(git ls-files -z -- '*.py' '*.md' | xargs -0 python -m ruff format --check -- 2>&1) || status=$?
[ "$status" -eq 123 ] && status=1

if [ -n "$out" ]; then
    printf '%s\n' "$out"
fi

if [ "$status" -ne 0 ]; then
    # ruff already said which files it would reformat; its own exit code is the
    # answer and re-deriving it would only add a second chance to be wrong.
    exit "$status"
fi

reported=$(printf '%s\n' "$out" | grep -oE '[0-9]+ files? already formatted' | tail -1 | cut -d' ' -f1)
if [ -z "$reported" ]; then
    # ruff said nothing and exited 0: it judged no file. Reporting that as a
    # clean tree is the silence this gate exists to break.
    echo "ruff reported no summary line, so it judged nothing; $count file(s) were handed to it" >&2
    exit 2
fi

if [ "$reported" -ne "$count" ]; then
    # The count is quoted in commit messages. If the tool declined some of the
    # files, that number describes a different set than the one in the message.
    echo "ruff judged $reported of the $count file(s) handed to it; the count cannot be quoted" >&2
    exit 2
fi
