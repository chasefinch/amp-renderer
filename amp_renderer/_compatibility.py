"""Compatibility helpers across supported Python versions."""

import sys

if sys.version_info >= (3, 12):  # noqa: UP036  # pragma: no cover
    from typing import override
else:  # pragma: no cover
    from collections.abc import Callable
    from typing import TypeVar

    _Method = TypeVar("_Method", bound=Callable[..., object])

    def override(method: _Method) -> _Method:  # noqa: UP047 (PEP 695 needs py3.12+)
        """Indicate that a method overrides a base class method.

        No-op backport of typing.override for Python versions before 3.12.
        """
        return method
