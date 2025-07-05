from __future__ import annotations

import ast
import warnings
from collections.abc import Callable
from pathlib import Path

from ._minimize_base import equal_ast
from ._minimize_structure import MinimizeStructure
from ._minimize_unique_name import MinimizeUniqueName
from ._minimize_value import MinimizeValue
from ._utils import parse
from ._utils import unparse

default_strategies = (MinimizeStructure, MinimizeValue, MinimizeUniqueName)


def minimize_ast(
    original_ast: ast.AST,
    checker,
    *,
    progress_callback=lambda current, total: None,
    retries=1,
    strategies=default_strategies,
) -> ast.AST:
    """
    minimizes the AST

    Args:
        ast: the ast to minimize
        checker: a function which gets the ast and returns `True` when the criteria is fulfilled.
        progress_callback: function which is called everytime the ast gets a bit smaller.
        retries: the number of retries which should be performed when the ast could be minimized (useful for non deterministic issues)

    returns the minimized ast
    """

    last_success = 0

    current_ast = original_ast
    while last_success <= retries:
        new_ast = current_ast

        for Minimizer in default_strategies:
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


def _minimize_source(
    source: str,
    checker: Callable[[str], bool],
    *,
    progress_callback: Callable[[int, int], object] = lambda current, total: None,
    retries: int = 1,
    compilable=True,
    strategies=default_strategies,
) -> str:
    """
    minimizes the source code

    Args:
        source: the source code to minimize
        checker: a function which gets the source and returns `True` when the criteria is fulfilled.
        progress_callback: function which is called everytime the source gets a bit smaller.
        retries: the number of retries which should be performed when the ast could be minimized (useful for non deterministic issues)
        compilable: make sure that the minimized code can also be compiled and not just parsed.

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
        strategies=strategies,
    )

    return unparse(minimized_ast)


def minimize(
    source: str,
    checker: Callable[[str], bool],
    *,
    progress_callback: Callable[[int, int], object] = lambda current, total: None,
    retries: int = 1,
    compilable=True,
) -> str:
    """
    minimizes the source code

    Args:
        source: the source code to minimize
        checker: a function which gets the source and returns `True` when the criteria is fulfilled.
        progress_callback: (deprecated) function which is called everytime the source gets a bit smaller.
        retries: the number of retries which should be performed when the ast could be minimized (useful for non deterministic issues)
        compilable: make sure that the minimized code can also be compiled and not just parsed.

    Warning:
        `progress_callback` is deprecated and should be implemented inside in `checker` where you can use the `len(source_code)`
        to calculate the progress.

    returns the minimized source
    """
    return _minimize_source(
        source,
        checker,
        progress_callback=progress_callback,
        retries=retries,
        compilable=compilable,
    )


def minimize_all(
    sources: dict[Path, str],
    checker: Callable[[dict[Path, str | None], Path], bool],
    *,
    retries: int = 1,
    compilable=True,
) -> dict[Path, str | None]:
    """
    minimizes multiple source codes.

    Args:
        sources: the source code to minimize
        checker: a function which gets the source and returns `True` when the criteria is fulfilled.
        retries: the number of retries which should be performed when the ast could be minimized (useful for non deterministic issues)
        compilable: make sure that the minimized code can also be compiled and not just parsed.

    Returns:
        a dict with the minimized sources. The values are `None` when the source file should be deleted
    """

    current_files: dict[Path, str | None] = dict(sources)

    def run_files(strategies, retries):
        def tree_checker(new_source: str | None):
            result = checker({**current_files, current_file: new_source}, current_file)
            return result

        for current_file in current_files.keys():
            file = current_files[current_file]
            if file is not None:
                if tree_checker(None):
                    current_files[current_file] = None
                    continue
                current_files[current_file] = _minimize_source(
                    file,
                    tree_checker,
                    retries=retries,
                    compilable=compilable,
                    strategies=strategies,
                )

    for current_file in list(current_files.keys()):
        new_files = {**current_files, current_file: None}
        if checker(new_files, current_file):
            current_files = new_files

    run_files((default_strategies[0],), 0)
    run_files(default_strategies, retries)

    return current_files
