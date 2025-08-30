import sys

import pytest
from pysource_minimize import minimize


@pytest.mark.skipif(
    sys.version_info < (3, 14), reason="template strings are a 3.14 feature"
)
def test_template_string():
    assert minimize("t'{bug +a } abc'", lambda source: "t'{bug" in source) == "t'{bug}'"
