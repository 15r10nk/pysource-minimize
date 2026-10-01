import sys

import pytest
from pysource_minimize import minimize


@pytest.mark.skipif(
    sys.version_info < (3, 14), reason="template strings are a 3.14 feature"
)
def test_template_string():
    assert minimize("t'{bug +a } abc'", lambda source: "t'{bug" in source) == "t'{bug}'"


def test_f_string_minimize_does_not_create_invalid_constant_value():
    assert (
        minimize("f'{bug}'", lambda source: source.startswith("f") and "bug" in source)
        == "f'{bug}'"
    )


@pytest.mark.skipif(
    sys.version_info < (3, 14), reason="template strings are a 3.14 feature"
)
def test_template_string_minimize_does_not_create_invalid_constant_value():
    assert (
        minimize("t'{bug}'", lambda source: source.startswith("t") and "bug" in source)
        == "t'{bug}'"
    )


@pytest.mark.skipif(
    sys.version_info < (3, 14), reason="template strings are a 3.14 feature"
)
def test_template_string_minimize_nested_f_string_value():
    assert (
        minimize(
            "t'{f'{bug}'}'",
            lambda source: source.startswith("t") and "f" in source and "bug" in source,
        )
        == "t\"{f'{bug}'}\""
    )
