import ast

from ._minimize_base import MinimizeBase


class MinimizeValue(MinimizeBase):

    allow_multiple_mappings = True

    def minimize_stmt(self, stmt):
        self.minimize(stmt)

    def minimize(self, o):
        method_name = "minimize_" + type(o).__name__
        if hasattr(self, method_name):
            getattr(self, method_name)(o)
        else:
            for child in ast.iter_child_nodes(o):
                self.minimize(child)

    def minimize_Constant(self, constant: ast.Constant):
        if isinstance(constant.value, bool):
            if constant.value is True:
                self.try_attr(constant, "value", False)
        elif isinstance(constant.value, float):
            v = constant.value
            l = 0.0

            while l != v:
                m = (l + v) / 2
                if self.try_attr(constant, "value", m):
                    if v == m:
                        break
                    v = m
                else:
                    if l == m:
                        break
                    l = m

        elif isinstance(constant.value, int):
            v = constant.value
            l = 0

            while l != v:
                m = (l + v) // 2
                if self.try_attr(constant, "value", m):
                    if v == m:
                        break
                    v = m
                else:
                    if l == m:
                        break
                    l = m

        elif isinstance(constant.value, str):
            pass
