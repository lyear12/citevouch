"""Read a LaTeX manuscript as the plain text this tool works on.

Everything downstream of `draft` reads Markdown: claim blocks, sentences,
`[@key]` markers. A `.tex` file is none of those, so it is converted here and
nowhere else. `scan` and `verify` never learn that LaTeX exists, which is the
point: the thing that decides whether a quote is on page 6 should not also be
the thing that has an opinion about `%` comments.

What this does:

* drops everything outside ``\\begin{document}`` / ``\\end{document}`` - the
  preamble and whatever follows the document (usually a bibliography);
* drops ``thebibliography``, ``verbatim``, ``tabular`` and friends whole, since
  their contents are reference lists and code, not prose that gets cited in a
  sentence;
* strips `%` comments, keeping an escaped ``\\%`` as a literal percent;
* turns every citation command into the Pandoc marker the rest of the tool
  already understands, so ``\\citep[see][p.~3]{a, b}`` becomes ``[@a; @b]``;
* keeps the argument of commands that carry text (``\\section``, ``\\textbf``,
  ``\\footnote``) and drops the ones that carry none (``\\label``, ``\\ref``,
  ``\\includegraphics``);
* turns block structure into paragraph breaks, because a sentence finder that
  cannot see paragraphs glues a heading onto the sentence beneath it.

What this does not do: it is not a TeX parser. A macro that changes how text is
produced, an ``\\input`` of another file, or an environment whose body is not
prose will be read as prose or dropped. The converted text is used only to find
the sentence around a citation - the quote itself always comes from the PDF - so
a mangled sentence costs a worse proposal, never a false verification.
"""

from __future__ import annotations

import re
from pathlib import Path

#: Suffixes this module claims. `looks_like_latex` is the only entrance.
SUFFIXES = frozenset({".tex", ".ltx", ".latex"})

_BEGIN_DOC = re.compile(r"\\begin\s*\{document\}")
_END_DOC = re.compile(r"\\end\s*\{document\}")
_CITE = re.compile(
    r"\\(?:cite|citep|citet|citealp|citealt|citeauthor|citeyear|citeyearpar"
    r"|nocite|parencite|textcite|autocite|footcite|smartcite|supercite)"
    r"\*?(?:\s*\[[^\]]*\])*\{([^}]*)\}"
)

#: Inline commands whose argument TeX prints without interpreting it. The
#: delimiter is any character the author picks, so there is no brace group to
#: balance and `_DROP_ARGUMENT` cannot express them. The body may not contain a
#: newline (that is TeX's own rule for `\verb`), which is what keeps a missing
#: closing delimiter from eating the rest of the paragraph.
_INLINE_VERBATIM = re.compile(
    r"\\(?P<name>verb\*?|lstinline|mintinline)"
    r"(?P<options>(?:[ \t]*\[[^\]\n]*\])*)"
    r"(?:[ \t]*\{(?P<language>[^{}\n]*)\})?"
    r"(?P<delimiter>[^A-Za-z \t\\])"
    r"(?P<body>[^\n]*?)"
    r"(?P=delimiter)"
)

#: Environments whose bodies TeX reads verbatim, so a `%` inside one is a
#: character and not the start of a comment. `tabular` and `tikzpicture` are
#: deliberately absent: they are dropped from the output anyway, but they do
#: honour `%` comments, so claiming otherwise would be a lie that only shows up
#: in a document that nests one of them inside these.
_VERBATIM_ENVIRONMENT = re.compile(
    r"\\begin\s*\{(?P<name>verbatim\*?|lstlisting|minted|filecontents)\}"
)

#: Stands in for text TeX does not interpret. A control character, so it cannot
#: collide with anything an author writes in a paper.
_VERBATIM_MARK = "\x00verbatim:"

# Commands whose first brace argument is text a reader sees.
_KEEP_ARGUMENT = frozenset(
    {
        "textbf",
        "textit",
        "textsc",
        "texttt",
        "textsl",
        "textup",
        "textmd",
        "textnormal",
        "textsuperscript",
        "textsubscript",
        "emph",
        "underline",
        "mbox",
        "hbox",
        "caption",
        "footnote",
        "footnotetext",
        "marginpar",
        "MakeUppercase",
        "MakeLowercase",
    }
)

# Sectioning commands: their argument is a title, which belongs on its own line.
_HEADING = frozenset(
    {"part", "chapter", "section", "subsection", "subsubsection", "paragraph", "subparagraph"}
)

#: Commands whose argument names another file this module does not read.
#: They are dropped from the output (they are not prose); the names are also
#: reported, because a paper split across files keeps its citations in the
#: parts, and a silent zero is the failure this tool exists to prevent.
_INCLUDE = re.compile(r"\\in(?:put|clude|cludeonly)\s*\{([^}]*)\}")

