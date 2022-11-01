import ast
import pathlib
from collections import Counter

import pytest

from pysource_minimize import minimize


def files():
    base_dir = pathlib.Path(__file__).parent.parent.parent / "executing"
    return base_dir.rglob("*.py")


def gen_params():
    for filename in files():

        text = filename.read_text()
        try:
            tree = ast.parse(text)
        except:
            pass
        c = Counter(node.id for node in ast.walk(tree) if isinstance(node, ast.Name))

        for name, nums in sorted(c.items())[:10]:
            yield pytest.param(
                filename, name, nums, id=f"{filename.stem}: {name} {nums}"
            )


@pytest.mark.parametrize("filename,name,num", gen_params())
def test_file(filename, name, num):
    print("search for:", name, num)
    filename = pathlib.Path(filename)

    tree = ast.parse(filename.read_text())

    def count(source):
        return sum(
            isinstance(node, ast.Name) and node.id == name
            for node in ast.walk(ast.parse(source))
        )

    def checker(source):
        return count(source) >= num

    new_source = minimize(filename.read_text(), checker)

    assert count(new_source) == num
