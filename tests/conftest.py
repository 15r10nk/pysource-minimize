import random

import pytest


@pytest.fixture(params=range(0))
def seed():
    return random.randrange(0, 100000000)


def pytest_addoption(parser, pluginmanager):
    parser.addoption(
        "--generate-samples",
        action="store_true",
        help="Config file to use, defaults to %(default)s",
    )


def pytest_sessionfinish(session, exitstatus):
    if exitstatus == 0 and session.config.option.generate_samples:
        from .test_needle import generate_needle

        generate_needle()

    # teardown_stuff
