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
#: Every citation command this tool reads, in every spelling natbib and
#: biblatex give it.  One table, because the copy `draft.py` kept had
#: already fallen behind: it was missing `citeyearpar`, so a manuscript
#: citing with it got a `[@key]` marker from `to_text` and no citation site
#: from `draft` - `draft` then said "no citations were found" while the
#: marker sat in the very text it was reading.
#:
#: The capitalised forms are not decoration: an author writes the capital
#: one when the citation opens a sentence, which is the first citation
#: anyone reading the paper sees.  Measured before they were listed,
#: `\Citet{knuth}` reached the page as the bare word `knuth`, and `draft`
#: proposed nothing at all.
#:
#: Both families have them and the table has to carry both.  natbib spells
#: `\Citet`; biblatex spells `\Textcite`.  Listing only natbib's was the
#: half-fix: measured on `\Autocite{paper}` where `\autocite{paper}` works,
#: the sentence became `'paper showed the effect.'` - the key pasted into
#: the prose as a word - and `draft` then said "no citations were found"
#: about a manuscript whose first sentence cites a paper.
CITATION_NAMES = tuple(
    sorted(
        {
            "cite",
            "citep",
            "citet",
            "citealp",
            "citealt",
            "citeauthor",
            "citeyear",
            "citeyearpar",
            "nocite",
            "parencite",
            "textcite",
            "autocite",
            "footcite",
            "smartcite",
            "supercite",
            "fullcite",
        }
        # The capitalised forms, spelled out rather than derived by
        # upper-casing the first letter: `\Cite` is not natbib's and
        # `\Nocite` is not biblatex's, so deriving them would claim two
        # commands exist that no author has ever written.  Derived, the
        # table would also grow `\Footcite` from `footcite` whether or not
        # biblatex defined it - and it is the reverse that matters here:
        # a name that exists and is missing costs the author a citation.
        | {
            # natbib
            "Citet",
            "Citep",
            "Citealp",
            "Citealt",
            "Citeauthor",
            "Citeyear",
            "Citeyearpar",
            # biblatex
            "Autocite",
            "Parencite",
            "Textcite",
            "Footcite",
            "Smartcite",
            "Supercite",
            "Fullcite",
        },
        key=len,
        reverse=True,
    )
)

#: The plural commands.  They take one brace group per source, so they need
#: a pattern of their own; the names come from here for the same reason.
MULTI_CITATION_NAMES = tuple(
    sorted(
        {
            "cites",
            "citeps",
            "citets",
            "citealps",
            "citealts",
            "parencites",
            "textcites",
            "autocites",
            "footcites",
            "smartcites",
            "supercites",
            "fullcites",
            # biblatex's capitalised plurals, for the same reason as the
            # singular ones: `\Autocites{a}{b}` opens a sentence.
            "Autocites",
            "Parencites",
            "Textcites",
            "Footcites",
            "Smartcites",
            "Supercites",
            "Fullcites",
        },
        key=len,
        reverse=True,
    )
)

#: Whitespace between a citation command and its arguments.  TeX allows a
#: space there and a reflowed line ends up with one, so `\citep[p.~3] {a}`
#: is the same citation as `\citep[p.~3]{a}` and used to be invisible: the
#: key was left as a bare word on the page and `draft` reported that the
#: manuscript cited nothing.
#:
#: A newline is deliberately excluded.  Between a command and its mandatory
#: argument a newline is where a *missing* brace would find the next
#: paragraph's brace group, and reading one paragraph's text as another
#: paragraph's citation is the kind of silent wrong answer this module
#: exists to avoid.
_GAP = r"[ \t]*"
#: The character a TeX command name starts with, spelled once: as a literal it costs a quoting layer per use,
#: and this file has already miscounted that layer twice.
BACKSLASH = chr(92)

_CITE = re.compile(
    r"\\(?:"
    + "|".join(CITATION_NAMES)
    + r")\*?(?:"
    + _GAP
    + r"\[[^\]]*\])*"
    + _GAP
    + r"\{([^}]*)\}"
)

#: The plural citation commands take one brace group per source, each with
#: its own optional arguments: `\cites[see][p.~3]{a}[p.~4]{b}`.  `_CITE`
#: cannot match them - its name ends at `cite`, and `s` is neither `*` nor
#: `[` nor `{` - so they fell through to the generic rule that drops a
#: command's name and keeps its arguments, which left every key in the prose
#: as a bare word and made `citation_sites` report that a manuscript citing
#: three sources at once cited none of them.  Measured before this pattern
#: existed:
#:
#:     \cites{a}{b}        -> 'ab'    sites=[]
#:     \parencites{a}{b}   -> 'ab'    sites=[]
#:     \citep{a}           -> '[@a]'  sites=['a']
_MULTI_CITE = re.compile(
    r"\\(?P<name>"
    + "|".join(MULTI_CITATION_NAMES)
    + r")\*?(?P<arguments>(?:(?:"
    + _GAP
    + r"\[[^\]]*\])*"
    + _GAP
    + r"\{[^{}]*\})+)"
)
_MULTI_ARGUMENT = re.compile(r"(?:" + _GAP + r"\[[^\]]*\])*" + _GAP + r"\{(?P<keys>[^{}]*)\}")

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

#: Environments whose body TeX reads as characters, plus the one the `comment`
#: package skips with a verbatim-style scan. A command inside one of these is
#: being *shown*, not executed: it is the syntax the paper is talking about, and
#: running it would be the tool reading a quotation as a command.
#:
#: `included_files` needs this set separately from `_VERBATIM_ENVIRONMENT`.
#: That one answers "is a `%` here a character", and it leaves `comment` out on
#: purpose (a `%` inside a comment environment starts a real comment). This one
#: answers "is a command here executed", and `comment` belongs in it.
#:
#: Measured before this set existed: a listing that showed `\input{chapters/intro}`
#: made `draft` print "This document pulls text in from chapters/intro, which
#: `citevouch draft` does not read" - a sentence about a file the paper never
#: reads, in the one comment the tool tells the author to check.
_LITERAL_ENVIRONMENT = frozenset(
    {"verbatim", "verbatim*", "lstlisting", "minted", "filecontents", "comment"}
)

_LITERAL_BEGIN = re.compile(
    r"\\begin\s*\{(?P<name>" + "|".join(sorted(map(re.escape, _LITERAL_ENVIRONMENT))) + r")\}"
)

#: Stands in for text TeX does not interpret. A control character, so it cannot
#: collide with anything an author writes in a paper.
_VERBATIM_MARK = "\x00verbatim:"

