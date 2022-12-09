import ast
import contextlib
import copy
import os

from rich.console import Console


@contextlib.contextmanager
def no_output():
    with open(os.devnull, "w") as f:
        with contextlib.redirect_stdout(f):
            with contextlib.redirect_stderr(f):
                yield


def is_block(nodes):
    return (
        isinstance(nodes, list)
        and nodes
        and all(isinstance(n, ast.stmt) for n in nodes)
    )


class Minimizer:
    def __init__(self, source, checker, progress_callback):

        self.checker = checker
        self.progress_callback = progress_callback

        self.original_source = source
        self.original_ast = ast.parse(source)
        self.original_nodes_number = self.nodes_of(self.original_ast)

        for i, node in enumerate(ast.walk(self.original_ast)):
            node.__index = i

        self.replaced = {}

        if not self.checker(self.original_source):
            raise ValueError("checker return False: nothing to minimize here")

        source = self.get_source({})
        if not self.checker(source):
            print("ast.unparse removes the error minimize can not help here")
            self.source = self.original_source
            return

        self.minimize_stmt(self.original_ast)

        self.source = self.get_source(self.replaced)

        console = Console()

    def get_ast(self, node, replaced={}):
        replaced = self.replaced | replaced

        tmp_ast = copy.deepcopy(node)
        node_map = {n.__index: n for n in ast.walk(tmp_ast)}

        def replaced_node(node):
            if not isinstance(node, ast.AST):
                return node
            i = node.__index
            while i in replaced:
                i = replaced[i]
                assert isinstance(i, (int, type(None))), (node, i)
            if i is None:
                return None
            return node_map[i]

        def replaced_nodes(nodes):
            def replace(l):
                for i in l:
                    if i not in replaced:
                        yield i
                    else:
                        i = replaced[i]
                        if isinstance(i, int):
                            yield from replace([i])
                        elif isinstance(i, list):
                            yield from replace(i)
                        else:
                            raise TypeError(type(i))

            if not all(isinstance(n, ast.AST) for n in nodes):
                return nodes

            block = is_block(nodes)

            l = list(replace([n.__index for n in nodes]))

            if not l and block:
                return [ast.Pass()]

            result = [node_map[i] for i in l]
            if block:
                result = [ast.Expr(r) if isinstance(r, ast.expr) else r for r in result]

            return result

        def map_node(node):
            for name, value in ast.iter_fields(node):
                if isinstance(value, list):
                    setattr(node, name, replaced_nodes(value))
                else:
                    setattr(node, name, replaced_node(value))
            for child in ast.iter_child_nodes(node):
                map_node(child)

        map_node(tmp_ast)

        return tmp_ast

    def get_source_tree(self, replaced):
        tree = self.get_ast(self.original_ast, replaced)
        ast.fix_missing_locations(tree)
        return ast.unparse(tree), tree

    def get_source(self, replaced):
        return self.get_source_tree(replaced)[0]

    @staticmethod
    def nodes_of(tree):
        return len(list(ast.walk(tree)))

    def try_with(self, replaced={}):
        """
        returns True if the minimization was successfull
        """

        source, tree = self.get_source_tree(replaced)
        try:
            compile(source, "<filename>", "exec")
        except Exception as e:
            if "assigned to before global declaration" in str(e):
                return False  # todo parse ... compile
            print(source)
            print(ast.dump(self.get_ast(self.original_ast, replaced), indent=4))
            raise

        if self.checker(source):
            self.replaced = self.replaced | replaced
            self.progress_callback(self.nodes_of(tree), self.original_nodes_number)
            return True

        return False

    def try_without(self, nodes):
        return self.try_with({n.__index: [] for n in nodes})

    def try_none(self, node):
        if node is not None:
            return self.try_with({node.__index: None})

    def try_only(self, node, child) -> bool:
        if isinstance(child, list):
            return self.try_with({node.__index: [c.__index for c in child]})
        else:
            return self.try_with({node.__index: child.__index})

    def minimize_comprehension(self, comp):
        self.minimize_expr(comp.iter)
        for if_ in comp.ifs:
            self.minimize_expr(if_)

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
        if isinstance(o, ast.expr):
            return self.minimize_expr(o)
        elif isinstance(o, ast.stmt):
            return self.minimize_stmt(o)
        elif isinstance(o, list):
            return self.minimize_list(o, self.minimize)
        else:
            raise TypeError(type(o))

    def minimize_expr(self, node):
        if isinstance(node, ast.BoolOp):
            self.minimize_list(node.values, self.minimize_expr, 1)
        elif isinstance(node, ast.Compare):
            self.try_only_minimize(node, node.left, *node.comparators)
        elif isinstance(node, ast.Subscript):
            if not self.try_only_minimize(node, node.value):
                self.minimize_expr(node.slice)
                # todo minimize slice to

        elif isinstance(node, ast.FormattedValue):
            self.minimize_expr(node.value)

        elif isinstance(node, ast.JoinedStr):
            self.minimize(node.values)
            # todo minimize values

        elif isinstance(node, ast.Slice):
            self.try_only_minimize(node, node.lower, node.upper, node.step)
        elif isinstance(node, ast.Lambda):
            self.try_only_minimize(node.body)
        elif isinstance(node, ast.UnaryOp):
            self.try_only_minimize(node, node.operand)
        elif isinstance(node, ast.BinOp):
            self.try_only_minimize(node, node.left, node.right)
        elif isinstance(node, ast.Attribute):
            self.try_only_minimize(node, node.value)
        elif isinstance(node, ast.IfExp):
            self.try_only_minimize(node, node.test, node.body, node.orelse)
        elif isinstance(node, ast.Yield):
            self.try_only_minimize(node, node.value)
        elif isinstance(node, ast.YieldFrom):
            self.try_only_minimize(node, node.value)
        elif isinstance(node, ast.Dict):
            self.try_only_minimize(node, *node.keys, *node.values)
            # todo: minimize list
        elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            self.minimize(node.elts)
        elif isinstance(node, ast.Name):
            pass
        elif isinstance(node, ast.Constant):
            pass
        elif isinstance(node, ast.Starred):
            self.try_only_minimize(node, node.value)
        elif isinstance(node, ast.Call):
            if self.try_only_minimize(
                node,
                node.func,
                *[kw.value for kw in node.keywords],
                *[
                    arg.value if isinstance(arg, ast.Starred) else arg
                    for arg in node.args
                ]
            ):
                return

            not_stared = [arg for arg in node.args if not isinstance(arg, ast.Starred)]
            for arg in not_stared:
                if self.try_only(node, arg):
                    self.minimize(arg)
                    break
            else:
                self.minimize(node.args)

        elif isinstance(
            node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)
        ):
            for gen in node.generators:
                if self.try_only(node, gen.iter):
                    self.minimize_expr(gen.iter)
                    return

            if isinstance(node, ast.DictComp):
                if self.try_only(node, node.key):
                    self.minimize_expr(node.key)
                    return

                if self.try_only(node, node.value):
                    self.minimize_expr(node.value)
                    return

                self.minimize_expr(node.key)
                self.minimize_expr(node.value)
            else:
                if self.try_only(node, node.elt):
                    self.minimize_expr(node.elt)
                    return

                self.minimize_expr(node.elt)
            self.minimize_list(node.generators, self.minimize_comprehension, 1)

        else:
            raise TypeError(node)  # Expr

            for e in ast.iter_child_nodes(node):
                if self.try_only(node, e):
                    self.minimize_expr(e)
                    return

            for e in ast.iter_child_nodes(node):
                self.minimize_expr(e)

    def minimize_except_handler(self, handler):
        self.minimize_list(handler.body, self.minimize_stmt)
        if handler.type is not None:
            self.minimize_expr(handler.type)

    def minimize_stmt(self, node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if self.try_only_minimize(node, node.decorator_list):
                return

            self.minimize_list(node.body, self.minimize_stmt)
            body = self.get_ast(node)

            if not any(
                isinstance(
                    n,
                    (
                        ast.Return,
                        ast.Yield,
                        ast.YieldFrom,
                        ast.Await,
                        ast.AsyncFor,
                        ast.AsyncWith,
                    ),
                )
                for n in ast.walk(body)
            ):
                if self.try_only(node, node.body):
                    return

            nargs = node.args

            self.minimize_list(nargs.posonlyargs, lambda e: None)
            self.minimize_list(nargs.args, lambda e: None)
            self.minimize_list(nargs.kwonlyargs, lambda e: None)
            self.try_none(nargs.vararg)
            self.try_none(nargs.kwarg)

        elif isinstance(node, ast.ClassDef):
            if self.try_only_minimize(node, node.decorator_list):
                return

            if self.try_only_minimize(node, node.body):
                return

            self.minimize(node.bases)

        elif isinstance(node, ast.Return):
            self.try_only_minimize(node, node.value)

        elif isinstance(node, ast.Delete):
            self.try_only_minimize(node, *node.targets)

        elif isinstance(node, ast.Assign):
            self.try_only_minimize(node, node.value)
            # todo minimize targets

        elif isinstance(node, ast.AugAssign):
            self.try_only_minimize(node, node.value)
            # todo minimize target

        elif isinstance(node, ast.AnnAssign):
            self.try_only_minimize(node, node.value)
            # todo minimize target

        elif isinstance(node, (ast.For, ast.AsyncFor)):
            self.minimize_list(node.body, self.minimize_stmt)
            body = self.get_ast(node)
            if not any(
                isinstance(n, (ast.Break, ast.Continue)) for n in ast.walk(body)
            ):
                if self.try_only(node, node.body):
                    return

            self.try_only_minimize(node, node.iter, node.orelse)

        elif isinstance(node, ast.While):
            self.minimize_list(node.body, self.minimize_stmt)
            body = self.get_ast(node)
            if not any(
                isinstance(n, (ast.Break, ast.Continue)) for n in ast.walk(body)
            ):
                if self.try_only(node, node.body):
                    return

            self.try_only_minimize(node, node.test, node.orelse)

        elif isinstance(node, ast.If):
            self.try_only_minimize(node, node.test, node.body, node.orelse)

        elif isinstance(node, (ast.With, ast.AsyncWith)):
            self.minimize_list(node.body, self.minimize_stmt)
            if self.try_only_minimize(node, *[ctx.context_expr for ctx in node.items]):
                return
            self.minimize_list(node.items, lambda e: None, minimal=1)

        elif isinstance(node, ast.Match):
            pass  # todo Match

        elif isinstance(node, ast.Raise):
            self.try_only_minimize(node, node.exc, node.cause)

        elif isinstance(node, (ast.Try, ast.TryStar)):
            if self.try_only(node, node.body):
                self.minimize(node.body)
                return
            if node.orelse and self.try_only(node, node.orelse):
                self.minimize(node.orelse)
                return
            if node.finalbody and self.try_only_minimize(node, node.finalbody):
                self.minimize(node.finalbody)
                return

            if self.try_only_minimize(node, *[h.body for h in node.handlers]):
                return
            if self.try_only_minimize(node, *[h.type for h in node.handlers]):
                return

            self.minimize_list(
                node.handlers, self.minimize_except_handler, 0 if node.finalbody else 1
            )
        elif isinstance(node, ast.Assert):
            self.try_only_minimize(node, node.test, node.msg)

        elif isinstance(node, (ast.Import, ast.ImportFrom)):

            self.minimize_list(node.names, lambda e: None, 1)

        elif isinstance(node, (ast.Global)):
            pass  # TODO
        elif isinstance(node, (ast.Nonlocal)):
            pass  # TODO

        elif isinstance(node, ast.Expr):
            self.minimize_expr(node.value)

        elif isinstance(node, ast.Module):
            self.minimize(node.body)
        else:

            raise TypeError(node)  # Stmt

            for name, value in ast.iter_fields(node):
                if isinstance(node, ast.Module):
                    continue

                if is_block(value):
                    if self.try_only(node, value):
                        self.minimize_list(value, self.minimize_stmt)
                        return
                elif isinstance(value, ast.expr):
                    if self.try_only(node, value):
                        self.minimize_expr(value)
                        return

            for name, value in ast.iter_fields(node):
                if is_block(value):
                    self.minimize_list(value, self.minimize_stmt)
                elif isinstance(value, ast.expr):
                    self.minimize_expr(value)

    def minimize_list(self, stmts, terminal, minimal=0):
        max_remove = len(stmts) - minimal

        def wo(l):
            nonlocal max_remove

            if max_remove < len(l):
                devide(l)
            else:
                if self.try_without(l):
                    max_remove -= len(l)
                else:
                    devide(l)

        def devide(l):
            nonlocal max_remove
            if not l:
                return

            if len(l) == 1:
                if max_remove >= 1:
                    if self.try_without(l):
                        max_remove -= 1
                    else:
                        terminal(l[0])
                else:
                    terminal(l[0])
            else:

                mid = len(l) // 2

                wo(l[mid:])
                wo(l[:mid])

        devide(stmts)


def minimize(source, checker, *, progress_callback=lambda current, total: None):
    """
    minimzes the source code

    Args:
        checker: a function which gets the source and returns `True` when the criteria is fullfilled.
        progress_callback: function which is called everytime the source gets a bit smaller.

    returns the minimized source
    """

    minimizer = Minimizer(source, checker, progress_callback)

    return minimizer.source
