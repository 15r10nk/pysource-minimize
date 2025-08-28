import os
import re
import sys
from pathlib import Path
from traceback import format_tb
from typing import List
from typing import Optional

import pytest
from click.testing import CliRunner
from inline_snapshot import snapshot
from pysource_minimize.__main__ import main


def minimize_files(
    files,
    track,
    extra_args=[],
    minimize: Optional[List[str]] = None,
    run=None,
    expected_output="",
    expected_files={},
):

    if minimize is None:
        minimize = list(files.keys())

    if run is None:
        run = [sys.executable, minimize[0]]

    runner = CliRunner()

    with runner.isolated_filesystem():

        for name, source in files.items():
            Path(name).write_text(source)

        os.environ["COLUMNS"] = "80"

        result = runner.invoke(
            main,
            [
                *[f"--file={name}" for name in minimize],
                *extra_args,
                "--track",
                track,
                "--",
                *run,
            ],
        )

        if result.exc_info:
            print("\n".join(format_tb(result.exc_info[2])))
            print(result.exception)

        output = re.sub("'/.*python3?", "'python", result.output)

        assert output == expected_output

        new_files = {
            name: p.read_text() if (p := Path(name)).exists() else None
            for name in files
        }

        if new_files == files:
            assert "<unchanged>" == expected_files
        else:
            assert new_files == expected_files


def test_minimize_multiple_files():
    files = {
        "bug.py": """\
from var_a import a
from var_d import d
print(d[a],"b")
""",
        "var_a.py": """\
a=1+2+3
""",
        "var_d.py": """\
d={0:1,5:8}
""",
    }

    minimize_files(
        files,
        track="KeyError",
        minimize=["bug.py", "var_a.py"],
        expected_output=snapshot(
            """\
You can support my work by sponsoring me on GitHub ❤ github.com/sponsors/15r10nk


The minimized code is:
╭─ bug.py ─────────────────────────────────────────────────────────────────────╮
│   1 from var_a import a                                                      │
│   2 from var_d import d                                                      │
│   3 d[a]                                                                     │
╰──────────────────────────────────────────────────────────────────────────────╯

╭─ var_a.py ───────────────────────────────────────────────────────────────────╮
│   1 a = 1                                                                    │
╰──────────────────────────────────────────────────────────────────────────────╯

Please report if your code can be further simplified. This will help \n\
pysource-minimize to improve further.

original files restored
"""
        ),
        expected_files=snapshot("<unchanged>"),
    )


def test_format():
    files = {
        "bug.py": f"""\
very_long_name=10
l=[{'very_long_name,'*10}]
print("sum",sum(l))
""",
    }

    minimize_files(
        files,
        track="sum 100",
        extra_args=["--format", "-w"],
        expected_output=snapshot(
            """\
You can support my work by sponsoring me on GitHub ❤ github.com/sponsors/15r10nk


The minimized code is:
╭─ bug.py ─────────────────────────────────────────────────────────────────────╮
│    1 very_long_name = 10                                                     │
│    2 l = [                                                                   │
│    3     very_long_name,                                                     │
│    4     very_long_name,                                                     │
│    5     very_long_name,                                                     │
│    6     very_long_name,                                                     │
│    7     very_long_name,                                                     │
│    8     very_long_name,                                                     │
│    9     very_long_name,                                                     │
│   10     very_long_name,                                                     │
│   11     very_long_name,                                                     │
│   12     very_long_name,                                                     │
│   13 ]                                                                       │
│   14 print("sum", sum(l))                                                    │
│   15                                                                         │
╰──────────────────────────────────────────────────────────────────────────────╯

Please report if your code can be further simplified. This will help \n\
pysource-minimize to improve further.

minimized files saved
"""
        ),
        expected_files=snapshot(
            {
                "bug.py": """\
very_long_name = 10
l = [
    very_long_name,
    very_long_name,
    very_long_name,
    very_long_name,
    very_long_name,
    very_long_name,
    very_long_name,
    very_long_name,
    very_long_name,
    very_long_name,
]
print("sum", sum(l))
"""
            }
        ),
    )


def test_no_track():
    files = {
        "bug.py": f"""\
print("aaaa")
""",
    }

    minimize_files(
        files,
        track="bbbb",
        expected_output=snapshot(
            """\
I don't know what you want to minimize for.
'bbbb' is not a string which in the stdout/stderr of 'python bug.py'
"""
        ),
        expected_files=snapshot("<unchanged>"),
    )


@pytest.mark.skipif(
    sys.version_info < (3, 9), reason="unparse behaves different for 3.8"
)
def test_writeback():
    files = {
        "bug.py": f"""\
print("aa"+"aa","bbb")
""",
    }

    for args in (("-w",), ()):
        key = " ".join(args)
        minimize_files(
            files,
            track="aaa",
            extra_args=args,
            expected_output=snapshot(
                {
                    "-w": """\
You can support my work by sponsoring me on GitHub ❤ github.com/sponsors/15r10nk


The minimized code is:
╭─ bug.py ─────────────────────────────────────────────────────────────────────╮
│   1 print('a' + 'aa')                                                        │
╰──────────────────────────────────────────────────────────────────────────────╯

Please report if your code can be further simplified. This will help \n\
pysource-minimize to improve further.

minimized files saved
""",
                    """""": """\
You can support my work by sponsoring me on GitHub ❤ github.com/sponsors/15r10nk


The minimized code is:
╭─ bug.py ─────────────────────────────────────────────────────────────────────╮
│   1 print('a' + 'aa')                                                        │
╰──────────────────────────────────────────────────────────────────────────────╯

Please report if your code can be further simplified. This will help \n\
pysource-minimize to improve further.

original files restored
""",
                }
            )[key],
            expected_files=snapshot(
                {"-w": {"bug.py": "print('a' + 'aa')"}, """""": "<unchanged>"}
            )[key],
        )