# Commands whose first brace argument is text a reader sees.
#: Note commands whose argument is a sentence of its own.
#:
#: They used to be inline (``_KEEP_ARGUMENT``), which pasted the note's words
#: into the words around it: ``The method works\footnote{See \citep{fn} for the proof.}, and we ...`` converted to ``The method worksSee
#: [@fn] for the proof., and we ...``.  The word ``worksSee`` is in no paper, and
#: `draft` proposed exactly that string as the claim text, so the proposal was
#: built on a sentence nobody wrote.  A block of their own keeps the main
#: sentence whole and leaves the note where a reader can see it is a note.
#:
#: The first version of this list held three kernel names.  Measured on the tree
#: it left behind, ``\thanks{We thank the annotators.}``, ``\tnotetext{...}``,
#: ``\marginnote{...}``, ``\sidenote{...}`` and ``\endnote{...}`` all still glued
#: their body into the sentence - ``The method worksWe thank the annotators., and
#: we show it.`` - which is the same defect under names a paper about papers
#: uses constantly.  A name on this list is a claim that the name is a note; a
#: name missing from it is a claim that the words belong to the sentence.
_SEPARATE_ARGUMENT = frozenset(
    {
        "footnote",
        "footnotetext",
        "marginpar",
        # The kernel's note inside ``\author`` and ``\title``.  It is the one
        # that reaches a manuscript most often, because every funded paper has
        # one, and it is written in the middle of a sentence.
        "thanks",
        # threeparttable's note under a table.
        "tnotetext",
        # The margin/side-note packages.
        "marginnote",
        "sidenote",
        "sidenotetext",
        # The endnotes package.
        "endnote",
    }
)

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
        "makebox",
        "framebox",
        "caption",
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

#: A LaTeX control word is a backslash and then ASCII letters.  ``str.isalpha``
#: is not that test: it is true for Chinese, Japanese and Korean characters too,
#: and Chinese prose has no spaces, so ``\noindent构式语法认为...`` was read as
#: one control word whose name was ``noindent`` plus the whole sentence.  The
#: sentence vanished - measured on a four-line ``ctexart`` document, every line
#: of prose disappeared and what survived was the closing punctuation.  The
#: damage is silent: `draft` proposes nothing, and `check` reports a clean run
#: over text that was never read.
_LETTER = re.compile(r"[A-Za-z]")


def _is_letter(char: str) -> bool:
    """Whether `char` can be part of a control word's name."""
    return _LETTER.match(char) is not None


#: ``\input`` also takes its filename without braces - plain TeX's form, and the
#: one people type by hand.  ``_INCLUDE`` above only sees the braced spelling,
#: so ``\input sec/intro`` used to leave ``sec/intro`` in the prose *and* report
#: no included files: the path was glued into the sentence around a citation,
#: which is the sentence `draft` proposes a claim for, and the author was told
#: nothing was missing while a whole section of the paper - its citations
#: included - was never opened.  Measured: ``We show this in \input sec_intro
#: and continue`` converted to ``We show this in sec_intro and continue`` with
#: ``included_files`` returning ``[]``.
_BARE_INPUT = re.compile(r"\\input\s+(?P<name>[^\s{}%\\]+)")

#: File-inclusion commands beyond ``\input``/``\include``/``\includeonly``, and
#: how many braced arguments name the file: ``\import{dir/}{file}`` takes two and
#: the name is their concatenation, everything else takes one.
#:
#: Each of these was in neither the keep-list nor the drop-list, so the same
#: fallthrough that produced ``redsmall`` for ``\textcolor`` pasted the path into
#: the prose - and ``included_files`` said nothing was included.  Measured:
#: ``\subfile{sec/intro}`` became ``sec/intro`` in the text and ``[]`` from
#: ``included_files``; ``\includepdf{pages/p1.pdf}`` became ``pages/p1.pdf``;
#: ``\lstinputlisting{code/s1.py}`` became ``code/s1.py``.  The whole point of
#: this list is that a paper split across files keeps its citations in the parts,
#: and the parts were being read as if they were sentences.
_INCLUDE_ARGUMENTS = {
    "subfile": 1,
    "import": 2,
    "subimport": 2,
    "includestandalone": 1,
    "includepdf": 1,
    "lstinputlisting": 1,
    "verbatiminput": 1,
}

_INCLUDE_COMMAND = re.compile(
    r"\\(?P<name>" + "|".join(sorted(_INCLUDE_ARGUMENTS, key=len, reverse=True)) + r")\s*"
)

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
        # `\\ref`-family commands that the fallthrough left in the sentence:
        # `\\nameref{sec:data}` became ``sec:data`` as a word of the prose, so
        # `draft` proposed a sentence containing a label key.  `\\vref` is the
        # same command under a different package, so it goes in the same set -
        # a table of names retyped in a second place is incomplete there.
        "nameref",
        "vref",
        "Vref",
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
        "hypersetup",
        "setcounter",
        "cline",
        "raisebox",
    }
)

# Environment bodies that are not prose and are dropped whole.
#: TeX conditionals that open a block and end at a matching ``\fi``.
#: Every name here takes its test from the following tokens rather than from
#: braces, so nesting one inside another is a matter of counting names.
#: ``ifthenelse`` is deliberately absent: it is a macro from the ``ifthen``
#: package that takes three braced arguments and no ``\fi``, and
#: counting it here would leave every body unterminated.
_TEX_CONDITIONAL = frozenset(
    {
        "if",
        "if0",
        "if1",
        "ifcase",
        "ifcat",
        "ifcsname",
        "ifdefined",
        "ifdim",
        "ifeof",
        "iffalse",
        "ifhbox",
        "ifhmode",
        "ifinner",
        "ifmmode",
        "ifnum",
        "ifodd",
        "iftrue",
        "ifvbox",
        "ifvmode",
        "ifvoid",
        "ifx",
    }
)

#: Conditionals that take no operand before their body, so the converter can
#: act on them without parsing TeX tokens.  ``\ifnum``, ``\ifdim``, ``\ifodd``,
#: ``\ifx``, ``\ifcat`` and ``\ifcase`` all read operands first; acting on
#: those without reading the operands pasted them into the sentence
#: (``\ifnum1>0 \citep{x}\fi`` measured as ``1>0 [@x]``), so they stay in
#: ``_TEX_CONDITIONAL`` - where they are counted for nesting - and out of both
#: act-on sets.  That leaves them exactly as they were, and the operand problem
#: is a token-level parser away rather than a half fix away.
_NO_OPERAND_CONDITIONAL = frozenset({"iftrue", "iffalse", "if0", "if1", "ifdefined"})

#: Conditionals whose body is dead text by construction.  Converting a body
#: that TeX never reads turned a commented-out citation into a real one:
#: ``\iffalse \citep{hidden} \input{ghost/sec} \fi`` measured as
#: ``[@hidden]`` in the prose and ``ghost/sec`` in the include list, so
#: `draft` proposed a claim for a citation the author had turned off and the
#: author was told a file was missing that the paper never reads.  A \else
#: inside one of these is live text and is kept.
_CONDITIONAL_FALSE = frozenset({"iffalse", "if0"} & _NO_OPERAND_CONDITIONAL)

#: The mirror image: body is live, the marker is not.  It used to leave its
#: own name in the sentence (``\iftrue A \fi`` -> ``A`` was right, but
#: ``\ifdefined\x`` pasted ``ifdefined``), because the fallthrough
#: drops a command's name only when it has no body to keep.
_CONDITIONAL_TRUE = frozenset({"iftrue", "if1"} & _NO_OPERAND_CONDITIONAL)

