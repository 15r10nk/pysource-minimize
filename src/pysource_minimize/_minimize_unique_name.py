import ast

from ._minimize_base import MinimizeBase

prefix = "unique_name_"


class MinimizeUniqueName(MinimizeBase):

    def start(self, tree: ast.AST):
        self.used_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                self.used_names.add(node.id)

        self.name_index = 0

    def new_name(self):
        while (new_name := prefix + str(self.name_index)) in self.used_names:
            self.name_index += 1
        return new_name

    def minimize_stmt(self, stmt):
        self.minimize(stmt)

    def minimize(self, o):
        method_name = "minimize_" + type(o).__name__
        if hasattr(self, method_name):
            getattr(self, method_name)(o)
        else:
            for child in ast.iter_child_nodes(o):
                self.minimize(child)

    def minimize_Name(self, node: ast.Name):
        if node.id.startswith(prefix):
            return
        new_name = self.new_name()
        if self.try_attr(node, "id", new_name):
            self.used_names.add(new_name)
