import os
import random

import pytest

from . import session_config

os.environ["PYSOURCE_TESTING"] = "1"


@pytest.fixture(params=range(0))
def seed():
    return random.randrange(0, 100000000)


def pytest_report_header(config):
    if config.getoption("verbose") > 0:
        session_config.verbose = True


def pytest_addoption(parser, pluginmanager):
    parser.addoption(
        "--generate-samples",
        action="store_true",
        help="Config file to use, defaults to %(default)s",
    )


def pytest_sessionfinish(session, exitstatus):
    print("exitstatus", exitstatus)

    if exitstatus == 0 and session.config.option.generate_samples:
        from .test_remove_one import generate_remove_one
        from .test_needle import generate_needle

        for i in range(2):
            generate_needle()
            generate_remove_one()

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
