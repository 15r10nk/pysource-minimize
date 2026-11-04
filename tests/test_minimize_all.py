from pathlib import Path

from inline_snapshot import snapshot
from inline_snapshot.extra import raises
from pysource_minimize._minimize import minimize_all


def test_minimize_all():
    files = {
        Path("bug1.py"): """\
a=1+2+3
""",
        Path("bug2.py"): """\
print(d[a],"b")
""",
        Path("bug3.py"): """\
x=2
""",
    }

    def check(sources, current_file):
        globals = {"d": {0: 1, 5: 8}}
        try:
            for path, source in sorted(sources.items(), key=lambda i: i[0].stem):
                if source is not None:
                    exec(source, globals)
        except KeyError:
            return True
        except:
            return False
        return False

    assert minimize_all(files, check) == (
        snapshot(
            {
                Path("bug1.py"): "a = 1",
                Path("bug2.py"): "d[a]",
                Path("bug3.py"): None,
            }
        )
    )


def test_minimize_all_raises_when_checker_stops_reproducing():
    """Test the exception raised if a callback stops reproducing on the original source.

    For example, a callback checking for a timeout might return `True` only when
    running the files exceeds its time limit. If their runtime is close to that
    limit, varying execution time can make the next check return False for the same
    files.
    """
    reproductions = iter((True, False))

    def checker(sources, current_file):
        return sources[current_file] is not None and next(reproductions)

    with raises(
        snapshot("CouldNotMinimize: checker return False: nothing to minimize here")
    ):
        minimize_all({Path("bug.py"): "x = 1"}, checker)
