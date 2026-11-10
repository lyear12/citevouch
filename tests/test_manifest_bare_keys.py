"""A source name TOML cannot spell bare is refused by both readers, alike.

`sources.toml` has two readers: `tomllib` on 3.11+, and `_mini_toml` on 3.10,
which has no `tomllib`.  A bare key may hold `A-Z`, `a-z`, `0-9`, `_` and `-`
and nothing else.  The line-based subset splits on `=` and strips, so it used
to bind anything the author wrote: `王力2020`, `smith/2020`, `smith 2020`.

Measured, same bytes, both readers, `[sources]` + `<key> = "page.txt"`:

===========================  ===========================  ==================
key                          tomllib                      subset
===========================  ===========================  ==================
`王力2020`                   refuses the whole file       binds `王力2020`
`wang力`                     refuses the whole file       binds `wang力`
`smith/2020`                 refuses the whole file       binds `smith/2020`
`smith+2020`                 refuses the whole file       binds `smith+2020`
`smith 2020`                 refuses the whole file       binds `smith 2020`
`smith:2020`                 refuses the whole file       binds `smith:2020`
`smith@2020`                 refuses the whole file       binds `smith@2020`
`papér`                      refuses the whole file       binds `papér`
===========================  ===========================  ==================

Same repository, same file, green on 3.10 and red on 3.12 - and the red one is
worse than a miss: `tomllib` refuses the file, so every claim in the manuscript
loses its source at once, while the author's own key looks perfectly fine on
the page.  `"王力2020"` is the same source under a legal spelling, quotes and
all, which is why the message offers it.

Two neighbouring shapes are deliberately *not* this question, and each keeps
the sentence it already had: a dotted key (`smith.2020` is legal TOML naming a
nested table) and a quoted key this reader cannot spell (`"pa#ge"`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from citevouch import sources

NL = chr(10)

PAGE = "We collected 40,688 examples from the corpus." + NL

#: Keys TOML allows unquoted.  Both readers must bind every one of them.
BARE_KEYS = [
    "paper",
    "Paper",
    "paper_2020",
    "paper-2020",
    "2020smith",
    "a",
    "_x",
    "-x",
]

#: Keys TOML refuses unquoted.  Both readers must refuse every one of them.
NOT_BARE_KEYS = [
    "\u738b\u529b2020",
    "wang\u529b",
    "smith/2020",
    "smith+2020",
    "smith 2020",
    "smith:2020",
    "smith@2020",
    "pap\u00e9r",
]

#: The same names, quoted.  Legal TOML, and both readers bind them.
QUOTED_KEYS = [
    '"\u738b\u529b2020"',
    '"smith:2020"',
    '"smith 2020"',
    '"smith/2020"',
    '"\u6587\u732e:2019"',
]


def manifest(key: str) -> str:
    return "[sources]" + NL + key + ' = "page.txt"' + NL


def both_readers(text: str) -> list[tuple[str, object]]:
    """What each reader makes of `text`, as (outcome, value or message)."""
    out: list[tuple[str, object]] = []
    for reader in (sources._load_toml, sources._mini_toml):
        try:
            out.append(("read", reader(text)))
        except ValueError as exc:
            out.append(("refused", str(exc)))
    return out


def bound(tmp_path: Path, key: str) -> dict[str, str]:
    """The sources a project binds when its manifest spells `key` that way."""
    root = tmp_path / "p"
    root.mkdir(exist_ok=True)
    (root / "sources.toml").write_text(manifest(key), encoding="utf-8", newline=NL)
    (root / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)
    original = sources._load_toml
    sources._load_toml = lambda text, odd=None: sources._mini_toml(text, odd)
    try:
        return sources.read_source_table(root).found
    finally:
        sources._load_toml = original


class TestTheKeysTomlCallsBare:
    @pytest.mark.parametrize("key", BARE_KEYS)
    def test_both_readers_bind_it(self, key: str) -> None:
        left, right = both_readers(manifest(key))
        assert left[0] == "read", f"{key}: tomllib refused a bare key"
        assert right[0] == "read", f"{key}: the subset refused a bare key"

    @pytest.mark.parametrize("key", BARE_KEYS)
    def test_the_two_readings_name_the_same_source(self, key: str) -> None:
        left, right = both_readers(manifest(key))
        assert left[1] == right[1], f"{key}: two readings of one file"


class TestTheKeysTomlWouldRefuse:
    @pytest.mark.parametrize("key", NOT_BARE_KEYS)
    def test_both_readers_refuse_it(self, key: str) -> None:
        left, right = both_readers(manifest(key))
        assert left[0] == "refused", f"{key}: tomllib was expected to refuse"
        assert right[0] == "refused", f"{key}: the subset bound a key TOML refuses"

    @pytest.mark.parametrize("key", NOT_BARE_KEYS)
    def test_the_two_refusals_are_one_sentence(self, key: str) -> None:
        """One refusal, one explanation, whichever interpreter is installed."""
        left, right = both_readers(manifest(key))
        assert left[1] == right[1], f"{key}: {left[1]!r} vs {right[1]!r}"

    @pytest.mark.parametrize("key", NOT_BARE_KEYS)
    def test_the_sentence_offers_the_quoted_spelling(self, key: str) -> None:
        """The message has to carry the fix, or it is only a refusal.

        Naming the spelling is not enough on its own: an author reading
        ``is not a bare TOML key. "王力2020" - to bind one source under that
        name`` is told what the fix looks like without being told it is a fix.
        The sentence says what to do *and* shows the result.
        """
        _, message = both_readers(manifest(key))[1]
        assert "not a bare TOML key" in message, key
        assert "quote it" in message, key
        assert f'"{key}"' in message, key

    def test_the_quoted_spelling_it_offers_actually_works(self, tmp_path: Path) -> None:
        """Every message in the list above names a spelling that binds.

        A refusal that suggests a spelling this reader then refuses is worse
        than a refusal with no suggestion: the author does what it says and is
        told again, in a different sentence.
        """
        for key in NOT_BARE_KEYS:
            found = bound(tmp_path, f'"{key}"')
            assert list(found) == [key], key
            assert found[key].endswith("page.txt"), key


class TestTheRefusedKeyIsRefusedByTheWholeRun:
    """Not just by the parser: the project reads the manifest, or does not."""

    @pytest.mark.parametrize("key", ["\u738b\u529b2020", "smith 2020"])
    def test_the_subset_binds_nothing_either(self, tmp_path: Path, key: str) -> None:
        root = tmp_path / "p"
        root.mkdir()
        (root / "sources.toml").write_text(manifest(key), encoding="utf-8", newline=NL)
        (root / "page.txt").write_text(PAGE, encoding="utf-8", newline=NL)

        real = sources.read_source_table(root)
        original = sources._load_toml
        sources._load_toml = lambda text, odd=None: sources._mini_toml(text, odd)
        try:
            mini = sources.read_source_table(root)
        finally:
            sources._load_toml = original

        assert real.found == mini.found == {}, key
        assert real.unusable == mini.unusable, key
        assert bool(real.manifest_problem) == bool(mini.manifest_problem), key
        assert real.manifest_problem, f"{key}: the manifest was read anyway"
        assert "not a bare TOML key" in str(real.manifest_problem), key


class TestTheNeighbouringShapesKeepTheirOwnSentence:
    """A dotted key is legal TOML, and an unspellable one is a different fault.

    Answering either with "quote it" would replace the right sentence with a
    near miss: `"smith.2020"` is how you bind a source called `smith.2020`,
    not how you fix a nested table, and `"pa#ge"` is refused for a reason the
    quoting does not address.
    """

    def test_the_dotted_key_still_speaks_of_a_nested_table(self) -> None:
        left, right = both_readers(manifest("smith.2020"))
        assert left[0] == "refused" and right[0] == "refused"
        assert left[1] == right[1]
        assert "dotted key" in str(left[1])
        assert "not a bare TOML key" not in str(left[1])

    def test_the_unspellable_key_still_speaks_of_spelling(self) -> None:
        left, right = both_readers(manifest('"pa#ge"'))
        assert left[0] == "refused" and right[0] == "refused"
        assert left[1] == right[1]
        assert "cannot spell" in str(left[1])
        assert "not a bare TOML key" not in str(left[1])


class TestTheQuotedNamesRead:
    @pytest.mark.parametrize("key", QUOTED_KEYS)
    def test_both_readers_bind_it(self, key: str) -> None:
        left, right = both_readers(manifest(key))
        assert left[0] == "read", f"{key}: tomllib refused a legal key"
        assert right[0] == "read", f"{key}: the subset refused a legal key"
        assert left[1] == right[1], f"{key}: two readings of one file"

    @pytest.mark.parametrize("key", QUOTED_KEYS)
    def test_the_run_binds_the_name_without_its_quotes(self, tmp_path: Path, key: str) -> None:
        """The quotes are syntax, not part of the name the claim will write."""
        unquoted = key[1:-1]
        found = bound(tmp_path, key)
        assert list(found) == [unquoted], key
        assert found[unquoted].endswith("page.txt"), key
