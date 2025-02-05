[![pypi version](https://img.shields.io/pypi/v/pysource-minimize.svg)](https://pypi.org/project/pysource-minimize/)
![Python Versions](https://img.shields.io/pypi/pyversions/pysource-minimize)
![PyPI - Downloads](https://img.shields.io/pypi/dw/pysource-minimize)
[![GitHub Sponsors](https://img.shields.io/github/sponsors/15r10nk)](https://github.com/sponsors/15r10nk)

# pysource-minimize

If you build a linter, formatter or any other tool which has to analyse python source code you might end up searching bugs in pretty large input files.

`pysource_minimize` is able to remove everything from the python source which is not related to the problem.

## CLI

You can use `pysource-minimize` from the command line like follow:

```bash
pysource-minimize --file bug.py --track "Assertion" -- python bug.py
```

This will run `python bug.py` and try to find the string "Assertion" in the output.
The `--file bug.py` gets minimized as long as "Assertion" is part of the output of the command.

> [!WARNING]
> Be careful when you execute code which gets minimized.
> It might be that some combination of the code you minimize erases your hard drive
> or does other unintended things.

![example](example.gif)



## API
Example:
``` pycon
>>> from pysource_minimize import minimize

>>> source = """
... def f():
...     print("bug"+"other string")
...     return 1+1
... f()
... """

>>> print(minimize(source, lambda new_source: "bug" in new_source))
"""bug"""

```
