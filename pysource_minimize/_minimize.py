import ast
import copy
import os
import sys
from typing import List
from typing import Union

try:
    from ast import unparse
except ImportError:
    from astunparse import unparse  # type: ignore

TESTING = "PYTEST_CURRENT_TEST" in os.environ


py311 = sys.version_info >= (3, 11)
py310 = sys.version_info >= (3, 10)
py39 = sys.version_info >= (3, 9)
py38 = sys.version_info >= (3, 8)

until_py37 = sys.version_info < (3, 8)


def is_block(nodes):
    return (
        isinstance(nodes, list)
        and nodes
        and all(isinstance(n, ast.stmt) for n in nodes)
    )


def arguments(
    node: Union[ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda]
) -> List[ast.arg]:
    args = node.args
    l = [*args.args, args.vararg, *args.kwonlyargs, args.kwarg]

    if sys.version_info >= (3, 8):
        l += args.posonlyargs

    return [arg for arg in l if arg is not None]


class Minimizer:
    def __init__(self, source, checker, progress_callback):
        self.checker = checker
        self.progress_callback = progress_callback

        self.original_source = source
        if sys.version_info >= (3, 8):
            self.original_ast = ast.parse(source, type_comments=True)
        else:
            self.original_ast = ast.parse(source)

        class UniqueObj(ast.NodeTransformer):
            def visit(self, node):
                if not node._fields:
                    return type(node)()
                return super().visit(node)

        self.original_ast = UniqueObj().visit(self.original_ast)

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

    def get_ast(self, node, replaced={}):
        replaced = {**self.replaced, **replaced}

        tmp_ast = copy.deepcopy(node)
        node_map = {n.__index: n for n in ast.walk(tmp_ast)}

        if TESTING:
            for a, b in zip(ast.walk(tmp_ast), ast.walk(node)):
                assert a.__index == b.__index

            unique_index = {}
            for n in ast.walk(tmp_ast):
                assert n.__index not in unique_index, (n, unique_index[n.__index])
                unique_index[n.__index] = n

        def replaced_node(node):
            if not isinstance(node, ast.AST):
                return node
            if not hasattr(node, "_Minimizer__index"):
                return node
            i = node.__index
            while i in replaced:
                i = replaced[i]
                assert isinstance(i, (int, type(None), ast.AST)), (node, i)
            if i is None:
                return None
            if isinstance(i, ast.AST):
                return i
            return node_map[i]

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
                        else:
                            raise TypeError(type(next_i))

            if not all(isinstance(n, ast.AST) for n in nodes):
                return nodes

            block = is_block(nodes)

            result = list(replace([n.__index for n in nodes]))

            if not result and block and name not in ("orelse", "finalbody"):
                return [ast.Pass()]

            if block:
                result = [ast.Expr(r) if isinstance(r, ast.expr) else r for r in result]

            return result

        def map_node(node):
            for name, child in ast.iter_fields(node):
                if (
                    hasattr(node, "_Minimizer__index")
                    and (node.__index, name) in replaced
                ):
                    setattr(node, name, replaced[(node.__index, name)])
                elif isinstance(child, list):
                    setattr(node, name, replaced_nodes(child, name))
                else:
                    setattr(node, name, replaced_node(child))
            for child in ast.iter_child_nodes(node):
                map_node(child)

        map_node(tmp_ast)

        return tmp_ast

    def get_source_tree(self, replaced):
        tree = self.get_ast(self.original_ast, replaced)
        ast.fix_missing_locations(tree)
        return unparse(tree), tree

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

        for node in ast.walk(tree):
            if isinstance(node, ast.Delete) and any(
                isinstance(target, (ast.Constant, ast.NameConstant))
                for target in node.targets
            ):
                # code like:
                # delete None
                return False

        if 0:
            print()
            print("replaced:", self.replaced, replaced)
            if source.count("\n") < 15:
                print(source)

        if 0:
            try:
                compile(source, "<filename>", "exec")
            except Exception:
                return False

        if self.checker(source):
            self.replaced.update(replaced)
            self.progress_callback(self.nodes_of(tree), self.original_nodes_number)
            return True

        return False

    def try_attr(self, node, attr_name, new_attr):
        return self.try_with({(node.__index, attr_name): new_attr})

    def try_node(self, old_node, new_node):
        return self.try_with({old_node.__index: new_node})

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
        self.minimize_list(comp.ifs, terminal=self.minimize_expr)

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
        elif sys.version_info < (3, 9) and isinstance(o, ast.slice):
            return self.minimize_expr(o)
        elif isinstance(o, list):
            return self.minimize_list(o, self.minimize)
        else:
            raise TypeError(type(o))

    def minimize_expr(self, node):
        if isinstance(node, ast.BoolOp):
            self.minimize_list(node.values, self.minimize_expr, 1)
        elif isinstance(node, ast.Compare):
            if self.try_only(node, node.left):
                self.minimize(node.left)
                return

            for comp in node.comparators:
                if self.try_only(node, comp):
                    self.minimize(comp)
                    return

            self.minimize_lists(
                (node.ops, node.comparators), (lambda _: None, self.minimize)
            )

        elif isinstance(node, ast.Subscript):
            self.try_only_minimize(node, node.value, node.slice)

        elif isinstance(node, ast.FormattedValue):
            if (
                isinstance(node.format_spec, ast.JoinedStr)
                and len(node.format_spec.values) == 1
                and self.try_only(node, node.format_spec.values[0])
            ):
                self.minimize(node.format_spec.values[0])
                return

            self.try_none(node.format_spec)
            self.minimize_expr(node.value)

        elif isinstance(node, ast.JoinedStr):
            if (
                len(node.values) == 1
                and isinstance(node.values[0], ast.FormattedValue)
                and self.try_only(node, node.values[0].value)
            ):
                self.minimize(node.values[0].value)
                return

            self.minimize(node.values)
            # todo minimize values

        elif isinstance(node, ast.Slice):
            self.try_only_minimize(node, node.lower, node.upper, node.step)
        elif isinstance(node, ast.Lambda):

            if self.try_only_minimize(node, node.body):
                return

            if self.minimize_args_of(node):
                return

        elif isinstance(node, ast.UnaryOp):
            self.try_only_minimize(node, node.operand)
        elif isinstance(node, ast.BinOp):
            self.try_only_minimize(node, node.left, node.right)
        elif isinstance(node, ast.Attribute):
            if not self.try_node(node, ast.Name(id="something")):
                self.try_only_minimize(node, node.value)
        elif isinstance(node, ast.IfExp):
            self.try_only_minimize(node, node.test, node.body, node.orelse)
        elif isinstance(node, ast.Await):
            self.try_only_minimize(node, node.value)
        elif isinstance(node, ast.Yield):
            self.try_only_minimize(node, node.value)
        elif isinstance(node, ast.YieldFrom):
            self.try_only_minimize(node, node.value)
        elif isinstance(node, ast.Dict):
            for n in [*node.values, *node.keys]:
                if self.try_only(node, n):
                    self.minimize(n)
                    return

            self.minimize_lists(
                (node.keys, node.values), (self.minimize, self.minimize)
            )

        elif isinstance(node, (ast.Set)):
            if node.elts and self.try_only(node, node.elts[0]):
                self.minimize(node.elts[0])
                return
            self.minimize_list(node.elts, self.minimize, 1)
        elif isinstance(node, (ast.List, ast.Tuple)):
            if node.elts and self.try_only(node, node.elts[0]):
                self.minimize(node.elts[0])
                return
            self.minimize(node.elts)
        elif isinstance(node, ast.Name):
            pass
        elif isinstance(node, ast.Constant):
            pass
        elif isinstance(node, ast.Index):
            self.minimize(node.value)
        elif until_py37 and isinstance(
            node, (ast.Str, ast.Bytes, ast.Num, ast.NameConstant, ast.Ellipsis)
        ):
            pass
        elif isinstance(node, ast.Starred):
            self.try_only_minimize(node, node.value)
        elif isinstance(node, ast.Call):
            for e in [
                node.func,
                *[kw.value for kw in node.keywords],
                *[
                    arg.value if isinstance(arg, ast.Starred) else arg
                    for arg in node.args
                ],
            ]:
                if self.try_only(node, e):
                    self.minimize(e)
                    return

            self.minimize(node.args)
            self.minimize_list(
                node.keywords, terminal=lambda kw: self.minimize(kw.value)
            )

        elif isinstance(
            node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)
        ):
            for gen in node.generators:
                if self.try_only(node, gen.target):
                    self.minimize_expr(gen.target)
                    return

                if self.try_only(node, gen.iter):
                    self.minimize_expr(gen.iter)
                    return

                for if_ in gen.ifs:
                    if self.try_only(node, if_):
                        self.minimize_expr(if_)
                        return

            if isinstance(node, ast.DictComp):
                if self.try_only_minimize(node, node.key, node.value):
                    return
            else:
                if self.try_only_minimize(node, node.elt):
                    return

            self.minimize_list(node.generators, self.minimize_comprehension, 1)

        elif isinstance(node, ast.NamedExpr):
            self.try_only_minimize(node, node.target, node.value)
        else:
            raise TypeError(node)  # Expr

    def minimize_optional(self, node):
        if node is not None and not self.try_none(node):
            self.minimize(node)

    if py310:

        def minimize_match_case(self, c: ast.match_case):
            def minimize_pattern(pattern):
                if isinstance(pattern, ast.MatchSequence):
                    self.minimize_list(pattern.patterns, minimize_pattern)
                elif isinstance(pattern, ast.MatchOr):
                    self.minimize_list(pattern.patterns, minimize_pattern, 1)

                elif isinstance(pattern, ast.MatchAs):
                    if pattern.pattern:
                        self.try_only(pattern, pattern.pattern)
                elif isinstance(pattern, ast.MatchMapping):
                    self.minimize_lists(
                        (pattern.keys, pattern.patterns),
                        (self.minimize, minimize_pattern),
                    )
                elif isinstance(pattern, ast.MatchClass):
                    self.minimize(pattern.cls)
                    self.minimize_list(pattern.patterns, minimize_pattern)

                    new_attrs = list(pattern.kwd_attrs)

                    for i in reversed(range(len(pattern.kwd_patterns))):
                        try_attrs = [v for j, v in enumerate(new_attrs) if j != i]
                        if self.try_with(
                            {
                                pattern.kwd_patterns[i].__index: [],
                                (pattern.__index, "kwd_attrs"): try_attrs,
                            }
                        ):
                            new_attrs = try_attrs

            self.minimize(c.body)

            if c.guard and not self.try_none(c.guard):
                self.minimize(c.guard)

            minimize_pattern(c.pattern)

    def minimize_args_of(self, func):
        args = func.args

        for child in [
            *[arg.annotation for arg in arguments(func)],
            *func.args.defaults,
            *func.args.kw_defaults,
            getattr(func, "returns", None),
        ]:
            if child is not None and self.try_only(func, child):
                self.minimize(child)
                return True

        def minimize_arg(arg: ast.arg):
            if arg.annotation is not None and not self.try_none(arg.annotation):
                self.minimize(arg.annotation)

            if sys.version_info >= (3, 8):
                self.try_none(arg.type_comment)

        if py38:
            self.minimize_list(args.posonlyargs, minimize_arg)

        self.minimize_list(args.defaults, self.minimize)

        self.minimize_list(args.args, minimize_arg)

        self.minimize_lists(
            (args.kwonlyargs, args.kw_defaults), (minimize_arg, self.minimize)
        )

        if args.vararg is not None and not self.try_none(args.vararg):
            minimize_arg(args.vararg)

        if args.kwarg is not None and not self.try_none(args.kwarg):
            minimize_arg(args.kwarg)

        return False

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

            if self.minimize_args_of(node):
                return
            if sys.version_info >= (3, 12):
                self.minimize_list(node.type_params, self.minimize_type_param)

            if node.returns:
                if not self.try_none(node.returns):
                    self.minimize_expr(node.returns)

        elif isinstance(node, ast.ClassDef):
            if self.try_only_minimize(node, node.decorator_list):
                return

            if self.try_only_minimize(node, node.body):
                return

            if sys.version_info >= (3, 12):
                self.minimize_list(node.type_params, self.minimize_type_param)

            for e in [
                *[kw.value for kw in node.keywords],
                *[
                    arg.value if isinstance(arg, ast.Starred) else arg
                    for arg in node.bases
                ],
            ]:
                if self.try_only(node, e):
                    self.minimize(e)
                    return

            self.minimize(node.bases)
            self.minimize_list(
                node.keywords, terminal=lambda kw: self.minimize(kw.value)
            )
            return

        elif isinstance(node, ast.Return):
            self.try_only_minimize(node, node.value)

        elif isinstance(node, ast.Delete):
            if len(node.targets) == 1 and self.try_only(node, node.targets[0]):
                self.minimize(node.targets[0])
                return

            self.minimize_list(node.targets, self.minimize, 1)

        elif isinstance(node, ast.Assign):
            self.try_only_minimize(node, node.value, node.targets)

        elif isinstance(node, ast.AugAssign):
            self.try_only_minimize(node, node.target, node.value)

        elif isinstance(node, ast.AnnAssign):

            if node.value is None or not self.try_node(
                node, ast.Assign(targets=[node.target], value=node.value)
            ):
                self.try_only_minimize(node, node.target, node.value, node.annotation)

        elif isinstance(node, (ast.For, ast.AsyncFor)):
            if self.try_only(node, node.target):
                self.minimize(node.target)
                return

            self.minimize_list(node.body, self.minimize_stmt)
            body = self.get_ast(node)
            if not any(
                isinstance(n, (ast.Break, ast.Continue)) for n in ast.walk(body)
            ):
                if self.try_only(node, node.body):
                    return

            self.try_only_minimize(node, node.iter, node.orelse)
            self.minimize(node.target)

        elif isinstance(node, ast.While):
            self.minimize_list(node.body, self.minimize_stmt)
            body = self.get_ast(node)
            if not any(
                isinstance(n, (ast.Break, ast.Continue)) for n in ast.walk(body)
            ):
                if self.try_only(node, node.body):
                    return

            self.try_only_minimize(node, node.test, node.orelse)

        elif isinstance(node, (ast.Break, ast.Continue)):
            pass

        elif isinstance(node, ast.If):
            self.try_only_minimize(node, node.test, node.body, node.orelse)

        elif isinstance(node, (ast.With, ast.AsyncWith)):

            if self.try_only_minimize(node, node.body):
                return

            for item in node.items:
                if self.try_only(node, item.context_expr):
                    self.minimize(item.context_expr)
                    return

                if item.optional_vars is not None and self.try_only(
                    node, item.optional_vars
                ):
                    self.minimize(item.optional_vars)
                    return

            def minimize_item(item: ast.withitem):
                self.minimize(item.context_expr)
                self.minimize_optional(item.optional_vars)

            self.minimize_list(node.items, minimize_item, minimal=1)

        elif py310 and isinstance(node, ast.Match):
            if self.try_only_minimize(node, node.subject):
                return

            for case_ in node.cases:
                for e in [case_.guard, case_.body]:
                    if e is not None and self.try_only(node, e):
                        self.minimize(e)
                        return

                if isinstance(case_.pattern, ast.MatchValue):
                    if self.try_only(node, case_.pattern.value):
                        self.minimize(case_.pattern.value)
                        return

            self.minimize_list(node.cases, self.minimize_match_case, 1)

        elif isinstance(node, ast.Raise):
            if not self.try_only(node, node.exc) and not self.try_only(node, node.exc):
                self.minimize_optional(node.cause)
                # cause requires exc
                # `raise from cause` is not valid
                if self.get_ast(node).cause:
                    self.minimize(node.exc)
                else:
                    self.minimize_optional(node.exc)

        elif isinstance(node, ast.Try) or (py311 and isinstance(node, ast.TryStar)):
            try_star = py311 and isinstance(node, ast.TryStar)

            if try_star and self.try_node(
                node,
                ast.Try(
                    body=node.body,
                    handlers=node.handlers,
                    orelse=node.orelse,
                    finalbody=node.finalbody,
                ),
            ):
                return

            if self.try_only(node, node.body):
                self.minimize(node.body)
                return

            if node.orelse and self.try_only(node, node.orelse):
                self.minimize(node.orelse)
                return

            if node.finalbody and self.try_only(node, node.finalbody):
                self.minimize(node.finalbody)
                return

            for h in node.handlers:
                if self.try_only(node, h.body):
                    self.minimize(h.body)
                    return
                if h.type is not None and self.try_only(node, h.type):
                    self.minimize(h.type)
                    return

            def minimize_except_handler(handler):
                self.minimize_list(handler.body, self.minimize_stmt)

                if not handler.name and not try_star:
                    self.minimize_optional(handler.type)

            self.minimize_list(
                node.handlers, minimize_except_handler, 1  # 0 if node.finalbody else 1
            )
            self.minimize(node.body)
            self.minimize(node.orelse)
            self.minimize(node.finalbody)

        elif isinstance(node, ast.Assert):
            if node.msg:
                if not self.try_none(node.msg):
                    self.try_only(node, node.msg)
                    self.minimize(node.msg)

            if self.try_only_minimize(node, node.test):
                return

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
        elif sys.version_info >= (3, 12) and isinstance(node, ast.TypeAlias):
            self.minimize_list(node.type_params, self.minimize_type_param)
            self.minimize(node.value)
            self.minimize(node.name)

        elif isinstance(node, ast.Pass):
            pass
        else:
            raise TypeError(node)  # Stmt

    def minimize_type_param(self, node):
        assert sys.version_info >= (3, 12)
        if isinstance(node, ast.TypeVar):
            self.minimize_optional(node.bound)

    def minimize_lists(self, lists, terminals, minimal=0):
        lists = list(zip(*lists))
        max_remove = len(lists) - minimal

        import itertools

        def try_without(l):
            self.try_without(itertools.chain.from_iterable(l))

        def wo(l):
            nonlocal max_remove

            if max_remove < len(l) or not try_without(l):
                devide(l)
            else:
                max_remove -= len(l)

        def devide(l):
            nonlocal max_remove, remaining
            if not l:
                return

            if len(l) == 1:
                if max_remove >= 1 and try_without(l):
                    max_remove -= 1
                else:
                    remaining.append(l[0])
            else:
                mid = len(l) // 2

                # remove in reverse order
                # this is a good heuristic, because it removes the usage before the definition
                wo(l[mid:])
                wo(l[:mid])

        remaining = []
        devide(lists)

        for nodes in remaining:
            for terminal, node in zip(terminals, nodes):
                terminal(node)

    def minimize_list(self, stmts, terminal, minimal=0):
        # return self.minimize_lists((stmts,),(terminal,),minimal=0)
        stmts = list(stmts)
        max_remove = len(stmts) - minimal

        def wo(l):
            nonlocal max_remove

            if max_remove < len(l) or not self.try_without(l):
                devide(l)
            else:
                max_remove -= len(l)

        def devide(l):
            nonlocal max_remove, remaining
            if not l:
                return

            if len(l) == 1:
                if max_remove >= 1 and self.try_without(l):
                    max_remove -= 1
                else:
                    remaining.append(l[0])
            else:
                mid = len(l) // 2

                # remove in reverse order
                # this is a good heuristic, because it removes the usage before the definition
                wo(l[mid:])
                wo(l[:mid])

        remaining = []
        devide(stmts)

        for node in remaining:
            terminal(node)


def minimize(
    source: str, checker, *, progress_callback=lambda current, total: None
) -> str:
    """
    minimzes the source code

    Args:
        source: the source code to minimize
        checker: a function which gets the source and returns `True` when the criteria is fullfilled.
        progress_callback: function which is called everytime the source gets a bit smaller.

    returns the minimized source
    """

    last_result = ""

    while last_result != source:
        minimizer = Minimizer(source, checker, progress_callback)
        last_result, source = source, minimizer.source

    return last_result
