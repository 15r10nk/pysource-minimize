import ast
import copy
import sys
from typing import List
from typing import Union


TESTING = False


def is_block(nodes):
    return (
        isinstance(nodes, list)
        and nodes
        and all(isinstance(n, ast.stmt) for n in nodes)
    )


class StopMinimization(Exception):
    pass


class CoverageRequired(Exception):
    pass


def coverage_required():
    if TESTING:
        raise CoverageRequired()


def equal_ast(lhs, rhs):
    if type(lhs) != type(rhs):
        return False

    elif isinstance(lhs, list):
        if len(lhs) != len(rhs):
            return False

        return all(equal_ast(l, r) for l, r in zip(lhs, rhs))

    elif isinstance(lhs, ast.AST):
        return all(
            equal_ast(getattr(lhs, field), getattr(rhs, field))
            for field in lhs._fields
            if field not in ("ctx",)
        )
    else:
        return lhs == rhs
        assert False, f"unexpected type {type(lhs)}"


class ValueWrapper(ast.AST):
    def __init__(self, value=None):
        self.value = value

    def __repr__(self):
        return f"ValueWrapper({self.value!r})"

    def __eq__(self, other):
        return self.value == other


def arguments(
    node: Union[ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda]
) -> List[ast.arg]:
    args = node.args
    l = [*args.args, args.vararg, *args.kwonlyargs, args.kwarg]

    if sys.version_info >= (3, 8):
        l += args.posonlyargs

    return [arg for arg in l if arg is not None]


