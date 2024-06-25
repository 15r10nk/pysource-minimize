import ast
import hashlib
import random
import sys
from pathlib import Path

import pysource_minimize._minimize
import pytest
from pysource_codegen import generate
from pysource_minimize import minimize

from . import session_config
from .dump_tree import dump_tree
from tests.utils import testing_enabled

try:
    import pysource_minimize_testing  # type: ignore
except ImportError:
    import pysource_minimize as pysource_minimize_testing

sample_dir = Path(__file__).parent / "remove_one_samples"

sample_dir.mkdir(exist_ok=True)


def node_weights(source):
    tree = ast.parse(source)

    def weight(node):

        result = 1
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
                ast.arguments,
            ),
        ):
            result = 0

        if isinstance(node, (ast.GeneratorExp, ast.ListComp, ast.SetComp)):
            result = 0
        if isinstance(node, (ast.DictComp)):
            result = -2
        if isinstance(node, ast.comprehension):
            # removing comrehension removes variable and iterable
            result = -1

        if isinstance(node, (ast.Dict)):
            result = -len(node.keys) + 1
        if sys.version_info >= (3, 8) and isinstance(node, ast.NamedExpr):
            result = 0

        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                result = int(node.value) + 1
            elif isinstance(node.value, int):
                result = bin(node.value).count("1")
            elif isinstance(node.value, float):
                result = abs(int(node.value * 10)) + 1
            elif isinstance(node.value, (bytes, str)):
                result = len(node.value) + 1

        if isinstance(node, ast.FormattedValue):
            result = 0
        if isinstance(node, ast.JoinedStr):
            # work around for https://github.com/python/cpython/issues/110309
            result = -(sum(isinstance(n, ast.Constant) for n in node.values))

        if isinstance(node, ast.IfExp):
            result = -1
        if isinstance(node, ast.Subscript):
            result = 0
        if isinstance(node, ast.Index):
            result = 0

        if isinstance(node, (ast.Nonlocal, ast.Global)):
            result = len(node.names)

        # match
        if sys.version_info >= (3, 10):
            if isinstance(node, ast.MatchValue):
                result = -1
            if isinstance(node, (ast.MatchOr, ast.match_case, ast.MatchClass)):
                result = 0
            if isinstance(node, ast.Match):
                result = -1  # for the subject
            if isinstance(node, ast.MatchMapping):
                # key-value pairs can only be removed together
                result = -len(node.patterns) + 1

        # try
        if sys.version_info >= (3, 11) and isinstance(node, ast.TryStar):
            # execpt*: is invalid syntax
            result = -len(node.handlers) + 1

        if isinstance(node, ast.excepthandler):
            result = 0
            if node.name:
                result += 1

        if sys.version_info >= (3, 12):
            if isinstance(node, ast.TypeAlias):
                result = 0

        if hasattr(node, "type_comment") and node.type_comment is not None:
            result += 1

        return result

    return [(n, weight(n)) for n in ast.walk(tree)]


def count_nodes(source):
    return sum(v for n, v in node_weights(source))


def try_remove_one(source):
    node_count = count_nodes(source)

    def checker(source):
        try:
            compile(source, "<string>", "exec")
        except:
            return False

        count = count_nodes(source)

        if count == node_count - 1:
            raise pysource_minimize_testing.StopMinimization

        return count_nodes(source) >= node_count - 1

    while node_count > 1:
        # remove only one "node" from the ast at a time
        print("node_count:", node_count)

        with testing_enabled():
            new_source = pysource_minimize_testing.minimize(source, checker, retries=0)

        if session_config.verbose and False:
            print("\nnew_source:")
            print(new_source)
            tree = ast.parse(new_source)
            weights = dict(node_weights(tree))

            dump_tree(tree, lambda node: f"w={weights[node]}")

        assert count_nodes(new_source) == node_count - 1

        source = new_source

        node_count -= 1


@pytest.mark.parametrize(
    "file", [pytest.param(f, id=f.stem) for f in sample_dir.glob("*.py")]
)
def test_samples(file):

    source = file.read_text()

    try:
        compile(source, file, "exec")
    except:
        pytest.skip("the sample does not compile for the current python version")

    print("source")
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

    try_remove_one(source)


def generate_remove_one():
    seed = random.randrange(0, 100000000)

    source = generate(seed, node_limit=1000, depth_limit=6)

    try:
        try_remove_one(source)
    except:

        # find minimal source where it is not possible to remove one "node"

        def checker(source):
            try:
                try_remove_one(source)
            except Exception as e:
                return True

            return False

        min_source = minimize(source, checker)

        (
            sample_dir / f"{hashlib.sha256(min_source.encode('utf-8')).hexdigest()}.py"
        ).write_text(min_source)

        raise ValueError("new sample found")