#: ``\\ifthenelse{test}{yes}{no}`` is not decidable here, and both
#: branches are text the author wrote.  Only the test is metadata.
#: Command name -> how many leading brace groups are the test.  The two
#: groups after those are branches, which are the author's prose.
#: Measured one by one: every command below pasted its test into the
#: sentence and glued its branches (``ifboolexpr{test}{Yes}{No}`` came out
#: as ``testYesNo``), and none of them was in any table the converter
#: consulted, so all of it reached the reader.
_BRANCH_COMMAND: dict[str, int] = {
    "ifthenelse": 1,
    "ifboolexpr": 1,
    "ifboolexpe": 1,
    "iftoggle": 1,
    "ifbool": 1,
    "ifblank": 1,
    "ifstrempty": 1,
    "ifrmnum": 1,
    "ifnumodd": 1,
    "ifcsdef": 1,
    "ifcsundef": 1,
    "ifcsvoid": 1,
    "ifcsempty": 1,
    "ifdefstring": 1,
    "IfFileExists": 1,
    "InputIfFileExists": 1,
    "ifstrequal": 2,
    "ifnumequal": 2,
    "ifnumgreater": 2,
    "ifnumless": 2,
    "ifinlist": 2,
    "ifnumcomp": 3,
    "ifdimcomp": 3,
    "ifdef": 0,
    "ifundef": 0,
    "ifdefmacro": 0,
    "ifdefparam": 0,
    "ifdefempty": 0,
    "ifdefvoid": 0,
    "ifdefltxprotect": 0,
}

#: The subset whose test begins with a bare control sequence.  The
#: fallthrough already drops that token, so this only has to say which
#: names have one; without it the group count is applied to the token.
_BRANCH_BARE_TEST: frozenset[str] = frozenset(
    {
        "ifdef",
        "ifundef",
        "ifdefmacro",
        "ifdefparam",
        "ifdefempty",
        "ifdefvoid",
        "ifdefltxprotect",
        "ifdefstring",
    }
)

#: Environments whose body is not prose, so it is dropped whole.
#:
#: A table is a grid of cells.  The author does not assert its rows the way they
#: assert a sentence, so a citation written inside one labels a row rather than
#: supporting an argument, and the column specification (``{lX}``) is
#: typesetting, not a word.
#:
#: This set used to name ``tabular`` and ``tabular*`` only, which meant the
#: choice of package decided whether the tool read a table as text.  Measured
#: before the fix, converting ``\\begin{tabularx}{\\linewidth}{lX}`` and one row
#: gave ``'lX\\nBaseline [@knuth2020] & 90,000'``: the column spec as a word, the
#: row as a sentence, and the row's citation recorded as a citation of the
#: paper's argument.  ``draft`` then said::
#:
#:     0 claim block(s) proposed (0 verbatim), 1 citation(s) left as comments
#:     <!-- line 9: knuth2020 - nothing on any page shares enough terms with
#:          the sentence (3 needed) -->
#:
#: - about ``Baseline \\citep{knuth2020} & 90,000``, which is not a sentence at
#: all.  The same table with ``tabular`` was dropped and the run truthfully
#: said "no citations were found".
#:
#: Deliberately absent: ``array``, ``matrix``, ``pmatrix``, ``bmatrix``,
#: ``Bmatrix``, ``vmatrix``, ``Vmatrix``, ``smallmatrix``, and the display-math
#: environments (``equation``, ``align``, ``gather``, ``split``, ``cases``).
#: Those bodies are formulas, where a number is part of the formula and a
#: reader does see it - the converter keeps their numbers on purpose, and
#: ``tests/test_table_environments.py`` writes that decision down as tests.
#: Table environments that take ``\\caption`` *inside* their own body.
#:
#: A ``table`` float keeps its caption outside the grid, so dropping ``tabular``
#: always left the caption alone.  The long-table packages are the other way
#: round - they break across pages and repeat the caption in a running head, so
#: ``\\caption`` is written before ``\\endfirsthead``, inside the environment.
#: Dropping the body therefore dropped a sentence the author wrote and a reader
#: sees, including the citation under the table.
#:
#: Measured before this set existed, ``draft`` on a paper whose longtable
#: caption cites ``knuth2020`` said::
#:
#:     0 claim block(s) proposed: no citations were found to propose them for
#:
#: The caption is prose, so it is converted and appended after the (dropped)
#: table; the cells stay out.
_CAPTIONED_ENVIRONMENT = frozenset({"longtable", "xltabular", "longtabu"})

_DROP_ENVIRONMENT = frozenset(
    {
        "thebibliography",
        "verbatim",
        "verbatim*",
        "lstlisting",
        "minted",
        "tikzpicture",
        "filecontents",
        "comment",
        # Tables, in every package a journal template might name.  `tabular`
        # and `tabular*` were the only two here; the rest were read as prose.
        "tabular",
        "tabular*",
        "tabularx",
        "xltabular",
        "tabulary",
        "longtable",
        "tabu",
        "longtabu",
        "supertabular",
    }
)

#: Commands that define a macro or an environment.  Their bodies are templates,
#: not sentences: ``\newcommand{\mycite}[1]{\citep{#1}}`` is a rule about how a
#: later call gets rendered, and the ``#1`` in it is a hole.  They used to be
#: handled as "drop one argument", so the parameter count and the body stayed in
#: the stream and were read as prose.  Measured before this set existed:
#: ``\newcommand{\knuthcite}{\citep{knuth}}`` put a ``[@knuth]`` into the text of
#: a paper that never cites Knuth, and ``\newcommand{\seecite}[1]{see
#: \citep{#1}}`` turned the real call ``\seecite{knuth}`` into a bare ``knuth``
#: while recording a citation to the key ``#1`` - the one case where the tool
#: invents evidence and loses the real citation in the same step.
_DEFINITION = frozenset(
    {
        "newcommand",
        "renewcommand",
        "providecommand",
        "DeclareRobustCommand",
        "def",
        "gdef",
        "edef",
        "xdef",
        "newenvironment",
        "renewenvironment",
        "newtheorem",
        # The xparse and etoolbox spellings take the same shape: a name, an
        # optional count, an optional default, a body.  They were falling
        # through as unknown commands, so the body stayed in the prose and
        # `\newcommandx{\x}[1]{Body #1}` measured as `[1]Body #1`.
        "newcommandx",
        "renewcommandx",
        "providecommandx",
        "DeclareDocumentCommand",
        "NewDocumentCommand",
        "RenewDocumentCommand",
        "ProvideDocumentCommand",
    }
)

#: Definitions written as ``\def\name#1#2{body}``: the name is not in braces and
#: the parameter text may hold anything up to the body.
#: The xparse spellings that take three groups: the name, the argument
#: specification and the body.  The etoolbox ``...x`` spellings do not: they take
#: a name, an optional count, an optional default and then the body.
_DOCUMENT_COMMAND = frozenset(
    {
        "DeclareDocumentCommand",
        "NewDocumentCommand",
        "RenewDocumentCommand",
        "ProvideDocumentCommand",
    }
)

_LOW_LEVEL_DEFINITION = frozenset({"def", "gdef", "edef", "xdef"})

