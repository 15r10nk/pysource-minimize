import ast

from rich.console import Console
from rich.tree import Tree


def dump_tree(tree, extra=lambda node: ""):

    node = tree

    def report(node, tree, field_name):
        if isinstance(node, (ast.expr_context, ast.operator, ast.unaryop, ast.cmpop)):
            return

        if field_name:
            field_name = f"[blue]{field_name}[/]"

        if not isinstance(node, ast.AST):
            value = f"[green]{node!r}[/]"
            if field_name:
                tree.add(f"{field_name}: {value}")
            else:
                tree.add(value)

            return
        else:
            e = extra(node)

        type_name = f"[blue bold]{type(node).__name__}()[/]"

        if e:
            type_name += f" [yellow]{e}[/]"

        name = f"{field_name}: {type_name}" if field_name else type_name

        if isinstance(node, ast.Attribute):
            name += "(.%s)" % node.attr

        t = tree.add(name)

        for field, value in ast.iter_fields(node):
            if isinstance(value, list) and value:
                c = t.add(f"[blue]{field}[/]:")
                for v in value:
                    report(v, c, "")
            else:
                report(value, t, field)

    tree = Tree("ast")
    report(node, tree, "root")
    console = Console(color_system="standard")
    console.print(tree)
