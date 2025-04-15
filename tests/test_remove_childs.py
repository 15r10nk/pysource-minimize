import ast
import hashlib
import random
import sys
from pathlib import Path
from typing import Optional

import pysource_minimize._minimize
import pytest
from pysource_codegen import generate
from pysource_minimize import minimize

from tests.utils import testing_enabled

try:
    import pysource_minimize_testing  # type: ignore
except ImportError:
    import pysource_minimize as pysource_minimize_testing

sample_dir = Path(__file__).parent / "remove_childs_samples"

sample_dir.mkdir(exist_ok=True)


def is_simple_node(node: Optional[ast.AST]):
    if node is None:
        return True

    if (
        isinstance(node, ast.Match)
        and is_simple_node(node.subject)
        and len(node.cases) == 1
        and is_simple_node(node.cases[0].pattern)
        and is_simple_node(node.cases[0].guard)
        and isinstance(node.cases[0].body, ast.Pass)
    ):
        return True

    if (
        isinstance(node, ast.MatchValue)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
    ):
        return True

    for name, field in ast.iter_fields(node):
        if (
            isinstance(field, (ast.expr, ast.stmt))
            and len([n for n in ast.walk(field) if isinstance(n, (ast.expr, ast.stmt))])
            > 1
        ):
            return False
    return True


def test_is_simple_node():
    match_value = ast.MatchValue(
        value=ast.Attribute(
            value=ast.Name(id="name_1", ctx=ast.Load()),
            attr="name_4",
            ctx=ast.Load(),
        )
    )

    node = ast.Module(
        body=[
            ast.Match(
                subject=ast.Tuple(elts=[], ctx=ast.Load()),
                cases=[
                    ast.match_case(
                        pattern=match_value,
                        body=[ast.Pass()],
                    )
                ],
            )
        ],
        type_ignores=[],
    )

    assert is_simple_node(node)
    assert is_simple_node(match_value)


def inner_nodes_of_type(node: ast.AST, node_type):
    childs = []
    for child in ast.iter_child_nodes(node):
        childs += inner_nodes_of_type(child, node_type)

    if not childs and isinstance(node, node_type):
        childs.append(node)

    return childs


def node_types(node: ast.AST):
    return {type(n) for n in ast.walk(node)}


def try_remove_childs(source):
    tree = ast.parse(source)

    for node_type in node_types(tree):
        number_of_nodes = len(inner_nodes_of_type(tree, node_type))
        print("search for:", node_type, number_of_nodes)

        def checker(source):
            new_tree = ast.parse(source)
            return number_of_nodes == len(inner_nodes_of_type(new_tree, node_type))

        with testing_enabled():
            new_source = pysource_minimize_testing.minimize(source, checker, retries=0)
        new_tree = ast.parse(new_source)

        for node in inner_nodes_of_type(new_tree, node_type):
            assert is_simple_node(node)


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

    print("ast")
    if sys.version_info >= (3, 9):
        print(ast.dump(ast.parse(source), indent=2))
    else:
        print(ast.dump(ast.parse(source)))

    try_remove_childs(source)


def generate_remove_childs():
    seed = random.randrange(0, 100000000)

    source = generate(seed, node_limit=1000, depth_limit=6)

    try:
        try_remove_childs(source)
    except:

        def checker(source):
            try:
                try_remove_childs(source)
            except Exception as e:
                return True

            return False

        min_source = minimize(source, checker)

        (
            sample_dir / f"{hashlib.sha256(min_source.encode('utf-8')).hexdigest()}.py"
        ).write_text(min_source)

        raise ValueError("new sample found")
