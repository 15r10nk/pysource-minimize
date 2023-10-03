import ast
import hashlib
import itertools
import random
from pathlib import Path

import pytest
from pysource_codegen import generate

from pysource_minimize import minimize

sample_dir = Path(__file__).parent / "needle_samples"

sample_dir.mkdir(exist_ok=True)

needle_name = "needle_17597"


def contains_one_needle(source):
    return needle_count(source) == 1


def needle_count(source):
    tree = ast.parse(source)

    return sum(
        isinstance(node, ast.Name) and node.id == needle_name for node in ast.walk(tree)
    )


def try_find_needle(source):
    assert contains_one_needle(source)

    new_source = minimize(source, contains_one_needle)
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

    print(source)
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


def generate_needle():
    seed = random.randrange(0, 100000000)

    source = generate(seed, node_limit=10000, depth_limit=6)

    for i in itertools.count():
        original_tree = ast.parse(source)

        hide_needle = HideNeedle(i)
        needle_tree = hide_needle.visit(original_tree)

        if not hide_needle.needle_hidden:
            break

        try:
            needle_source = ast.unparse(needle_tree)
            compile(needle_source, "<string>", "exec")
        except:
            print("skip this needle")
            continue

        assert contains_one_needle(needle_source)

        try:
            try_find_needle(needle_source)
        except:

            print("minimize")

            def checker(source):
                if needle_count(source) != 1:
                    return False
                try:
                    try_find_needle(source)
                except:
                    return True
                return False

            try:
                new_source = minimize(needle_source, checker)
                print(new_source)
                (
                    sample_dir
                    / f"{hashlib.sha256(new_source.encode('utf-8')).hexdigest()}.py"
                ).write_text(new_source)
            except:
                print("minimize failed")
                (
                    sample_dir
                    / f"{hashlib.sha256(needle_source.encode('utf-8')).hexdigest()}.py"
                ).write_text(source)

            raise
