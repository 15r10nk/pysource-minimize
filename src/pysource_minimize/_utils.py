import sys


if sys.version_info >= (3, 9):
    from ast import unparse
else:
    from astunparse import unparse as _unparse  # type: ignore

    def unparse(tree):
        return _unparse(tree).strip()


import ast


def parse(source: str) -> ast.Module:
    return ast.parse(source, type_comments=True)


__all__ = ("unparse",)
