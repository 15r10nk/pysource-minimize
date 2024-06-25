import ast
import hashlib
import itertools
import random
import sys
from pathlib import Path
from typing import Any

import pysource_minimize._minimize
import pytest
from pysource_codegen import generate

from .utils import testing_enabled

try:
    import pysource_minimize_testing  # type: ignore
except ImportError:
    import pysource_minimize as pysource_minimize_testing


from pysource_minimize import minimize
from pysource_minimize._minimize import unparse


sample_dir = Path(__file__).parent / "needle_samples"

sample_dir.mkdir(exist_ok=True)

needle_name = "needle_17597"


def contains_one_needle(source):
    try:
        compile(source, "<string>", "exec")
    except:
        return False
    return needle_count(source) == 1


def needle_count(source):
    tree = ast.parse(source)

    return sum(
        isinstance(node, ast.Name) and node.id == needle_name for node in ast.walk(tree)
    )


def try_find_needle(source):
    assert contains_one_needle(source)

    with testing_enabled():
        new_source = pysource_minimize_testing.minimize(
            source, contains_one_needle, retries=0
        )

    assert new_source.strip() == needle_name


@pytest.mark.parametrize(
    "file", [pytest.param(f, id=f.stem) for f in sample_dir.glob("*.py")]
)
def test_needle(file):
    source = file.read_text()

    try:
        compile(source, file, "exec")
    except:
        pytest.skip()

    print(f"the following code can not be minimized to needle:")
    print(source)

    if sys.version_info >= (3, 9):
        print()
        print("ast:")
        print(ast.dump(ast.parse(source), indent=2))

    try_find_needle(source)


class HideNeedle(ast.NodeTransformer):
    def __init__(self, num):
        self.num = num
        self.index = 0
        self.needle_hidden = False

    def generic_visit(self, node: ast.AST) -> ast.AST:
        if isinstance(node, ast.expr):
            if self.num == self.index and not self.needle_hidden:
                self.index += 1
                self.needle_hidden = True
                print("replace", node, "with needle")
                return ast.Name(id=needle_name)
            self.index += 1

        return super().generic_visit(node)

    if sys.version_info >= (3, 10):

        def visit_Match(self, node: ast.Match) -> Any:
            node.subject = self.visit(node.subject)
            for case_ in node.cases:
                case_.body = [self.visit(b) for b in case_.body]

            return node


import sys


def generate_needle():
    seed = random.randrange(0, 100000000)
    print("seed:", seed)

    source = generate(seed, node_limit=10000, depth_limit=6)

    for i in itertools.count():
        original_tree = ast.parse(source)

        hide_needle = HideNeedle(i)
        needle_tree = hide_needle.visit(original_tree)

        if not hide_needle.needle_hidden:
            break

        try:
            needle_source = unparse(needle_tree)
            compile(needle_source, "<string>", "exec")
        except:
            print("skip this needle")
            continue

        if not contains_one_needle(needle_source):
            # match 0:
            #     case needle:
            # could be generated which can not be reduced to needle
            continue

        try:
            try_find_needle(needle_source)
        except:

            print("minimize")

            def checker(source):
                try:
                    compile(source, "<string>", "exec")
                except:
                    return False

                if needle_count(source) != 1:
                    return False
                try:
                    try_find_needle(source)
                except:
                    return True

                return False

            new_source = minimize(needle_source, checker)
            print(new_source)
            (
                sample_dir
                / f"{hashlib.sha256(new_source.encode('utf-8')).hexdigest()}.py"
            ).write_text(new_source)

            raise ValueError("new sample found")
