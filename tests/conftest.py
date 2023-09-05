import random

import pytest


@pytest.fixture(params=range(0))
def seed():
    return random.randrange(0, 100000000)
