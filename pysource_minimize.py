import os
import sys


import traceback
import contextlib

import asttokens
import asttokens.util
import ast
from rich import print as rprint
import rich

import rich.syntax
from rich.console import Console
import token


@contextlib.contextmanager
def no_output():
    with open(os.devnull, "w") as f:
        with contextlib.redirect_stdout(f):
            with contextlib.redirect_stderr(f):
                yield


def start_offset(thing):
    if isinstance(thing, ast.AST):
        return thing.first_token.startpos

    if isinstance(thing, asttokens.util.Token):
        return thing.startpos

    assert isinstance(thing, int)

    return thing


def end_offset(thing):
    if isinstance(thing, ast.AST):
        return thing.last_token.endpos

    if isinstance(thing, asttokens.util.Token):
        return thing.endpos

    assert isinstance(thing, int)

    return thing


class Minimizer:
    def __init__(self, source, checker):

        self.checker = checker

        self.original_source = source
        self.source = source

        self.atok = asttokens.ASTTokens(self.original_source, parse=True)

        self.replacements = []
        self.indent_map = {}
        self.removed = set()

        self.minimize_stmt(self.atok.tree)
        console = Console()

        console.print("minimized:")
        console.print(rich.syntax.Syntax(self.source, "python", line_numbers=True))

    def test_with(self, *subs) -> bool:
        "returns True if removal was successful and the bug still exists"

        new_replacements = []

        for source_range, replacement in subs:

            if isinstance(source_range, ast.AST):
                start = end = source_range

            elif isinstance(source_range, (list, tuple)):
                start = source_range[0]
                end = source_range[-1]
            else:
                raise TypeError

            start = start_offset(start)
            end = end_offset(end)

            new_replacements.append((start, end, replacement))

        return self.test_code(new_replacements)

    def test_code(self, replacements=[], indent_map={}, removed=set()):

        replacements = [*self.replacements, *replacements]
        removed = {*self.removed, *removed}

        new_replacements = list(replacements)

        indent_map = self.indent_map | indent_map

        for indent_node in indent_map:

            if indent_node in removed:
                continue

            indenting = indent_node
            while indenting in indent_map:
                indenting = indent_map[indenting]

            if isinstance(indent_node,ast.FunctionDef):
                def is_decorator(t):
                    return t.type == token.OP and t.string == "@"

                positions = self.get_indents(indent_node)
                if is_decorator(indent_node.first_token):
                    print("indent decorator")
                    positions = []
                    t = indent_node.first_token

                    while True:
                        positions.append(self.get_indent(t))
                        if not is_decorator(t):
                            assert t.string in ("def", "class"), t
                            break
                        t = self.atok.get_token(t.start[0] + 1, t.start[1])
            else:
                positions = self.get_indents(indent_node)

            positions=[(a,b) for a,b in positions if not any( l<=a and b<=r for l,r,_ in replacements )  ]


            new_replacements += [
                (*position, self.get_indent_text(indenting)) for position in positions
            ]

        new_replacements.sort()

        for a, b in zip(new_replacements, new_replacements[1:]):

            if a[1] > b[0]:
                console = Console()
                line_numbers=asttokens.LineNumbers(self.original_source)

                end=line_numbers.offset_to_line(a[1])
                start=line_numbers.offset_to_line(b[0])
                a_start=line_numbers.offset_to_line(a[0])
                b_end=line_numbers.offset_to_line(b[1])

                print(start,end)
                syntax=rich.syntax.Syntax(self.original_source, "python", line_numbers=True,line_range=(a_start[0],b_end[0]))
                syntax.stylize_range("on red",start,end)
                syntax.stylize_range("on blue",a_start,start)
                syntax.stylize_range("on blue",end,b_end)
                console.print(syntax)
                traceback.print_stack()
                sys.exit(1)

        def new_code(replacements):
            lines = asttokens.util.replace(
                self.original_source, replacements
            ).splitlines()
            return "\n".join(l for l in lines if l.strip())

        old_source = self.source
        new_source = new_code(new_replacements)

        self.source = new_source

        try:
            with no_output():
                compile(self.source, "<source>", "exec")
        except SyntaxError as e:
            console = Console()

            console.print("without modification:")
            console.print(rich.syntax.Syntax(old_source, "python", line_numbers=True))

            console.print("with modification:")
            console.print(rich.syntax.Syntax(new_source, "python", line_numbers=True))
            rprint("error", e)
            traceback.print_stack()
            sys.exit(1)

        bug_exists = self.checker(self.source)

        if not bug_exists:
            self.source = old_source
        else:

            self.replacements = replacements
            self.indent_map = indent_map

        return bug_exists

    def test_without(self, source_range) -> bool:

        return self.test_with((source_range, ""))

    def get_indent(self, node):
        "returns source_range"
        if isinstance(node, ast.AST):
            first = node.first_token
        else:
            first = node
        before = self.atok.prev_token(first, include_extra=True)

        while before.type not in (token.NEWLINE, token.NL):
            before = self.atok.prev_token(before, include_extra=True)

        return (end_offset(before), start_offset(first))


    def get_indents(self,node):
        if isinstance(node,ast.Try):
            tokens=[node,*node.handlers]
            return [self.get_indent(token) for token in tokens]
        else:
            return [self.get_indent(node)]

    def get_indent_text(self, node):
        start, end = self.get_indent(node)
        result = self.original_source[start:end]

        assert all(c in "\t " for c in result), repr(result)

        return result

    def try_only_stmts(self, outer_node, inner_stmts):

        new_map = {stmt: outer_node for stmt in inner_stmts}

        inner_start = self.get_indent(inner_stmts[0])[0]

        removed = [
            (start_offset(outer_node), inner_start, "\n"),
            (end_offset(inner_stmts[-1]), end_offset(outer_node), ""),
        ]
        return self.test_code(removed, new_map)

    def try_only_expr(self, outer_node, inner_node):
        if self.test_with(
            ((start_offset(outer_node), start_offset(inner_node)), ""),
            ((end_offset(inner_node), end_offset(outer_node)), ""),
        ):
            self.minimize_expr(inner_node)
            return True

        return False

    def node_range(self, first_node, last_node):
        return (first_node.first_token.startpos, last_node.last_token.endpos)

    def minimize_stmts(self, stmts):
        if not stmts:
            return

        if self.test_with((stmts[0], "pass"), *[(stmt, "") for stmt in stmts[1:]]):
            return
        to_remove = len(stmts)

        def try_remove(stmts):
            nonlocal to_remove
            # do not try to remove everything because this would produce invalid code
            if len(stmts) < to_remove:
                if self.test_with(*[(stmt, "") for stmt in stmts]):
                    self.removed |= set(stmts)
                    to_remove -= len(stmts)
                    return True

        def binary_remove(stmts):
            if len(stmts) == 0:
                return

            if len(stmts) == 1:
                if not try_remove(stmts):
                    self.minimize_stmt(stmts[0])
                    return

            mid = len(stmts) // 2
            first = stmts[:mid]
            last = stmts[mid:]

            if not try_remove(first):
                binary_remove(first)

            if not try_remove(last):
                binary_remove(last)

        if len(stmts) > 1:
            binary_remove(stmts)

    def minimize_list(self, exprs):
        def extend_comma(node):
            first = node.first_token
            last = node.last_token

            while True:
                next_token = self.atok.next_token(last)
                if next_token.type == token.OP and next_token.string in ")}]":
                    break

                last = next_token
                if last.type == token.OP and last.string == ",":
                    break

            return (first, last.endpos)

        def binary_remove(exprs):
            "returns true if the expressions could be removed"
            if len(exprs) == 0:
                return
            if len(exprs) == 1:
                if not self.test_without(extend_comma(exprs[0])):
                    self.minimize_stmt(exprs[0])
                return

            if self.test_without((exprs[0], extend_comma(exprs[-1])[1])):
                return

            mid = len(exprs) // 2
            first = exprs[:mid]
            last = exprs[mid:]

            binary_remove(first)
            binary_remove(last)

        binary_remove(exprs)

    def minimize_expr(self, expr):
        if self.test_with((expr, "a")):  # replace it just with some name
            return

        if isinstance(expr, ast.Call):
            self.minimize_expr(expr.func)
            if not self.test_without((expr.func.last_token.endpos, expr)):
                self.minimize_list(expr.args + expr.keywords)

        elif isinstance(expr, ast.Attribute):
            self.minimize_expr(expr.value)
            self.test_without((expr.value.last_token.endpos, expr))
        elif isinstance(expr, ast.Name):
            pass
        else:
            assert False, ("unsupported expr", expr)
            print("unsupported expr", expr)

    def minimize_stmt(self, node):
        if isinstance(node, ast.Module):
            self.minimize_stmts(node.body)
        elif isinstance(node, ast.ClassDef):
            self.try_only_stmts(node, node.body)
            self.minimize_stmts(node.body)

        elif isinstance(node, ast.FunctionDef):

            for decorator in node.decorator_list:
                if self.try_only_expr(node, decorator):
                    return
            self.minimize_stmts(node.body)

            self.try_only_stmts(node, node.body)
        elif isinstance(node, ast.If):
            if self.try_only_stmts(node, node.body):
                self.minimize_stmts(node.body)
            elif node.orelse and self.try_only_stmts(node, node.orelse):
                self.minimize_stmts(node.orelse)
            else:
                self.minimize_expr(node.test)
                self.minimize_stmts(node.body)
                self.minimize_stmts(node.orelse)
        elif isinstance(node, ast.Assign):
            self.try_only_expr(node,node.value)

        elif isinstance(node, ast.Try):
            if self.try_only_stmts(node, node.body):
                self.minimize_stmts(node.body)
                return
            for handler in node.handlers:
                if self.try_only_stmts(node, handler.body):
                    self.minimize_stmts(handler.body)
                    return

            for handler in node.handlers:
                if self.try_only_expr(node, handler.type):
                    return 

            self.minimize_stmts(node.body)
            for handler in node.handlers:
                self.minimize_stmts(handler.body)
                self.minimize_expr(handler.type)

        elif isinstance(node, ast.For):
            if self.try_only_stmts(node,node.body):
                self.minimize_stmts(node.body)
                return 

            if self.try_only_stmts(node,node.orelse):
                self.minimize_stmts(node.orelse)
                return 

            self.minimize_expr(node.iter)
            self.minimize_stmts(node.orelse)
            self.minimize_stmts(node.body)


        elif isinstance(node, ast.Expr):
            self.minimize_expr(node.value)
        elif isinstance(node, ast.Return):
            self.try_only_expr(node, node.value)
        else:
            assert False, ("unsupported stmt", node)
            print("unsupported", node)


def minimize(source, checker):

    minimizer = Minimizer(source, checker)

    return minimizer.source