class MinimizeBase:
    allow_multiple_mappings = False

    def __init__(self, original_ast, checker, progress_callback):
        self.checker = checker
        self.progress_callback = progress_callback
        self.stop = False

        # duplicate nodes like ast.Load()
        class UniqueObj(ast.NodeTransformer):
            def visit(self, node):
                if not node._fields:
                    return type(node)()
                return super().visit(node)

        self.original_ast = UniqueObj().visit(copy.deepcopy(original_ast))

        self.original_nodes_number = self.nodes_of(self.original_ast)

        def wrap(value):
            nonlocal i
            if isinstance(value, ast.AST):
                return value
            elif isinstance(value, list):
                return [wrap(e) for e in value]
            elif isinstance(value, (type(None), int, str, bytes)):
                return ValueWrapper(value)
            else:
                assert False

        for node in ast.walk(self.original_ast):
            for name, value in ast.iter_fields(node):
                if (type(node).__name__, name) in [
                    ("arguments", "kw_defaults"),
                    ("Nonlocal", "names"),
                    ("Global", "names"),
                    ("MatchClass", "kwd_attrs"),
                ]:
                    setattr(node, name, wrap(value))

        for i, node in enumerate(ast.walk(self.original_ast)):
            node.__index = i

        self.replaced = {}

        try:
            if not self.checker(self.get_ast(self.original_ast)):
                raise ValueError("checker return False: nothing to minimize here")

            self.minimize_stmt(self.original_ast)
        except StopMinimization:
            self.stop = True

    def index_of(self, node):
        return node.__index

    def get_ast(self, node, replaced={}):
        replaced = {**self.replaced, **replaced}

        tmp_ast = copy.deepcopy(node)
        node_map = {n.__index: n for n in ast.walk(tmp_ast)}

        if TESTING:
            for a, b in zip(ast.walk(tmp_ast), ast.walk(node)):
                assert a.__index == b.__index

            unique__index = {}
            for n in ast.walk(tmp_ast):
                assert n.__index not in unique__index, (n, unique__index[n.__index])
                unique__index[n.__index] = n

            for node in ast.walk(tmp_ast):
                for field in node._fields:
                    assert hasattr(
                        node, field
                    ), f"{node.__class__.__name__}.{field} is not defined"

        def replaced_node(node):
            if not isinstance(node, ast.AST):
                return node
            if not hasattr(node, "_MinimizeBase__index"):
                return node
            i = node.__index
            while i in replaced:
                i = replaced[i]
                assert isinstance(i, (int, type(None), ast.AST)), (node, i)
            if i is None:
                return None
            if isinstance(i, ValueWrapper):
                return i.value
            if isinstance(i, ast.AST):
                return i
            result = node_map[i]

            if isinstance(result, ValueWrapper):
                result = result.value

            return result

        def replaced_nodes(nodes, name):
            def replace(l):
                for i in l:
                    if i not in replaced:
                        yield node_map[i]
                    else:
                        next_i = replaced[i]
                        if isinstance(next_i, int):
                            yield from replace([next_i])
                        elif isinstance(next_i, list):
                            yield from replace(next_i)
                        elif isinstance(next_i, ast.AST):
                            yield next_i
                        elif next_i is None:
                            yield None
                        else:
                            raise TypeError(type(next_i))

            if not all(isinstance(n, ast.AST) for n in nodes):
                return nodes

            block = is_block(nodes)

            result = list(replace([n.__index for n in nodes]))
            result = [e.value if isinstance(e, ValueWrapper) else e for e in result]

            if not result and block and name not in ("orelse", "finalbody"):
                return [ast.Pass()]

            if block:
                result = [ast.Expr(r) if isinstance(r, ast.expr) else r for r in result]

            return result

        def map_node(node):
            for name, child in ast.iter_fields(node):
                if (
                    hasattr(node, "_MinimizeBase__index")
                    and (node.__index, name) in replaced
                ):
                    setattr(node, name, replaced[(node.__index, name)])
                elif isinstance(child, list):
                    setattr(node, name, replaced_nodes(child, name))
                else:
                    setattr(node, name, replaced_node(child))
            for child in ast.iter_child_nodes(node):
                map_node(child)

        # TODO: this could be optimized (copy all, reduce) -> (generate new ast nodes)
        map_node(tmp_ast)

        if TESTING:
            for node in ast.walk(tmp_ast):
                for field in node._fields:
                    assert hasattr(
                        node, field
                    ), f"{node.__class__.__name__}.{field} is not defined"

                for field, value in ast.iter_fields(node):
                    if isinstance(value, list):
                        assert not any(isinstance(e, ValueWrapper) for e in value)
                    else:
                        assert not isinstance(value, ValueWrapper)

                if isinstance(node, ast.arguments):
                    assert len(node.kw_defaults) == len(node.kwonlyargs)
                    if sys.version_info >= (3, 8):
                        assert len(node.defaults) <= len(node.posonlyargs) + len(
                            node.args
                        )

        return tmp_ast

    def get_current_node(self, ast_node):
        return self.get_ast(ast_node)

    def get_current_tree(self, replaced):
        tree = self.get_ast(self.original_ast, replaced)
        ast.fix_missing_locations(tree)
        return tree

    @staticmethod
    def nodes_of(tree):
        return len(list(ast.walk(tree)))

    def try_with(self, replaced={}):
        """
        returns True if the minimization was successfull
        """

        if TESTING and not self.allow_multiple_mappings:
            double_defined = self.replaced.keys() & replaced.keys()
            assert (
                not double_defined
            ), f"the keys {double_defined} are mapped a second time"

        tree = self.get_current_tree(replaced)

        for node in ast.walk(tree):
            if isinstance(node, ast.Delete) and any(
                isinstance(target, (ast.Constant, ast.NameConstant))
                for target in node.targets
            ):
                # code like:
                # delete None
                return False

        valid_minimization = False

        try:
            valid_minimization = self.checker(tree)
        except StopMinimization:
            valid_minimization = True
            raise
        finally:
            if valid_minimization:
                self.replaced.update(replaced)
                self.progress_callback(self.nodes_of(tree), self.original_nodes_number)

        return valid_minimization

    def try_attr(self, node, attr_name, new_attr):
        return self.try_with({(node.__index, attr_name): new_attr})

    def try_node(self, old_node, new_node):
        return self.try_with({old_node.__index: new_node})

    def try_without(self, nodes):
        return self.try_with({n.__index: [] for n in nodes})

    def try_none(self, node):
        if node is None:
            return True
        return self.try_with({node.__index: None})

    def try_only(self, node, *childs) -> bool:
        for child in childs:
            if isinstance(child, list):
                if self.try_with({node.__index: [c.__index for c in child]}):
                    return True
            elif child is None:
                continue
            else:
                if self.try_with({node.__index: child.__index}):
                    return True
        return False

    def try_only_minimize(self, node, *childs):
        childs = [child for child in childs if child is not None]

        for child in childs:
            if self.try_only(node, child):
                self.minimize(child)
                return True

        for child in childs:
            self.minimize(child)
        return False

    def minimize(self, o):
        raise NotImplementedError
