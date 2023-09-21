import ast
import hashlib
from pathlib import Path

import pytest
from pysource_codegen import generate

from pysource_minimize import minimize

sample_dir = Path(__file__).parent / "node_name_samples"

sample_dir.mkdir(exist_ok=True)


def check_sample(source, name):
    def count(source):
        return sum(
            node.id == name
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Name)
        )

    num = count(source)

    print("check", name, num)

    def checker(source):
        # print()
        # print("source:")
        # print(source)
        return count(source) >= num

    new_source = minimize(source, checker)
    assert count(new_source) == num

    # new_tree = ast.parse(new_source)
    # assert all(node.id != name for node in ast.walk(new_tree) if isinstance(node, ast.Name))


@pytest.mark.parametrize(
    "file", [pytest.param(f, id=f.stem) for f in sample_dir.glob("*.py")]
)
def test_files(file):
    name = file.stem.split("_", 1)[1]
    source = file.read_text()
    print(source)
    check_sample(source, name)


def test_file(seed):
    source = generate(seed, node_limit=10000, depth_limit=6)
    tree = ast.parse(source)

    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}

    for name in sorted(names):
        try:
            check_sample(source, name)
        except:

            print("minimize")

            def checker(source):
                try:
                    check_sample(source, name)
                except:
                    return True
                return False

            try:
                new_source = minimize(source, checker)
                (
                    sample_dir
                    / f"{hashlib.sha256(new_source.encode('utf-8')).hexdigest()}_{name}.py"
                ).write_text(new_source)
            except:
                (
                    sample_dir
                    / f"{hashlib.sha256(source.encode('utf-8')).hexdigest()}_{name}.py"
                ).write_text(source)

            raise
