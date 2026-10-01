from pathlib import Path

from inline_snapshot import snapshot
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