#: Definitions whose body is prose but whose name is not, in two parts.
_ENVIRONMENT_DEFINITION = frozenset({"newenvironment", "renewenvironment"})

#: ``\newtheorem{thm}{Theorem}[section]`` - an argument order that is neither of
#: the other shapes.
_THEOREM_DEFINITION = frozenset({"newtheorem"})


def _without_definitions(text: str) -> str:
    """`text` with every macro definition cut out, body included.

    ``included_files`` reads the raw source, and a body like ``\\input{#1}``
    names no file - but it was reported as one, under the name ``#1``, while the
    definition was also still in the prose.  `to_text` cuts bodies out through
    ``_definition_end``; this runs the same cut over the raw source so a reader
    that does not convert first gives the same answer.
    """
    out: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        if text[index] != "\\":
            out.append(text[index])
            index += 1
            continue
        end = index + 1
        while end < length and _is_letter(text[end]):
            end += 1
        name = text[index + 1 : end]
        if name not in _DEFINITION:
            out.append(text[index])
            index += 1
            continue
        index = _definition_end(text, name, end)
        out.append(" ")
    return "".join(out)


#: Commands whose first argument names something the reader never sees, and
#: whose second argument is the author's prose.  `\\captionof` is the caption
#: package's way of titling a float that is not a float - the one spelling a
#: thesis uses for a table set inside a paragraph - and it was not in any table,
#: so the unknown-command branch dropped the name and kept both arguments.
#: Measured before this set had them: `\\captionof{table}{We collected 154,391
#: examples.}` converted to `tableWe collected 154,391 examples.`, and because
#: that is not the sentence the page holds, `draft` proposed nothing at all -
#: a verbatim citation reported as "0 claim block(s) proposed".  Same shape for
#: `\\rotatebox{90}{...}` -> `90We collected ...` on a rotated figure label and
#: `\\hyperref[sec:data]{...}` -> `[sec:data]We collected ...`.
#:
#: Commands with one argument that is not prose (a colour, a URL, a scale, a
#: width) followed by one that is.  Neither ``_KEEP_ARGUMENT`` nor
#: ``_DROP_ARGUMENT`` describes them, so they used to fall through to the
#: unknown-command branch, which drops the name and keeps everything else: the
#: colour was left glued in front of the word, and ``\href{https://x}{this
#: paper}`` became ``https://xthis paper``.  Measured before this set existed:
#: ``\textcolor{red}{small}`` -> ``redsmall``, ``\scalebox{2}{big}`` -> ``2big``,
#: ``\parbox{3cm}{boxed}`` -> ``3cmboxed``, ``\href{http://x}{shown}`` ->
#: ``http://xshown``.  That text is what ``draft`` proposes as the claim, so the
#: proposal was built on a sentence the paper does not contain.
_SKIP_FIRST_ARGUMENT = frozenset(
    {
        "textcolor",
        "colorbox",
        "fcolorbox",
        "scalebox",
        "resizebox",
        "parbox",
        "hyperlink",
        "href",
        "foreignlanguage",
        "multicolumn",
        # The caption package's float-less caption and the graphics package's
        # rotation each take one name before the text the reader sees.
        # `\captionof*` needs no entry of its own: the scanner stops the command
        # name at the `*` and `_skip_optional_args` consumes it, so both
        # spellings arrive here as `captionof`.  Listing `captionof*` as well
        # was a name no lookup could ever produce - a dead line that read like
        # coverage.
        "captionof",
        "rotatebox",
        "hyperref",
    }
)

#: How many leading arguments of each `_SKIP_FIRST_ARGUMENT` command are not
#: prose.  `\parbox[c][2cm]{3cm}{text}` and `\resizebox{2}{!}{text}` take one
#: more than the rest, and `\multicolumn{2}{c}{text}` is a table cell whose text
#: is the third argument - skipping only the span left the alignment `c` glued to
#: the cell, which measured as ``cwide text``.
_SKIP_ARGUMENT_COUNT = {"fcolorbox": 2, "resizebox": 2, "multicolumn": 2}

#: Commands that spell their name in the optional argument *instead of* the
#: first braced one.  ``\hyperref[label]{text}`` and ``\hyperref{url}{text}``
#: both take exactly one argument that is not prose, but not the same one:
#: skipping a braced argument after a bracket ate the text and left an empty
#: sentence, which measured as ``\hyperref[sec:data]{We collected 154,391
#: examples.}`` converting to nothing at all - a worse outcome than the leak
#: this set was built for, because the words disappeared instead of growing.
_OPTIONAL_IS_THE_NAME = frozenset({"hyperref"})

#: Commands with no prose argument at all, and how many braced arguments each
#: takes.  Every one of these fell through to "keep whatever it wraps", which
#: is right for a wrapper around a sentence and wrong for a command that names a
#: counter, a length, a style or a registry key: the name was pasted into the
#: prose.  Measured before this set existed:
#:
#:   \setcounter{page}{3}We collected 40,688 examples.
#:       -> ``3We collected 40,688 examples.``
#:   \pagestyle{fancy} This chapter argues so.  -> ``fancy This chapter argues so.``
#:   \setlength{\parindent}{2em} Indented.       -> ``2em Indented.``
#:   \rule{3cm}{0.4pt} between words           -> ``0.4pt`` between the words
#:   \usetikzlibrary{arrows.meta} Body.         -> ``arrows.meta Body.``
#:
#: The digit case is the one that costs an author something: the stray ``3``
#: becomes the first character of the sentence `draft` proposes a claim for, so
#: the claim block it writes reads ``3We collected 40,688 examples``.  A count is
#: not decoration - it changes the sentence.
_DROP_ALL_ARGUMENTS = {
    "setcounter": 2,
    "addtocounter": 2,
    "stepcounter": 1,
    "refstepcounter": 1,
    "setlength": 2,
    "addtolength": 2,
    "settowidth": 2,
    "pagestyle": 1,
    "thispagestyle": 1,
    "pagenumbering": 1,
    "markboth": 2,
    "markright": 1,
    "addcontentsline": 3,
    "usetikzlibrary": 1,
    "graphicspath": 1,
    "captionsetup": 1,
    "selectlanguage": 1,
    "newcounter": 1,
    "phantom": 1,
    "hphantom": 1,
    "vphantom": 1,
    "index": 1,
    "glossary": 1,
    "DeclareMathOperator": 2,
    "rule": 2,
    "citeindextype": 1,
    "pdfbookmark": 2,
    "definelabel": 2,
    # `\footnotemark[1]` has no prose argument at all: the number is a pointer
    # to a note written elsewhere, and the fallthrough left the bracket in the
    # sentence as `[1]`.
    "footnotemark": 0,
    # The Chinese LaTeX stacks - ctex, xeCJK, CJKutf8 - name fonts, sizes and
    # registry codes, and none of those is a word of the thesis.  Measured on a
    # ctexart manuscript before these lines existed: `{\zihao{5} 相关研究 ...}`
    # converted to `5 相关研究 ...`, so `draft` wrote a claim whose text opens
    # with the point size.  `\setCJKmainfont{SimSun}` left the font name,
    # `\ctexset{section/format=...}` left `section/format=`, and
    # `\CTEXsetup[format=...]{section}` left both the bracket and the word.
    "zihao": 1,
    "CJKfamily": 1,
    "CJK": 1,
    "chinese": 1,
    "fontsize": 2,
    "linespread": 1,
    "setCJKmainfont": 1,
    "setCJKsansfont": 1,
    "setCJKmonofont": 1,
    "xeCJKsetup": 1,
    "xeCJKDeclareCharClass": 2,
    "ctexset": 1,
    "CTEXsetup": 1,
    "CTEXoptions": 1,
}

