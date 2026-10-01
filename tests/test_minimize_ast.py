import ast

from pysource_minimize._minimize import minimize_ast


class LosesBug:
    stop = False

    def __init__(self, original_ast, checker, progress_callback):
        assert checker(original_ast)

    def get_current_tree(self, replaced):
        return ast.Expression(ast.Constant("fixed"))


class ShouldNotRun:
    def __init__(self, original_ast, checker, progress_callback):
        if not checker(original_ast):
            raise ValueError("checker return False: nothing to minimize here")
        raise AssertionError("strategy should not minimize a non-reproducing tree")


def test_minimize_ast_keeps_last_reproducing_tree_between_strategies():
    tree = ast.Expression(ast.Constant("bug"))

    result = minimize_ast(
        tree,
        lambda candidate: candidate.body.value == "bug",
        retries=0,
        strategies=(LosesBug, ShouldNotRun),
    )

    assert result.body.value == "bug"
