import sys


if sys.version_info >= (3, 8):
    from ast import unparse
else:
    from astunparse import unparse  # type: ignore

__all__ = ("unparse",)
