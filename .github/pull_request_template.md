## What was wrong

<!-- The failing case, named. If there is an issue, its number. -->

## What changed, and why that shape

<!-- The class, not the sample. If the same bug could come back elsewhere, say where. -->

## Verification

- [ ] A test fails without this change and passes with it
- [ ] `python -m pytest -q` is green
- [ ] `ruff check . && ruff format --check .` is clean
- [ ] `citevouch verify demo/manuscript.md --root demo` still exits 1 with `fcg-editor` missing

## Not tried

<!-- What you could not check here: another OS, an old interpreter, a real manuscript.
     An empty section is a claim, so write "nothing" if it is true. -->
