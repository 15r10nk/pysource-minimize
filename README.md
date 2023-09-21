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
