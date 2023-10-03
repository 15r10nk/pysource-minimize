import ast
import hashlib
import sys
from pathlib import Path

import pytest
from pysource_codegen import generate

from pysource_minimize import minimize

sample_dir = Path(__file__).parent / "remove_one_samples"

sample_dir.mkdir(exist_ok=True)


def node_weights(source):
    tree = ast.parse(source)

    def weight(node):

        if isinstance(
            node,
            (
                ast.Pass,
                ast.expr_context,
                ast.Expr,
                ast.boolop,
                ast.unaryop,
                ast.keyword,
                ast.withitem,
                ast.For,
                ast.AsyncFor,
                ast.BoolOp,
                ast.AnnAssign,
                ast.AugAssign,
                ast.Compare,
                ast.cmpop,
                ast.BinOp,
                ast.operator,
                ast.Assign,
                ast.Import,
                ast.Delete,
                ast.ImportFrom,
            ),
        ):
            return 0

        if isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp)):
            return 0
        if isinstance(node, (ast.DictComp)):
            return -2
        if isinstance(node, ast.comprehension):
            # removing comrehension removes variable and iterable
            return -1

        if isinstance(node, (ast.Dict)):
            return -len(node.keys) + 1
        if sys.version_info >= (3, 8) and isinstance(node, ast.NamedExpr):
            return 0

        if isinstance(node, (ast.FormattedValue, ast.JoinedStr)):
            return 0

        if isinstance(node, ast.IfExp):
            return -1
        if isinstance(node, ast.Subscript):
            return 0
        if isinstance(node, ast.Index):
            return 0

        # match
        if sys.version_info >= (3, 10):
            if isinstance(node, ast.MatchValue):
                return -1
            if isinstance(node, (ast.MatchOr, ast.match_case, ast.MatchClass)):
                return 0
            if isinstance(node, ast.Match):
                return -1  # for the subject
            if isinstance(node, ast.MatchMapping):
                # key-value pairs can only be removed together
                return -len(node.patterns) + 1

        # try
        if sys.version_info >= (3, 11) and isinstance(node, ast.TryStar):
            # execpt*: is invalid syntax
            return -len(node.handlers) + 1

        if isinstance(node, ast.excepthandler):
            return 0

        if isinstance(node, ast.arguments):
            # kw_defaults and kwonlyargs can only be removed together
            return -len(node.kw_defaults)

        return 1

    return [(n, weight(n)) for n in ast.walk(tree)]


def count_nodes(source):
    return sum(v for n, v in node_weights(source))


def try_remove_one(source):
    node_count = count_nodes(source)

    while node_count > 1:
        # remove only one "node" from the ast at a time
        new_source = minimize(
            source, lambda source: count_nodes(source) >= node_count - 1
        )

        if count_nodes(new_source) != node_count - 1:
            return False, source

        source = new_source

        node_count -= 1

    return True, ""


def test_remove_one_generate(seed):
    source = generate(seed, node_limit=1000, depth_limit=6)

    result, source = try_remove_one(source)

    if not result:
        # find minimal source where it is not possible to remove one "node"

        def checker(source):
            result, failed_source = try_remove_one(source)

            return not result

        min_source = minimize(source, checker)

        (
            sample_dir / f"{hashlib.sha256(min_source.encode('utf-8')).hexdigest()}.py"
        ).write_text(min_source)


@pytest.mark.parametrize(
    "file", [pytest.param(f, id=f.stem) for f in sample_dir.glob("*.py")]
)
def test_samples(file):

    source = file.read_text()

    try:
        compile(source, file, "exec")
    except:
        pytest.skip()

    print("source")
    print(source)

    result, source = try_remove_one(source)

    print("\nnew minimized")
    print(source)
    print("weights:")
    for n, v in node_weights(source):
        if v:
            print(f"  {n}: {v}")
    print("ast")
    if sys.version_info >= (3, 9):
        print(ast.dump(ast.parse(source), indent=2))
    else:
        print(ast.dump(ast.parse(source)))

    assert result
