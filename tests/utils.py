from contextlib import contextmanager

import pysource_minimize._minimize_base


@contextmanager
def testing_enabled():
    old_value = pysource_minimize._minimize_base.TESTING
    pysource_minimize._minimize_base.TESTING = True
    try:
        yield
    finally:
        pysource_minimize._minimize_base.TESTING = old_value
