import ast
import sys

from ._minimize_base import arguments
from ._minimize_base import coverage_required
from ._minimize_base import MinimizeBase
from ._minimize_base import ValueWrapper


def walk_until(node, stop=()):
    if isinstance(node, list):
        for e in node:
            yield from walk_until(e, stop)
        return
    yield node
    for child in ast.iter_child_nodes(node):
        if not isinstance(child, stop):
            yield from walk_until(child)


class MinimizeStructure(MinimizeBase):
    def minimize(self, o):
        if (
            sys.version_info >= (3, 8)
            and isinstance(o, (ast.expr, ast.stmt))
            and hasattr(o, "type_comment")
        ):
            self.try_attr(o, "type_comment", None)

        if isinstance(o, ast.expr):
            return self.minimize_expr(o)
        elif isinstance(o, ast.stmt):
            return self.minimize_stmt(o)
        elif sys.version_info < (3, 9) and isinstance(o, ast.slice):
            return self.minimize_expr(o)
        elif isinstance(o, list):
            return self.minimize_list(o, self.minimize)
        elif isinstance(o, ast.arg):
            return self.minimize_arg(o)
        elif isinstance(o, ast.pattern):
            pass
        elif isinstance(o, ValueWrapper):
            pass
        else:
            raise TypeError(type(o))

    def minimize_comprehension(self, comp):
        self.minimize_expr(comp.iter)
        self.minimize_list(comp.ifs, terminal=self.minimize_expr)

    def minimize_arg(self, arg: ast.arg):
        self.minimize_optional(arg.annotation)

    def minimize_expr(self, node):
        if isinstance(node, ast.BoolOp):
            remaining = self.minimize_list(node.values, self.minimize_expr, 1)
            if len(remaining) == 1:
                self.try_only(node, remaining[0])

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
            if isinstance(node.format_spec, ast.JoinedStr):
                # work around for https://github.com/python/cpython/issues/110309
                spec = [
                    v
                    for v in node.format_spec.values
                    if not (isinstance(v, ast.Constant) and v.value == "")
                ]
                if len(spec) == 1 and self.try_only(node, spec[0]):
                    self.minimize(spec[0])
                    return

            if not self.try_none(node.format_spec):
                self.minimize(node.format_spec)

            self.minimize_expr(node.value)

        elif isinstance(node, ast.JoinedStr):
            for v in node.values:
                if isinstance(v, ast.FormattedValue) and self.try_only(node, v.value):
                    self.minimize(v.value)
                    return
                if (
                    isinstance(v, ast.FormattedValue)
                    and v.format_spec
                    and self.try_only(node, v.format_spec)
                ):
                    self.minimize(v.format_spec)
                    return

            self.minimize(node.values)
            # todo minimize values

        elif isinstance(node, ast.Slice):
            if self.try_only(node, node.lower, node.upper, node.step):
                return

            for child in (node.lower, node.upper, node.step):
                if not self.try_none(child):
                    self.minimize(child)

        elif isinstance(node, ast.ExtSlice):
            self.minimize_list(node.dims, minimal=1)

        elif isinstance(node, ast.Index):
            self.minimize(node.value)

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
            if not self.try_node(node, ast.Name(id="something", ctx=ast.Load())):
                self.try_only_minimize(node, node.value)
        elif isinstance(node, ast.IfExp):
            self.try_only_minimize(node, node.test, node.body, node.orelse)
        elif isinstance(node, ast.Await):
            self.try_only_minimize(node, node.value)
        elif isinstance(node, ast.Yield):
            if node.value is None:
                if self.try_node(node, ast.Constant(value=None, kind="")):
                    return
            self.try_only_minimize(node, node.value)
        elif isinstance(node, ast.YieldFrom):
            self.try_only_minimize(node, node.value)
        elif isinstance(node, ast.Dict):
            remaining = self.minimize_lists(
                (node.keys, node.values), (self.minimize, self.minimize)
            )
            if len(remaining) == 1:
                if self.try_only(node, remaining[0][0]):
                    return

                if self.try_only(node, remaining[0][1]):
                    return

        elif isinstance(node, (ast.Set)):
            remaining = self.minimize_list(node.elts, self.minimize, 1)
            # TODO: min size 1?
            if len(remaining) == 1:
                self.try_only(node, remaining[0])
        elif isinstance(node, (ast.List, ast.Tuple)):
            remaining = self.minimize_list(node.elts, self.minimize, 1)
            # TODO: min size 1?
            if len(remaining) == 1:
                self.try_only(node, remaining[0])
        elif isinstance(node, ast.Name):
            pass
        elif isinstance(node, ast.Constant):
            pass
        elif isinstance(node, ast.Index):
            self.minimize(node.value)
        elif sys.version_info < (3, 8) and isinstance(
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
            assert False, "expression is not handled %s" % (node)

    def minimize_optional(self, node):
        if not self.try_none(node):
            self.minimize(node)

    if sys.version_info >= (3, 10):

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
                    self.minimize_lists((pattern.kwd_attrs, pattern.kwd_patterns))

            self.minimize(c.body)

            if not self.try_none(c.guard):
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
            if child != None and self.try_only(func, child):
                self.minimize(child)
                return True

        all_args = []
        if sys.version_info >= (3, 8):
            all_args += args.posonlyargs
        all_args += args.args

        split = len(all_args) - len(args.defaults)
        self.minimize_list(all_args[:split])
        remaining = self.minimize_lists(
            (all_args[split:], args.defaults), (self.minimize, lambda a: None)
        )

        remove_defaults = True
        for _, default in remaining:
            if remove_defaults:
                if default is not None:
                    if not self.try_without([default]):
                        self.minimize(default)
                        remove_defaults = False
            else:
                self.minimize(default)

        remaining = self.minimize_lists(
            (args.kwonlyargs, args.kw_defaults), (self.minimize, lambda a: None)
        )
        for _, default in remaining:
            self.minimize_optional(default)

        self.minimize_optional(args.vararg)
        self.minimize_optional(args.kwarg)

        return False

    def minimize_stmt(self, node):

        if sys.version_info >= (3, 12) and hasattr(node, "type_params"):

            for p in node.type_params:
                if isinstance(p, ast.TypeVar):
                    if p.bound is not None and self.try_only(node, p.bound):
                        self.minimize(p.bound)
                        return

                if (
                    sys.version_info >= (3, 13)
                    and p.default_value is not None
                    and self.try_only(node, p.default_value)
                ):
                    self.minimize(p.default_value)
                    return
            self.minimize_list(node.type_params, self.minimize_type_param)

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if self.try_only_minimize(node, node.decorator_list):
                return

            self.minimize_list(node.body)
            body = self.get_ast(node).body

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
                for n in walk_until(
                    body,
                    (
                        ast.GeneratorExp,
                        ast.FunctionDef,
                        ast.ClassDef,
                        ast.AsyncFunctionDef,
                    ),
                )
            ):
                if self.try_only(node, node.body):
                    return

            if self.minimize_args_of(node):
                return

            if node.returns:
                if not self.try_none(node.returns):
                    self.minimize_expr(node.returns)

        elif isinstance(node, ast.ClassDef):
            if self.try_only_minimize(node, node.decorator_list):
                return

            if self.try_only_minimize(node, node.body):
                return

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
            for t in node.targets:
                if self.try_only(node, t):
                    self.minimize(t)
                    return

            self.minimize_list(node.targets, self.minimize, 1)

        elif isinstance(node, ast.Assign):
            self.try_only_minimize(node, node.value, node.targets)

        elif isinstance(node, ast.AugAssign):
            self.try_only_minimize(node, node.target, node.value)

        elif isinstance(node, ast.AnnAssign):
            for child in [node.target, node.value, node.annotation]:
                if child is not None and self.try_only(node, child):
                    self.minimize(child)
                    return

            if not self.try_node(
                node,
                ast.Assign(
                    targets=[node.target],
                    value=node.value,
                    **(dict(type_comment="") if sys.version_info >= (3, 8) else {}),
                ),
            ):
                self.minimize(node.target)
                self.minimize_optional(node.value)
                self.minimize(node.annotation)

        elif isinstance(node, (ast.For, ast.AsyncFor)):
            if self.try_only(node, node.target):
                self.minimize(node.target)
                return

            self.minimize_list(node.body)
            body = self.get_ast(node)
            if not any(
                isinstance(n, (ast.Break, ast.Continue)) for n in ast.walk(body)
            ):
                if self.try_only(node, node.body):
                    return

            self.try_only_minimize(node, node.iter, node.orelse)
            self.minimize(node.target)

        elif isinstance(node, ast.While):
            self.minimize_list(node.body)
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

        elif sys.version_info >= (3, 10) and isinstance(node, ast.Match):
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
            if node.exc and self.try_only(node, node.exc):
                self.minimize(node.exc)
                return

            if node.cause and not self.try_only(node, node.cause):
                self.minimize_optional(node.cause)
                # cause requires exc
                # `raise from cause` is not valid
                if self.get_ast(node).cause:
                    self.minimize(node.exc)
                else:
                    coverage_required()
                    self.minimize_optional(node.exc)

        elif isinstance(node, ast.Try) or (
            sys.version_info >= (3, 11) and isinstance(node, ast.TryStar)
        ):
            try_star = sys.version_info >= (3, 11) and isinstance(node, ast.TryStar)

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
                self.minimize_list(handler.body)

                if not handler.name and not try_star:
                    self.minimize_optional(handler.type)
                elif handler.type is not None:
                    self.minimize(handler.type)

                if handler.name:
                    self.try_attr(handler, "name", None)

            self.minimize_list(
                node.handlers, minimize_except_handler, 1  # 0 if node.finalbody else 1
            )

            self.minimize(node.body)
            self.minimize(node.orelse)
            self.minimize(node.finalbody)

            # if try_star and self.try_node(
            #     node,
            #     ast.Try(
            #         body=node.body,
            #         handlers=node.handlers,
            #         orelse=node.orelse,
            #         finalbody=node.finalbody,
            #     ),
            # ):
            #     return

        elif isinstance(node, ast.Assert):
            if node.msg:
                if self.try_only(node, node.msg):
                    self.minimize(node.msg)
                    return

                if not self.try_none(node.msg):
                    self.minimize(node.msg)

            if self.try_only_minimize(node, node.test):
                return

        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            self.minimize_list(node.names, lambda e: None, 1)

        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            self.minimize_list(node.names)

        elif isinstance(node, ast.Expr):
            self.minimize_expr(node.value)

        elif isinstance(node, ast.Module):
            self.minimize(node.body)
            if sys.version_info >= (3, 8):
                self.minimize_list(node.type_ignores, lambda e: None)
        elif sys.version_info >= (3, 12) and isinstance(node, ast.TypeAlias):
            if self.try_only_minimize(node, node.name, node.value):
                return

        elif isinstance(node, ast.Pass):
            pass
        else:
            raise TypeError(node)  # Stmt

    def minimize_type_param(self, node):
        assert sys.version_info >= (3, 12)
        if isinstance(node, ast.TypeVar):
            self.minimize_optional(node.bound)

        if sys.version_info >= (3, 13):
            if not self.try_none(node.default_value):
                self.minimize(node.default_value)

    def minimize_lists(self, lists, terminals=None, minimal=0):
        if terminals is None:
            terminals = [self.minimize for _ in lists]

        lists = list(zip(*lists))
        max_remove = len(lists) - minimal

        import itertools

        def try_without(l):
            return self.try_without(itertools.chain.from_iterable(l))

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

        return remaining

    def minimize_list(self, stmts, terminal=None, minimal=0):
        if terminal is None:
            terminal = self.minimize

        # result= self.minimize_lists((stmts,),(terminal,),minimal=0)
        # return [e[0] for e in result]

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

        return remaining