#: Commands that keep their first braced argument (prose) and drop the rest.
#: ``\texorpdfstring{TeX text}{PDF text}`` carries the same words twice; keeping
#: both said them twice, once in a form the reader never sees.
_KEEP_FIRST_ARGUMENT = frozenset({"texorpdfstring"})

#: How many braced arguments each environment takes before its body starts.
#:
#: The converter read the environment name out of `\begin{...}` and let
#: everything after it fall into the stream as prose, so a width or a column
#: count became a word: `\begin{spacing}{1.5}` converted to `'1.5
#: We collected ...'`, and `draft` glued the figure to the next line - there is
#: no full stop between them - and proposed
#:
#:     quote: |
#:       1.5 We collected 40,688 examples from the corpus ...
#:
#: with `confidence: medium` where the same sentence outside the environment
#: earns `high`.  Pasted back, that block is `[high] quote-fuzzy` **and**
#: `[high] number-absent-in-quote: the quote says 1.5 but page 1 does not
#: contain that number` - two accusations against a sentence the source prints
#: verbatim and a number the author never typed.
_ENVIRONMENT_ARGUMENTS = {
    "minipage": 1,
    "multicols": 1,
    "multicols*": 1,
    "spacing": 1,
    "column": 1,
    "column*": 1,
    "overlaycolumn": 1,
    "adjustbox": 1,
    "wrapfigure": 2,
    "wraptable": 2,
    "subfigure": 1,
    "subtable": 1,
    "list": 2,
}

#: Environments whose leading `[..]` is a placement or a list option, not
#: prose.  `theorem` and its relatives are deliberately absent: their
#: `[Main result]` names the result in words the author chose, and that reads
#: as text already.
_ENVIRONMENT_OPTIONAL = frozenset(
    {
        "figure",
        "figure*",
        "table",
        "table*",
        "algorithm",
        "algorithm*",
        "algorithmic",
        "minipage",
        "adjustbox",
        "itemize",
        "enumerate",
        "description",
    }
)

