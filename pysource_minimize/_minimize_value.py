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

        elif isinstance(constant.value, (str, bytes)):

            value_type = type(constant.value)

            def try_list(l):
                if value_type is str:
                    v = value_type().join(l)
                else:
                    v = bytes(l)
                result = self.try_attr(constant, "value", v)
                return result

            def without(before, l, after):

                if try_list(before + after):
                    return []
                elif len(l) == 1:
                    return l
                else:
                    return devide(before, l, after)

            def devide(before, l, after):
                if not l:
                    return []

                mid = len(l) // 2

                a, b = l[:mid], l[mid:]
                a = without(before, a, b + after)
                b = without(before + a, b, after)
                return a + b

            devide([], list(constant.value), [])
