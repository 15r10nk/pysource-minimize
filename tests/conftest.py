import os

from . import session_config

os.environ["PYSOURCE_TESTING"] = "1"


def pytest_report_header(config):
    if config.getoption("verbose") > 0:
        session_config.verbose = True


def pytest_addoption(parser, pluginmanager):
    parser.addoption(
        "--generate-samples",
        type=str,
        nargs="?",
        const="all",
        default=None,
        help="Config file to use, defaults to %(default)s",
    )


def pytest_sessionfinish(session, exitstatus):

    opts = session.config.option.generate_samples

    assert opts in (None, "all", "needle", "remove-one", "remove-children")

    if exitstatus == 0 and opts is not None:
        from .test_remove_one import generate_remove_one
        from .test_needle import generate_needle
        from .test_remove_children import generate_remove_children

        for i in range(4):
            if opts in ("all", "needle"):
                generate_needle()
            if opts in ("all", "remove-one"):
                generate_remove_one()
            if opts in ("all", "remove-children"):
                generate_remove_children()

    # teardown_stuff


from contextlib import contextmanager

depth = 0


@contextmanager
def ctx(msg):
    global depth
    print("│" * depth + "┌", msg)
    depth += 1
    try:
        yield
    finally:
        depth -= 1
        print("│" * depth + "└", msg)


import textwrap


def ctx_print(*a):
    s = " ".join(str(e) for e in a)
    prefix = "│" * (depth)
    print(textwrap.indent(s, prefix, lambda line: True))


__builtins__["ctx"] = ctx
__builtins__["ctx_print"] = ctx_print
