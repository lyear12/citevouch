"""Text this tool prints for the reader to type.

Two places build a command rather than a sentence: ``draft`` closes by naming
the ``check`` that reads the file it just wrote, and ``doctor`` names the
command that would fix each failed check.  Both are promises - the reader
copies the line into a shell - so both need the same quoting and the same rule
about which path to print.

They were written apart, and the second one drifted.  ``draft`` printed
``citevouch check claims.md`` for a project under ``proj/`` and learned to add
the ``--root`` it had used; ``doctor`` kept printing bare file names, so a
manuscript at ``paper/m.md`` produced ``citevouch draft m.md -o claims.md``,
and running that says ``manuscript m.md does not exist``.  Measured before
this module existed, from the directory holding ``paper/``::

    $ citevouch doctor --root . --manuscript paper/m.md
    [FAIL] claims  paper/m.md holds no claim blocks, ...
       -> ... `citevouch draft m.md -o claims.md`.  ...
    $ citevouch draft m.md -o claims.md
    citevouch: manuscript m.md does not exist

A helper both callers ask for cannot disagree with itself.
"""

from __future__ import annotations

# The quoting condition treats a backslash as needing quotes, and on Windows it
# is the ordinary separator rather than an exotic character.  Built through
# chr() because a literal backslash in a Python source file is one syntax
# decision away from being a different string than the one written.
_BACKSLASH = chr(92)


def shell_word(value: str) -> str:
    """A value quoted for a shell, or bare when it needs no quoting.

    The advice this tool prints is meant to be copied and run.  A path with a
    space in it would otherwise split into two arguments and fail for a reason
    that has nothing to do with the command, so the quoting is part of the
    sentence rather than an afterthought.

    The failure this prevents was measured on the ``draft`` advice: the output
    path was printed with forward slashes while ``--root`` was printed as it
    was given, so on Windows the one argument the reader had typed themselves
    was the one argument the shell ate - ``--root C:\\work\\proj`` arrived as
    ``C:workproj`` and the next command reported a directory that does not
    exist.  Quoting it costs one character pair and the two halves of the
    advice agree again.
    """
    if not value:
        return "''"
    if any(ch.isspace() for ch in value) or any(ch in value for ch in "\"'$`" + _BACKSLASH):
        return "'" + value.replace("'", "'" + _BACKSLASH + "''") + "'"
    return value


def citevouch_command(*words: str) -> str:
    """``citevouch`` followed by *words*, each quoted for a shell.

    The program name is printed as typed rather than quoted: it is not a path,
    and quoting it would read like an instruction about the shell instead of a
    command to run.
    """
    return " ".join(["citevouch", *(shell_word(word) for word in words)])


def root_words(root: str) -> list[str]:
    """The ``--root`` argument a command needs, or nothing when there is none.

    ``--root .`` is what every verb defaults to, so a reader working inside the
    project gets the short command and a reader working above it gets the one
    that works.  Printing the root only when it is not the default is also what
    keeps the advice short enough to read.
    """
    if root and root != ".":
        return ["--root", root]
    return []
