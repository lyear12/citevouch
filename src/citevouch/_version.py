"""The one place the version number is written down.

``pyproject.toml`` used to carry its own literal, and so did ``__init__.py``.
The release tool updated the first and not the second, so for four releases
``citevouch --version``, the SARIF ``driver.version`` and every ledger's
``tool_version`` said ``0.1.0`` while the wheel was something else entirely.

The file is a separate module rather than a literal in ``__init__.py`` because
setuptools reads the declared version by importing this attribute: keeping it
out of ``__init__`` means the build never pays for importing the package, and
``tools/next_version.py`` has exactly one line to rewrite.
"""

from __future__ import annotations

__version__ = "0.19.3"
