import pytest
from pysource_minimize import minimize
import ast
import pathlib


def gen_params():
    filename = pathlib.Path("./pysource_minimize.py")

    tree=ast.parse(filename.read_text())
    names=sorted({node.id for node in ast.walk(tree) if isinstance(node,ast.Name)})
    return [(filename,name) for name in names]
    

@pytest.mark.parametrize("filename,name",gen_params())
def test_file(filename,name):
    filename = pathlib.Path(filename)

    tree=ast.parse(filename.read_text())


    def checker(source):
        return any( isinstance(node,ast.Name) and node.id==name for node in ast.walk(ast.parse(source)))

    new_source=minimize(filename.read_text(),checker)

    assert new_source==name


    




