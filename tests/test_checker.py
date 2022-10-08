import pytest
from pysource_minimize import minimize
import ast
import pathlib


@pytest.mark.parametrize("filename",["./pysource_minimize.py"])
def test_file(filename,subtests):
    filename = pathlib.Path(filename)

    tree=ast.parse(filename.read_text())

    names=sorted({node.id for node in ast.walk(tree) if isinstance(node,ast.Name)})


    for name in names:
        subtests.test(msg=f"search for {name}",name=name)

        def checker(source):
            return any( isinstance(node,ast.Name) and node.id==name for node in ast.walk(ast.parse(source)))

        new_source=minimize(filename.read_text(),checker)

        assert new_source==name


    