# Commands whose argument is not prose.
_DROP_ARGUMENT = frozenset(
    {
        "label",
        "ref",
        "eqref",
        "pageref",
        "autoref",
        "cref",
        "Cref",
        "usepackage",
        "documentclass",
        "bibliographystyle",
        "bibliography",
        "includegraphics",
        "input",
        "include",
        "hspace",
        "vspace",
        "setlength",
        "addtolength",
        "newcommand",
        "renewcommand",
        "providecommand",
        "def",
        "hypersetup",
        "setcounter",
        "cline",
        "multicolumn",
        "rule",
        "raisebox",
    }
)

# Environment bodies that are not prose and are dropped whole.
_DROP_ENVIRONMENT = frozenset(
    {
        "thebibliography",
        "verbatim",
        "verbatim*",
        "lstlisting",
        "minted",
        "tabular",
        "tabular*",
        "tikzpicture",
        "filecontents",
        "comment",
    }
)

# Environments that separate prose from prose.
_BLOCK_ENVIRONMENT = frozenset(
    {
        "document",
        "itemize",
        "enumerate",
        "description",
        "figure",
        "figure*",
        "table",
        "table*",
        "equation",
        "equation*",
        "align",
        "align*",
        "alignat",
        "gather",
        "gather*",
        "multline",
        "abstract",
        "quote",
        "quotation",
        "center",
        "flushleft",
        "flushright",
        "titlepage",
        "appendix",
        "theorem",
        "proof",
        "definition",
        "example",
        "minipage",
    }
)

# Escaped characters that stand for themselves.
_LITERAL = {
    "%": "%",
    "&": "&",
    "_": "_",
    "#": "#",
    "$": "$",
    "{": "{",
    "}": "}",
    " ": " ",
    ",": "",
    ";": " ",
    ":": "",
    "!": "",
    "-": "",
    "/": "",
    "@": "",
}

_SPACE_COMMANDS = frozenset(
    {
        "newline",
        "linebreak",
        "par",
        "newpage",
        "clearpage",
        "bigskip",
        "medskip",
        "smallskip",
        "noindent",
        "indent",
        "centering",
        "item",
    }
)


def looks_like_latex(path: str | Path) -> bool:
    """Whether this file should be converted before anything else reads it."""
    return Path(path).suffix.lower() in SUFFIXES


def _verbs_and_environment_bodies(text: str) -> tuple[str, list[str]]:
    r"""Put a placeholder where TeX does not read its input as prose.

    Two shapes need protecting, and both of them used to be read as ordinary
    text. The body of a ``verbatim`` environment (and of ``lstlisting``,
    ``minted``, ``filecontents``) is taken literally by TeX, so a `%` there is
    the character and not the start of a comment - reading it as a comment ate
    the ``\end{verbatim}`` and the rest of the document with it. And an inline
    verbatim command is how a paper *shows* its citation syntax, so its body
    must not be read as a citation.

    Returns the text with placeholders and the bodies they stand for, indexed by
    placeholder number, so `_restore_verbatim` can put them back.
    """
    bodies: list[str] = []

    def placeholder(body: str) -> str:
        bodies.append(body)
        return _VERBATIM_MARK + str(len(bodies) - 1) + _VERBATIM_MARK

    out: list[str] = []
    index = 0
    for match in _VERBATIM_ENVIRONMENT.finditer(text):
        if match.start() < index:
            continue
        name = match.group("name")
        close = _environment_close(text, match.end(), name)
        if close is None:
            continue
        out.append(text[index : match.end()])
        out.append(placeholder(text[match.end() : close]))
        index = close
    out.append(text[index:])
    environment_masked = "".join(out)

    out = []
    index = 0
    for match in _INLINE_VERBATIM.finditer(environment_masked):
        if match.start() < index:
            continue
        # Only the body is masked. The command and its delimiter stay, because
        # `_restore_verbatim` puts the body back and the text that comes out of
        # here has to be the document the author wrote - `to_text` still has to
        # recognise the construct in order to drop it. Masking the whole call
        # left `\citep{a1}` sitting where `\verb|\citep{a1}|` used to be, which
        # is the exact false citation this protection exists to prevent.
        out.append(environment_masked[index : match.start("body")])
        out.append(placeholder(match.group("body")))
        index = match.end("body")
    out.append(environment_masked[index:])
    return "".join(out), bodies


