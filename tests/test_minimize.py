from unittest.mock import Mock

import pytest
from pysource_minimize import CouldNotMinimize
from pysource_minimize import minimize


@pytest.mark.parametrize("first_check_result", [False, True])
def test_minimize_raises_when_checker_stops_reproducing(first_check_result):
    checker = Mock(side_effect=[first_check_result, False])

    with pytest.raises(CouldNotMinimize):
        minimize("x = 1", checker)

    assert checker.call_count == (2 if first_check_result else 1)


def test_minimize_preserves_value_error_from_checker():
    error = ValueError("error in checker")
    checker = Mock(side_effect=[True, error])

    with pytest.raises(ValueError) as exc_info:
        minimize("x = 1", checker)

    assert exc_info.value is error
