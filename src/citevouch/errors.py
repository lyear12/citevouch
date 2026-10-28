"""Errors that map onto the CLI's exit codes.

Only four exit codes exist, so only two exception types are needed: a
:class:`UsageError` (exit 2, the caller did something the tool cannot act on)
and everything else, which is a bug and should surface as a traceback.
"""

from __future__ import annotations


class CitevouchError(Exception):
    """Base class, so callers can catch the tool's own failures only."""


class UsageError(CitevouchError):
    """The invocation or the project layout cannot be acted on.

    Examples: the manuscript path does not exist, a ledger is unreadable,
    ``--fail-on`` names an unknown severity.  Never a verification failure —
    those are findings with a severity, not exceptions.
    """
