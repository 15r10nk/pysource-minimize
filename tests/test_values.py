from pysource_minimize import minimize


def test_minimize_int():
    def contains_bug(source):
        try:
            return eval(source) > 70
        except SyntaxError:
            return False

    assert eval(minimize("100", contains_bug)) == 71


def test_minimize_fload():
    def contains_bug(source):
        try:
            return eval(source) > 70.0
        except SyntaxError:
            return False

    assert 70 <= eval(minimize("100.0", contains_bug)) <= 70.1