def _restore_verbatim(text: str, bodies: list[str]) -> str:
    """Put back what `_verbs_and_environment_bodies` stood in for."""
    if not bodies:
        return text
    pattern = re.compile(re.escape(_VERBATIM_MARK) + r"(\d+)" + re.escape(_VERBATIM_MARK))
    return pattern.sub(lambda found: bodies[int(found.group(1))], text)


#: Stands in for inline verbatim text while the citation pattern and the
#: converter run, and is put back afterwards as the characters TeX prints.
#: Different from `_VERBATIM_MARK` because `strip_comments` restores those
#: immediately: a `\verb|\citep{a}|` has to survive comment stripping as the
#: construct it is, and only be taken apart here, after the passes that would
#: otherwise read a quotation of syntax as syntax.
_DROPPED_MARK = "\x00dropped:"


def _drop_inline_verbatim(text: str) -> tuple[str, list[str]]:
    r"""Hide each ``\verb``-family body from the passes that read citations.

    `strip_comments` protects these bodies and then puts them back, which is
    right for its own job - the `%` inside them is a character. It is wrong for
    everything downstream: the restored body is read by `_CITE`, so a paper that
    *shows* ``\verb|\citep{a}|`` used to come out as a real ``[@a]``, and
    `_convert` kept whatever followed the command (``\verb|[@a]|``), so the
    example also became prose. Both of those are the tool reading a quotation of
    syntax as syntax.

    The bodies come back rather than being discarded: TeX prints them literally,
    so the `%` in ``50\verb|%|`` has to reach the output as a percent sign.
    """
    bodies: list[str] = []
    out: list[str] = []
    index = 0
    for match in _INLINE_VERBATIM.finditer(text):
        if match.start() < index:
            continue
        out.append(text[index : match.start()])
        out.append(_DROPPED_MARK + str(len(bodies)) + _DROPPED_MARK)
        bodies.append(match.group("body"))
        index = match.end()
    out.append(text[index:])
    return "".join(out), bodies


def _restore_dropped(text: str, bodies: list[str]) -> str:
    """Put back the literal characters `_drop_inline_verbatim` took out."""
    if not bodies:
        return text
    pattern = re.compile(re.escape(_DROPPED_MARK) + r"(\d+)" + re.escape(_DROPPED_MARK))
    return pattern.sub(lambda found: bodies[int(found.group(1))], text)


def strip_comments(text: str) -> str:
    r"""Remove `%` comments, keeping escaped ``\%`` as a literal percent.

    This is a scan rather than a regex because the two cases look identical to a
    look-behind: ``\%`` is an escaped percent that a reader sees, and ``\\%`` is
    a line break followed by a comment. Only the parity of the backslashes before
    the `%` tells them apart, so the parity is counted.

    Verbatim text is protected first and put back afterwards: a `%` inside a
    ``verbatim`` body or inside ``\verb|...|`` is a character, not a comment.
    Before that, the `%` was read as a comment and the scan ate the rest of the
    line - including the ``\end{verbatim}`` that closes the block, and with it
    everything the author wrote afterwards.
    """
    masked, bodies = _verbs_and_environment_bodies(text)
    out: list[str] = []
    index = 0
    length = len(masked)
    while index < length:
        char = masked[index]
        if char == "\\" and index + 1 < length:
            out.append(masked[index : index + 2])
            index += 2
            continue
        if char == "%":
            while index < length and masked[index] != "\n":
                index += 1
            continue
        out.append(char)
        index += 1
    return _restore_verbatim("".join(out), bodies)


def document_body(text: str) -> str:
    """The part between ``\\begin{document}`` and ``\\end{document}``."""
    begin = _BEGIN_DOC.search(text)
    if begin is not None:
        text = text[begin.end() :]
    end = _END_DOC.search(text)
    if end is not None:
        text = text[: end.start()]
    return text


def _pandoc_marker(keys: str) -> str:
    names = [name.strip() for name in keys.split(",") if name.strip()]
    if not names:
        return ""
    return "[" + "; ".join("@" + name for name in names) + "]"


def _group_end(text: str, start: int, opener: str = "{", closer: str = "}") -> int:
    """Index just past the balanced group starting at `start`, or -1."""
    if start >= len(text) or text[start] != opener:
        return -1
    depth = 0
    index = start
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return -1


def _environment_close(text: str, start: int, name: str) -> int | None:
    r"""Index of the ``\end{name}`` that closes a verbatim block, or None.

    A verbatim body is literal, so nesting is not possible and the first
    ``\end{name}`` wins. Returning None means the block is never closed, and the
    caller then leaves the document alone rather than guessing where it stops.
    """
    closer = re.compile(r"\\end\s*\{" + re.escape(name) + r"\}")
    found = closer.search(text, start)
    return None if found is None else found.start()


