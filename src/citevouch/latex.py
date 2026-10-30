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


def strip_comments(text: str) -> str:
    r"""Remove `%` comments, keeping escaped ``\%`` as a literal percent.

    This is a scan rather than a regex because the two cases look identical to a
    look-behind: ``\%`` is an escaped percent that a reader sees, and ``\\%`` is
    a line break followed by a comment. Only the parity of the backslashes before
    the `%` tells them apart, so the parity is counted.

    Known limitation: a `%` inside a ``verbatim`` block is treated as a comment
    too. That costs nothing unless the swallowed line is the ``\end{verbatim}``
    itself, which would then be read as prose - a worse proposal, never a false
    verification.
    """
    out: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char == "\\" and index + 1 < length:
            out.append(text[index : index + 2])
            index += 2
            continue
        if char == "%":
            while index < length and text[index] != "\n":
                index += 1
            continue
        out.append(char)
        index += 1
    return "".join(out)


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
    for match in _INCLUDE.finditer(strip_comments(tex)):
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
    body = _CITE.sub(lambda match: _pandoc_marker(match.group(1)), body)
    text = _convert(body)
    # Collapse the runs of blank lines the block environments produce.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"