#: Beamer environments whose leading `<..>` is an overlay specification.
_ENVIRONMENT_OVERLAY = frozenset(
    {
        "onlyenv",
        "visibleenv",
        "uncoverenv",
        "actionenv",
        "columns",
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


def _restore_dropped(text: str, bodies: list[str]) -> tuple[str, list[tuple[int, int]]]:
    """Put back the literal characters `_drop_inline_verbatim` took out.

    The spans are the other half of the answer.  TeX prints a ``\\verb`` body
    literally, so ``\\verb|%|`` has to reach the output as a percent sign and
    ``\\verb|\\textit{x}|`` as visible backslashes - but the *same* body is a
    specimen to every reader downstream, and `draft` read the restored
    ``\\verb|\\citep{ghost}|`` as a citation the author made, then told them
    their own example was missing a paper.  Reporting where each body landed
    lets the caller blank exactly what was displayed, instead of trying to
    recognise it again from the characters - which is the guess that failed.
    """
    if not bodies:
        return text, []
    pattern = re.compile(re.escape(_DROPPED_MARK) + r"(\d+)" + re.escape(_DROPPED_MARK))
    out: list[str] = []
    spans: list[tuple[int, int]] = []
    cursor = 0
    landed = 0
    for found in pattern.finditer(text):
        out.append(text[cursor : found.start()])
        landed += found.start() - cursor
        body = bodies[int(found.group(1))]
        spans.append((landed, landed + len(body)))
        out.append(body)
        landed += len(body)
        cursor = found.end()
    out.append(text[cursor:])
    return "".join(out), spans


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


def _pandoc_multi(arguments: str) -> str:
    """The same marker, for a command that takes one group per source."""
    names: list[str] = []
    for match in _MULTI_ARGUMENT.finditer(arguments):
        names.extend(name.strip() for name in match.group("keys").split(",") if name.strip())
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


def _without_literal_bodies(text: str) -> str:
    r"""Blank out the body of every environment whose content TeX only shows.

    `included_files` reads the raw source, and the raw source holds the listing
    that *demonstrates* `\input`.  A name written there is an example, not a
    file, so reporting it as one makes the warning false in the one place the
    tool points the author at.  Bodies are replaced by a single space rather than
    deleted, so no two words on either side of an environment get joined.

    An unclosed environment blanks the rest of the document: a file that stops
    inside a listing has nothing after it that TeX executed either.
    """
    if not _LITERAL_BEGIN.search(text):
        return text
    out: list[str] = []
    index = 0
    for match in _LITERAL_BEGIN.finditer(text):
        if match.start() < index:
            continue
        close = _environment_close(text, match.end(), match.group("name"))
        out.append(text[index : match.end()])
        if close is None:
            index = len(text)
            break
        out.append(" ")
        index = close
    out.append(text[index:])
    return "".join(out)


def _environment_close(text: str, start: int, name: str) -> int | None:
    r"""Index of the ``\end{name}`` that closes a verbatim block, or None.

    A verbatim body is literal, so nesting is not possible and the first
    ``\end{name}`` wins. Returning None means the block is never closed, and the
    caller then leaves the document alone rather than guessing where it stops.
    """
    closer = re.compile(r"\\end\s*\{" + re.escape(name) + r"\}")
    found = closer.search(text, start)
    return None if found is None else found.start()


_CAPTION = re.compile(r"\\caption\*?")


def _shown_not_written(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Ranges inside ``text[start:end]`` whose content TeX only displays.

    A paper about writing tables may print ``\\caption{...}`` inside a
    ``verbatim`` block to show the reader the syntax.  That is an example, not a
    caption of this table, and lifting it would put a sentence on the page that
    the author never wrote there.
    """
    ranges: list[tuple[int, int]] = []
    for match in _LITERAL_BEGIN.finditer(text, start, end):
        close = _environment_close(text, match.end(), match.group("name"))
        ranges.append((match.start(), end if close is None else min(close, end)))
    return ranges


def _captions_inside(text: str, start: int, end: int, notes: list[str] | None) -> str:
    """Convert the captions written in ``text[start:end]``, joined by newlines."""
    shown = _shown_not_written(text, start, end)
    parts: list[str] = []
    cursor = start
    while True:
        match = _CAPTION.search(text, cursor, end)
        if match is None:
            break
        if any(lo <= match.start() < hi for lo, hi in shown):
            cursor = match.end()
            continue
        group_start = _skip_optional_args(text, match.end())
        close = _group_end(text, group_start)
        if close < 0 or close > end:
            cursor = match.end()
            continue
        body = _convert(text[group_start + 1 : close - 1], notes).strip()
        if body:
            parts.append(body)
        cursor = close
    return ("\n\n".join(parts) + "\n\n") if parts else ""


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


def _skip_space(text: str, start: int) -> int:
    """Index of the first non-blank character at or after `start`."""
    index = start
    while index < len(text) and text[index] in " \t\n\r":
        index += 1
    return index


def _unreadable(cursor: int) -> int:
    """Where reading stops when a definition cannot be read to its end.

    Answering ``len(text)`` here deleted the rest of the document: measured on
    ``A. \\newcommand The grammar is large.`` the sentence came out as ``A.``.
    A definition this reader cannot follow is a definition it should leave
    alone - the source then shows up in the prose, which an author can see,
    instead of vanishing, which they cannot.
    """
    return cursor


def _definition_end(text: str, name: str, start: int) -> int:
    """Index just past the definition of `name` that follows `start`.

    Three shapes, and each has to be read to its end: a definition whose body is
    left in the stream is read as a sentence, so ``\\newcommand{\\see}[1]{see
    \\citep{#1}}`` contributed a citation to the key ``#1`` and swallowed the
    real call at every use site.
    """
    cursor = _skip_space(text, start)
    if cursor < len(text) and text[cursor] == "*":
        # ``\newcommand*{\x}{body}`` is the same command as ``\newcommand``:
        # the star only says the definition must not be \long.  Without this
        # line the next character is not a brace, ``_group_end`` answers -1,
        # and the fallthrough below returns ``len(text)`` - the whole rest of
        # the document became part of a macro that was never called.  Measured
        # on ``A. \newcommand*{\x}{y} The grammar is large.``: the sentence
        # came out as ``A.`` and the 32 characters after the definition were
        # gone, with no finding to say so.
        cursor = _skip_space(text, cursor + 1)
    if name in _LOW_LEVEL_DEFINITION:
        # `\def\name#1#2{body}`: the name is not in braces, and the parameter
        # text runs up to the body's opening brace.
        opening = text.find("{", cursor)
        if opening < 0:
            return _unreadable(cursor)
        group = _group_end(text, opening)
        return group if group > 0 else _unreadable(cursor)
    if name in _THEOREM_DEFINITION:
        # `\newtheorem{name}[counter]{Printed Name}[within]`.
        group = _group_end(text, cursor)
        if group < 0:
            return _unreadable(cursor)
        cursor = _skip_optional_args(text, group)
        group = _group_end(text, cursor)
        if group < 0:
            return cursor
        return _skip_optional_args(text, group)
    group = _group_end(text, cursor)
    if group < 0:
        return _unreadable(cursor)
    cursor = _skip_optional_args(text, group)
    if name in _DOCUMENT_COMMAND:
        # ``\\NewDocumentCommand{\\x}{m}{Body #1}``: name, argument
        # specification, body.  Reading only the first two left the body in the
        # prose, so ``\\NewDocumentCommand{\\seecite}{m}{see \\citep{#1}}``
        # contributed the words ``see [@#1]`` to the text and `draft` reported a
        # citation to the key ``#1`` -- a source the paper never cites, offered
        # to the author to paste.
        for _ in range(2):
            group = _group_end(text, cursor)
            if group < 0:
                return cursor
            cursor = _skip_optional_args(text, group)
        return cursor
    if name in _ENVIRONMENT_DEFINITION:
        for _ in range(2):
            group = _group_end(text, cursor)
            if group < 0:
                return cursor
            cursor = _skip_optional_args(text, group)
        return cursor
    group = _group_end(text, cursor)
    return group if group > 0 else cursor


def _conditional_span(text: str, start: int) -> tuple[int, int, int] | None:
    """Where the conditional opened before `start` ends.

    Returns ``(false_end, else_at, fi_end)``: the body TeX skips runs from
    `start` to ``false_end``, ``else_at`` is the position of the \\else that
    turns the rest live (``-1`` when there is none), and ``fi_end`` is just
    past the matching \fi.  ``None`` means the conditional never closes,
    which TeX also treats as running to the end of the file.
    """
    depth = 0
    index = start
    length = len(text)
    else_at = -1
    while index < length:
        if text[index] != "\\":
            index += 1
            continue
        end = index + 1
        while end < length and _is_letter(text[end]):
            end += 1
        name = text[index + 1 : end]
        if not name:
            index += 2
            continue
        if name == "fi":
            if depth == 0:
                return (else_at if else_at >= 0 else index), else_at, end
            depth -= 1
        elif name == "else":
            if depth == 0 and else_at < 0:
                else_at = index
        elif name in _TEX_CONDITIONAL:
            depth += 1
        index = end
    return None


def _without_false_branches(text: str) -> str:
    """`text` with every `\\iffalse ... \fi` body cut out.

    `included_files` reads the raw source rather than the converted text, so
    a `\\input` inside a dead branch was reported as a file the paper reads
    while `to_text` never opened it.  The two readers have to agree about
    which text is real, and the converted one already knows.
    """
    out: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        if text[index] != "\\":
            out.append(text[index])
            index += 1
            continue
        end = index + 1
        while end < length and _is_letter(text[end]):
            end += 1
        name = text[index + 1 : end]
        if name == "if" and end < length and text[end] in "01":
            name = "if" + text[end]
            end += 1
        if name not in _CONDITIONAL_FALSE:
            out.append(text[index])
            index += 1
            continue
        span = _conditional_span(text, end)
        if span is None:
            break
        _, else_at, fi_end = span
        if else_at >= 0:
            out.append(_without_false_branches(text[else_at:fi_end]))
        index = fi_end
    return "".join(out)


def _convert(text: str, notes: list[str] | None = None) -> str:
    """Convert one stretch of LaTeX (no comment stripping, no preamble).

    ``notes`` collects the bodies of note commands (``\footnote`` and friends)
    instead of leaving them where they were written: a note's words are the
    author's, but splicing them into the sentence the note hangs on produced
    text no paper contains - ``The method works\footnote{See ...}`` became
    ``The method worksSee ...``, and `draft` proposed that as the claim.  The
    body is still converted, so its citations still count; it just stops
    interrupting.
    """
    out: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]

        if char == "\\":
            nxt = text[index + 1] if index + 1 < length else ""
            if _is_letter(nxt):
                end = index + 1
                while end < length and _is_letter(text[end]):
                    end += 1
                name = text[index + 1 : end]
                if name in _HEADING:
                    cursor = _skip_optional_args(text, end)
                    group = _group_end(text, cursor)
                    if group > 0:
                        title = _convert(text[cursor + 1 : group - 1], notes).strip()
                        out.append("\n\n" + title + "\n\n")
                        index = group
                        continue
                    index = end
                    continue
                if name in _SEPARATE_ARGUMENT:
                    cursor = _skip_optional_args(text, end)
                    group = _group_end(text, cursor)
                    if group > 0:
                        body = _convert(text[cursor + 1 : group - 1], notes).strip()
                        if notes is not None and body:
                            notes.append(body)
                        index = group
                        continue
                    index = end
                    continue
                if name in _KEEP_ARGUMENT:
                    cursor = _skip_optional_args(text, end)
                    group = _group_end(text, cursor)
                    if group > 0:
                        out.append(_convert(text[cursor + 1 : group - 1], notes))
                        index = group
                        continue
                    index = end
                    continue
                if name in _SKIP_FIRST_ARGUMENT:
                    # Skip the arguments that are not prose, keep the last one.
                    # `fcolorbox` and `resizebox` take two, the rest take one;
                    # both counts are handled by skipping until an argument is
                    # followed by no further argument of its own.
                    cursor = _skip_optional_args(text, end)
                    skip = _SKIP_ARGUMENT_COUNT.get(name, 1)
                    if name in _OPTIONAL_IS_THE_NAME and "[" in text[end:cursor]:
                        skip -= 1
                    for _ in range(skip):
                        group = _group_end(text, cursor)
                        if group < 0:
                            break
                        cursor = _skip_optional_args(text, group)
                    group = _group_end(text, cursor)
                    if group > 0:
                        out.append(_convert(text[cursor + 1 : group - 1], notes))
                        index = group
                        continue
                    index = cursor
                    continue
                if name in _DROP_ALL_ARGUMENTS:
                    # No argument here is prose: the command names a counter, a
                    # length, a style or a registry key.  Leaving any of them to
                    # the fallthrough pasted the name into the sentence.
                    cursor = _skip_optional_args(text, end)
                    for _ in range(_DROP_ALL_ARGUMENTS[name]):
                        group = _group_end(text, cursor)
                        if group < 0:
                            break
                        cursor = _skip_optional_args(text, group)
                    index = max(cursor, end)
                    continue
                if name in _KEEP_FIRST_ARGUMENT:
                    # `\texorpdfstring{TeX text}{PDF text}` says the same words
                    # twice; only the first is in the body.
                    cursor = _skip_optional_args(text, end)
                    group = _group_end(text, cursor)
                    if group > 0:
                        out.append(_convert(text[cursor + 1 : group - 1], notes))
                        rest = _skip_optional_args(text, group)
                        second = _group_end(text, rest)
                        index = second if second > 0 else group
                        continue
                    index = end
                    continue
                if name == "if" and end < length and text[end] in "01":
                    name = "if" + text[end]
                    end += 1
                if name in _CONDITIONAL_FALSE or name in _CONDITIONAL_TRUE:
                    # Dead text is not text: a commented-out citation is not a
                    # citation, and a file named inside one is not a file this
                    # paper reads.  Live text keeps its body and loses the
                    # marker, which is what the fallthrough failed to do for
                    # the marker's name.
                    span = _conditional_span(text, end)
                    if span is None:
                        # Unterminated.  TeX runs a conditional to the end of
                        # the file, so a dead body swallows the rest and a live
                        # one is converted to the end - the same rule, applied
                        # to whichever kind of body this is.
                        if name in _CONDITIONAL_TRUE:
                            out.append(_convert(text[end:], notes))
                        index = length
                        continue
                    false_end, else_at, fi_end = span
                    if name in _CONDITIONAL_TRUE:
                        if else_at >= 0:
                            out.append(_convert(text[end:else_at], notes))
                        else:
                            out.append(_convert(text[end:false_end], notes))
                    elif else_at >= 0:
                        out.append(_convert(text[else_at:fi_end], notes))
                    index = fi_end
                    continue
                if name in _BRANCH_COMMAND:
                    # The test is metadata, the branches are the author's own
                    # text.  Keeping the test glued it to the first branch,
                    # and keeping the branches flush glued them to each other.
                    cursor = _skip_optional_args(text, end)
                    if name in _BRANCH_BARE_TEST:
                        # ``\\ifdef\\foo{yes}{no}``: the test is a bare control sequence, so step
                        # over the token before counting brace groups.
                        while cursor < length and text[cursor] == BACKSLASH:
                            cursor += 1
                        while cursor < length and text[cursor].isalpha():
                            cursor += 1
                    for _ in range(_BRANCH_COMMAND[name]):
                        group = _group_end(text, cursor)
                        if group < 0:
                            break
                        cursor = _skip_optional_args(text, group)
                    for number in range(2):
                        group = _group_end(text, cursor)
                        if group < 0:
                            break
                        if number:
                            # Each branch is a whole piece of prose and at most
                            # one of them is ever typeset, so they are joined by
                            # a space.  Written flush,
                            # ``{We report five}{We report these} results`` measured as
                            # ``We report fiveWe report these results``: a token (``fiveWe``) that is in
                            # neither branch, in the sentence ``draft`` offers the author to
                            # paste.  Two citation branches were joined the same
                            # way, ``[@no][@yes]``.
                            out.append(" ")
                        out.append(_convert(text[cursor + 1 : group - 1], notes))
                        cursor = group
                    index = cursor
                    continue
                if name in _DEFINITION:
                    # A macro body is a template, not a sentence.  Leaving it in
                    # invented citations that the paper never makes and turned
                    # `\seecite{knuth}` into a bare word.
                    index = _definition_end(text, name, end)
                    continue
                if name in _INCLUDE_ARGUMENTS:
                    # The file name is not prose.  Drop the arguments whole;
                    # `included_files` reports them separately.
                    cursor = _skip_optional_args(text, end)
                    for _ in range(_INCLUDE_ARGUMENTS[name]):
                        group = _group_end(text, cursor)
                        if group < 0:
                            break
                        cursor = _skip_optional_args(text, group)
                    index = cursor
                    continue
                if name in _DROP_ARGUMENT:
                    cursor = _skip_optional_args(text, end)
                    group = _group_end(text, cursor)
                    if group > 0:
                        index = group
                        continue
                    if name == "input":
                        # Plain TeX's brace-less form: the file name is the next
                        # word, and it is not prose.  Leaving it in glued a path
                        # into the sentence `draft` reads, so the statement it
                        # proposed contained `sec_intro`.
                        bare = _BARE_INPUT.match(text, index)
                        index = bare.end() if bare else end
                        continue
                    index = end
                    continue
                if name in ("begin", "end"):
                    cursor = _skip_optional_args(text, end)
                    group = _group_end(text, cursor)
                    if group < 0:
                        index = end
                        continue
                    environment = text[cursor + 1 : group - 1].strip()
                    if name == "begin" and environment in _DROP_ENVIRONMENT:
                        after = _skip_environment(text, group, environment)
                        if environment in _CAPTIONED_ENVIRONMENT:
                            # The cells are data; the caption is a sentence.
                            out.append(_captions_inside(text, group, after, notes))
                        index = after
                        continue
                    out.append("\n\n" if environment in _BLOCK_ENVIRONMENT else "")
                    if name == "begin":
                        index = _past_environment_arguments(text, group, environment)
                    else:
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


def _skip_spaces(text: str, start: int) -> int:
    """Index just past the spaces and tabs at `start`."""
    index = start
    while index < len(text) and text[index] in " \t\r\n":
        index += 1
    return index


def _past_environment_arguments(text: str, start: int, name: str) -> int:
    """Index just past the arguments a `\begin{name}` line takes.

    `start` is just past the closing brace of the name.  An overlay
    specification, the `[..]` options a float takes and the braced arguments
    the environment declares are markup: TeX consumes them, and leaving them
    in the stream is how a width became the first word of a sentence.
    """
    index = _skip_spaces(text, start)
    if name in _ENVIRONMENT_OVERLAY and index < len(text) and text[index] == "<":
        end = _group_end(text, index, "<", ">")
        if end > 0:
            index = end
    if name in _ENVIRONMENT_OPTIONAL:
        while True:
            index = _skip_spaces(text, index)
            if index >= len(text) or text[index] != "[":
                break
            end = _group_end(text, index, "[", "]")
            if end < 0:
                return index
            index = end
    for _ in range(_ENVIRONMENT_ARGUMENTS.get(name, 0)):
        index = _skip_spaces(text, index)
        end = _group_end(text, index)
        if end < 0:
            return index
        index = end
    return index


def _skip_optional_args(text: str, start: int) -> int:
    """Skip the ``*``, ``[..]`` and whitespace before a command's argument.

    TeX does not care whether an argument touches its command, so
    ``\\input {sec/intro}`` and ``\\input{sec/intro}`` are
    the same command.  Only the touching spellings were understood:
    measured on the unpatched tree, 85 of the 104 commands whose
    arguments must not reach the prose pasted their argument into it
    when one space stood between, and ``\\input {sec/intro}``
    became ``... examples. sec/intro The end.``

    Whitespace is held pending rather than swallowed, and only spent
    when a brace group follows it.  `*` and `[..]` are different: they
    are arguments in their own right, so a command that only takes
    those - ``\\footnotemark[1]`` - must not fall back to the
    space and eat it.  A command used as a switch - ``\\bfseries
    We collected`` - has no argument at all, and the space after it
    separates two words; gluing them is a second way to lose text.
    """
    index = start
    committed = start
    while index < len(text):
        char = text[index]
        if char in " \t\r\n":
            index += 1
            continue
        if char == "*":
            index += 1
            committed = index
            continue
        if char == "[":
            group = _group_end(text, index, "[", "]")
            if group < 0:
                break
            index = group
            committed = index
            continue
        break
    if index < len(text) and text[index] == "{":
        return index
    return committed


def _plain_math(inner: str) -> str:
    """Inline math as a reader says it: `$\\\\alpha = 0.5$` becomes `= 0.5`."""
    without_commands = re.sub(r"\\[A-Za-z]+", "", inner)
    without_commands = without_commands.replace("{", "").replace("}", "")
    return without_commands.strip()


def included_files(tex: str) -> list[str]:
    """Name the files this document pulls in, in the order it pulls them.

    Both spellings of ``\\input`` count: ``\\input{sec/intro}`` and the plain
    TeX ``\\input sec/intro``.  The second one used to be invisible here while
    it was also left in the prose, so a paper split across files got a clean
    zero that mentioned neither the missing half nor the stray path.

    ``\\subfile``, ``\\import``, ``\\subimport``, ``\\includestandalone``,
    ``\\includepdf``, ``\\lstinputlisting`` and ``\\verbatiminput`` count too,
    through ``_INCLUDE_ARGUMENTS``: each of them names a file whose text was not
    read, and each used to be pasted into the prose instead of reported.

    The patterns do not overlap: ``_INCLUDE`` needs a ``{`` right after
    ``\\in…``, ``_BARE_INPUT`` needs whitespace and then a name that excludes
    ``{``, and ``_INCLUDE_COMMAND`` names seven other commands in full.
    Sorting by position therefore needs no de-duplication between them.
    """
    stripped = _without_false_branches(
        _without_definitions(
            _drop_inline_verbatim(strip_comments(_without_literal_bodies(tex)))[0]
        )
    )
    found: list[tuple[int, str]] = [
        (match.start(), match.group(1)) for match in _INCLUDE.finditer(stripped)
    ]
    found.extend(
        (match.start(), match.group("name")) for match in _BARE_INPUT.finditer(stripped)
    )
    found.extend(_other_includes(stripped))
    seen: list[str] = []
    for _, name in sorted(found):
        name = name.strip()
        if name and name not in seen:
            seen.append(name)
    return seen


def _other_includes(text: str) -> list[tuple[int, str]]:
    """The file names in ``_INCLUDE_ARGUMENTS``, with ``\\import`` joined up.

    ``\\import{chapters/}{one}`` names one file, ``chapters/one``; every other
    command in the table names its file in a single argument.
    """
    found: list[tuple[int, str]] = []
    for match in _INCLUDE_COMMAND.finditer(text):
        cursor = _skip_optional_args(text, match.end())
        parts: list[str] = []
        for _ in range(_INCLUDE_ARGUMENTS[match.group("name")]):
            group = _group_end(text, cursor)
            if group < 0:
                break
            parts.append(text[cursor + 1 : group - 1])
            cursor = _skip_optional_args(text, group)
        name = "".join(parts)
        if name:
            found.append((match.start(), name))
    return found


def to_text(tex: str) -> str:
    """Convert a LaTeX document into the plain text the rest of the tool reads.

    The result keeps the paragraph structure (blank lines) and turns citations
    into ``[@key]`` so that `draft` needs no second code path for LaTeX.
    """
    return to_text_and_display(tex)[0]


def to_text_and_display(tex: str) -> tuple[str, list[tuple[int, int]]]:
    """`to_text`, plus where each displayed TeX body ended up in the result.

    An inline ``\\verb``-family body is dropped before the citation patterns
    run and put back afterwards as the characters TeX prints - so a
    ``\\verb|\\citep{ghost}|`` is not a citation in the converter, correctly.
    It was one again in `draft`, which reads the converted text: the restored
    characters came back as the LaTeX spelling, `citation_sites` recognised it,
    and the author was told their own example key has no local file.  Measured
    on a manuscript with ``\\verb|\\citep{ghost2021}|`` beside a real
    ``\\citep{paper}``: ``3 citation(s) left as comments``.

    The bodies go back **last**, after the whitespace passes: their markers
    hold no space and no newline, so no pass touched them and no pass moved
    them, and a span measured here is a span in the string the caller gets.
    Collapsing whitespace before the restore would mean measuring spans in one
    string and returning another.
    """
    body = document_body(strip_comments(tex))
    body, verbatim = _drop_inline_verbatim(body)
    body = _MULTI_CITE.sub(lambda match: _pandoc_multi(match.group("arguments")), body)
    body = _CITE.sub(lambda match: _pandoc_marker(match.group(1)), body)
    notes: list[str] = []
    text = _convert(body, notes)
    # Collapse the runs of blank lines the block environments produce.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    if notes:
        # A note is one sentence, at the foot of a page that this tool does not
        # model.  Keeping it in one block of its own means `draft` reads it as
        # a phrase the author wrote rather than as words inside a claim.
        text = text + "\n\n" + "\n\n".join(notes)
    text, displayed = _restore_dropped(text, verbatim)
    return text + "\n", displayed
