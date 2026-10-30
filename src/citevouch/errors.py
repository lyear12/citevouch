"""Errors that map onto the CLI's exit codes.

Only four exit codes exist, so only two exception types are needed: a
:class:`UsageError` (exit 2, the caller did something the tool cannot act on)
and everything else, which is a bug and should surface as a traceback.
"""

from __future__ import annotations

import errno
import os
from pathlib import Path


class CitevouchError(Exception):
    """Base class, so callers can catch the tool's own failures only."""


class UsageError(CitevouchError):
    """The invocation or the project layout cannot be acted on.

    Examples: the manuscript path does not exist, a ledger is unreadable,
    ``--fail-on`` names an unknown severity.  Never a verification failure —
    those are findings with a severity, not exceptions.
    """


def why_not_a_file(path: Path) -> str:
    """Say what is wrong with a path that was expected to be a file.

    The three answers a reader can act on are different mistakes, so they are
    different sentences.  "does not exist" about a directory sends someone
    looking for a file they can see; "does not exist" about a path on a share
    that is not mounted sends them looking for a manuscript they never lost.
    A false sentence is worse than a vague one, because it is followed.

    Windows reports an unreachable share as ``ERROR_BAD_NETPATH`` (53) and a
    missing path as ``ERROR_FILE_NOT_FOUND`` (3), and Python maps **both** to
    ``errno.ENOENT`` — so ``Path.exists()`` cannot tell them apart and the
    distinction has to come from the raw error.  On POSIX an unreachable mount
    is ``ENETUNREACH``/``EHOSTUNREACH``/``EIO`` or ``ESTALE`` for a share that
    went away underneath a directory that still stats.

    A path that cannot be judged (permission denied, a broken symlink) falls
    back to "does not exist", because the caller is about to fail on it either
    way and guessing a reason is worse than stating the one the operation
    reported.
    """
    if path.is_dir():
        return "is a directory, not a file"
    try:
        os.stat(path)
    except OSError as exc:
        reason = _unreachable_reason(exc)
        if reason is not None:
            return reason
    return "does not exist"


#: ``error.winerror`` values that mean "the share is not there", as opposed to
#: "the file is not there".  Both arrive as ``errno.ENOENT`` on Windows.
_WINERROR_UNREACHABLE = {
    53,  # ERROR_BAD_NETPATH - the network path was not found
    67,  # ERROR_BAD_NET_NAME - the network name cannot be found
    51,  # ERROR_REM_NOT_LIST - the remote computer is not available
    1231,  # ERROR_NETWORK_UNREACHABLE
    1232,  # ERROR_HOST_UNREACHABLE
    1236,  # ERROR_CONNECTION_ABORTED
    1326,  # ERROR_LOGON_FAILURE - the share needs credentials this process lacks
    1396,  # ERROR_LOGON_TYPE_NOT_GRANTED
}

#: POSIX errno values with the same meaning.
_ERRNO_UNREACHABLE = {
    getattr(errno, name)
    for name in ("ENETUNREACH", "EHOSTUNREACH", "ECONNREFUSED", "EIO", "ESTALE")
    if hasattr(errno, name)
}


def _unreachable_reason(exc: OSError) -> str | None:
    """Return a sentence naming an unreachable location, or ``None``."""
    if getattr(exc, "winerror", None) in _WINERROR_UNREACHABLE:
        return (
            "cannot be reached (the network path is not available from here), "
            "which is not the same as missing"
        )
    if exc.errno in _ERRNO_UNREACHABLE:
        return (
            "cannot be reached (the filesystem reports it is unavailable), "
            "which is not the same as missing"
        )
    return None
