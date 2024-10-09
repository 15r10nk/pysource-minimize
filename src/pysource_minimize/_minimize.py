from __future__ import annotations

import ast
import warnings
from collections.abc import Callable

from ._minimize_base import equal_ast
from ._minimize_structure import MinimizeStructure
from ._minimize_value import MinimizeValue
from ._utils import parse
from ._utils import unparse


def minimize_ast(
    original_ast: ast.AST,
    checker,
    *,
    progress_callback=lambda current, total: None,
    retries=1,
) -> ast.AST:
    """
    minimzes the AST

    Args:
        ast: the ast to minimize
        checker: a function which gets the ast and returns `True` when the criteria is fullfilled.
        progress_callback: function which is called everytime the ast gets a bit smaller.
        retries: the number of retries which sould be performed when the ast could be minimized (useful for non deterministic issues)

    returns the minimized ast
    """

    last_success = 0

    current_ast = original_ast
    while last_success <= retries:
        new_ast = current_ast

        for Minimizer in (MinimizeStructure, MinimizeValue):
            minimizer = Minimizer(new_ast, checker, progress_callback)
            new_ast = minimizer.get_current_tree({})
            if minimizer.stop:
                break

        minimized_something = not equal_ast(new_ast, current_ast)

        current_ast = new_ast

        if minimized_something:
            last_success = 0
        else:
            last_success += 1

    return current_ast


class CouldNotMinimize(ValueError):
    """Raised to indicate that the source code could not be minimized."""


def minimize(
    source: str,
    checker: Callable[[str], bool],
    *,
    progress_callback: Callable[[int, int], object] = lambda current, total: None,
    retries: int = 1,
    compilable=True,
) -> str:
    """
    minimzes the source code

    Args:
        source: the source code to minimize
        checker: a function which gets the source and returns `True` when the criteria is fullfilled.
        progress_callback: function which is called everytime the source gets a bit smaller.
        retries: the number of retries which sould be performed when the ast could be minimized (useful for non deterministic issues)
        compilable: make shure that the minimized code can also be compiled and not just parsed.

    returns the minimized source
    """

    original_ast = parse(source)

    def source_checker(new_ast):
        try:
            with warnings.catch_warnings():
                source = unparse(new_ast)
                warnings.simplefilter("ignore", SyntaxWarning)
                if compilable:
                    compile(source, "<string>", "exec")
        except:
            return False

        return checker(source)

    if not source_checker(original_ast):
        raise CouldNotMinimize(
            "Source code cannot be minimized: the error failed to reproduce "
            "after roundtripping the source using `ast.parse()` and `ast.unparse()`"
        )

    minimized_ast = minimize_ast(
        original_ast,
        source_checker,
        progress_callback=progress_callback,
        retries=retries,
    )

    return unparse(minimized_ast)