def _skip_environment(text: str, start: int, name: str) -> int:
    """Index just past the matching ``\\end{name}``, counting nesting."""
    depth = 1
    cursor = start
    opener = re.compile(r"\\begin\s*\{" + re.escape(name) + r"\}")
    closer = re.compile(r"\\end\s*\{" + re.escape(name) + r"\}")
    while depth > 0:
        found = closer.search(text, cursor)
        if found is None:
            return len(text)
        between = opener.search(text, cursor, found.end())
        if between is None:
            depth -= 1
            cursor = found.end()
        else:
            depth += 1
            cursor = between.end()
    return cursor


def _convert(text: str) -> str:
    """Convert one stretch of LaTeX (no comment stripping, no preamble)."""
    out: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]

        if char == "\\":
            nxt = text[index + 1] if index + 1 < length else ""
            if nxt.isalpha():
                end = index + 1
                while end < length and text[end].isalpha():
                    end += 1
                name = text[index + 1 : end]
                if name in _HEADING:
                    cursor = _skip_optional_args(text, end)
                    group = _group_end(text, cursor)
                    if group > 0:
                        title = _convert(text[cursor + 1 : group - 1]).strip()
                        out.append("\n\n" + title + "\n\n")
                        index = group
                        continue
                    index = end
                    continue
                if name in _KEEP_ARGUMENT:
                    cursor = _skip_optional_args(text, end)
                    group = _group_end(text, cursor)
                    if group > 0:
                        out.append(_convert(text[cursor + 1 : group - 1]))
                        index = group
                        continue
                    index = end
                    continue
                if name in _DROP_ARGUMENT:
                    cursor = _skip_optional_args(text, end)
                    group = _group_end(text, cursor)
                    index = group if group > 0 else end
                    continue
                if name in ("begin", "end"):
                    cursor = _skip_optional_args(text, end)
                    group = _group_end(text, cursor)
                    if group < 0:
                        index = end
                        continue
                    environment = text[cursor + 1 : group - 1].strip()
                    if name == "begin" and environment in _DROP_ENVIRONMENT:
                        index = _skip_environment(text, group, environment)
                        continue
                    out.append("\n\n" if environment in _BLOCK_ENVIRONMENT else "")
                    index = group
                    continue
                if name in _SPACE_COMMANDS:
                    out.append("\n\n" if name == "par" else " ")
                    index = end
                    continue
                # An unknown command: keep whatever text it wraps, drop the name.
                index = end
                continue
            if nxt in _LITERAL:
                out.append(_LITERAL[nxt])
                index += 2
                continue
            if nxt == "\\":
                out.append("\n")
                index += 2
                continue
            index += 2
            continue

        if char == "~":
            out.append(" ")
            index += 1
            continue

        if char == "$":
            double = text.startswith("$$", index)
            size = 2 if double else 1
            close = text.find("$" * size, index + size)
            if close < 0:
                index += size
                continue
            out.append(_plain_math(text[index + size : close]))
            index = close + size
            continue

        if char in "{}":
            index += 1
            continue

        out.append(char)
        index += 1

    return "".join(out)


def _skip_optional_args(text: str, start: int) -> int:
    """Skip any ``*`` and ``[..]`` arguments before a command's brace group."""
    index = start
    if index < len(text) and text[index] == "*":
        index += 1
    while index < len(text) and text[index] == "[":
        group = _group_end(text, index, "[", "]")
        if group < 0:
            break
        index = group
    return index


def _plain_math(inner: str) -> str:
    """Inline math as a reader says it: `$\\\\alpha = 0.5$` becomes `= 0.5`."""
    without_commands = re.sub(r"\\[A-Za-z]+", "", inner)
    without_commands = without_commands.replace("{", "").replace("}", "")
    return without_commands.strip()


def included_files(tex: str) -> list[str]:
    """Name the files this document pulls in, in the order it pulls them."""
    seen: list[str] = []
    for match in _INCLUDE.finditer(_drop_inline_verbatim(strip_comments(tex))[0]):
        name = match.group(1).strip()
        if name and name not in seen:
            seen.append(name)
    return seen


def to_text(tex: str) -> str:
    """Convert a LaTeX document into the plain text the rest of the tool reads.

    The result keeps the paragraph structure (blank lines) and turns citations
    into ``[@key]`` so that `draft` needs no second code path for LaTeX.
    """
    body = document_body(strip_comments(tex))
    body, verbatim = _drop_inline_verbatim(body)
    body = _CITE.sub(lambda match: _pandoc_marker(match.group(1)), body)
    text = _restore_dropped(_convert(body), verbatim)
    # Collapse the runs of blank lines the block environments produce.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"
