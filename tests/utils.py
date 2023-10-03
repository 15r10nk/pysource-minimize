from contextlib import contextmanager

import pysource_minimize._minimize


@contextmanager
def testing_enabled():
    old_value = pysource_minimize._minimize.TESTING
    pysource_minimize._minimize.TESTING = True
    try:
        yield
    finally:
        pysource_minimize._minimize.TESTING = old_value
