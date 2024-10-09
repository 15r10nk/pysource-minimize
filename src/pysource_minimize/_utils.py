import sys


if sys.version_info >= (3, 9):
    from ast import unparse
else:
    from astunparse import unparse  # type: ignore

import ast


def parse(source: str) -> ast.Module:
    if sys.version_info >= (3, 8):
        return ast.parse(source, type_comments=True)
    else:
        return ast.parse(source)


__all__ = ("unparse",)
