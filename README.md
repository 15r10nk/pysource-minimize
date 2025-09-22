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

This executes `python bug.py` and tries to find the string “Assertion” in the output.
The `---file bug.py` will be minimized as long as “assertion” is part of the output of the command.
The `--file` option can be specified multiple times and there is also an `--dir` option which can be used to search directories recursively for Python files.

> [!WARNING]
> Be careful when you execute code which gets minimized.
> It might be that some combination of the code you minimize erases your hard drive
> or does other unintended things.

![example](example.gif)



## API

Example for single files:
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

This example minimizes multiple files and searches for sets which have 2 common elements:
``` pycon
>>> from pathlib import Path
>>> from typing import Dict
>>> from pprint import pprint
>>> from pysource_minimize._minimize import minimize_all
>>> sources = {
...     Path(
...         "a.py"
...     ): """\
... l={1,81894,9874,89228,897985,897498,9879,9898}
...     """,
...     Path(
...         "b.py"
...     ): """\
... l={5,81894,9274,89218,897985,897298,9879,9898}
...     """,
...     Path(
...         "c.py"
...     ): """\
... l={0,81894,9874,89218,897985,897498,9879,9298}
...     """,
... }
>>> def check(sources: Dict[Path, str | None], current_filename: Path) -> bool:
...     # current_filename can be used for progress output
...     # print(f"working on {current_filename} ...")
...     sets = []
...     for source in sources.values():
...         if source is not None:
...             globals = {}
...             try:
...                 exec(source, globals)
...             except:
...                 return False
...             if "l" not in globals:
...                 return False
...             sets.append(globals["l"])
...     return (
...         len(sets) >= 2
...         and all(isinstance(s, set) for s in sets)
...         and len(set.intersection(*sets)) >= 2
...     )
>>> pprint(minimize_all(sources, checker=check))
{PosixPath('a.py'): None,
 PosixPath('b.py'): 'l = {81894, 0}',
 PosixPath('c.py'): 'l = {0, 81894}'}
```

You might think that there are no two zeros in the original sets.
This problem can occur if your check function is not specific enough.
*pysource-minimize* tries to minimize numbers and strings, does so for one of the sets and finds that it satisfies your check.
It generates new code during the minimization and can only use the `check` function to know if the solution is correct.
This kind of problem can be solved by using a more precise check function or a `--track` argument when using the CLI.
For example, you can add a check that all numbers in the set must be non-zero.
However, this problem will not occur if you are looking for real minimal examples that throw certain exceptions.
The worst that can happen here is that *pysource-minimize* finds another example that triggers the same problem.

<details>
  <summary>fixed check function</summary>

``` pycon
>>> from pathlib import Path
>>> from typing import Dict
>>> from pprint import pprint
>>> from pysource_minimize._minimize import minimize_all
>>> sources = {
...     Path(
...         "a.py"
...     ): """\
... l={1,81894,9874,89228,897985,897498,9879,9898}
...     """,
...     Path(
...         "b.py"
...     ): """\
... l={5,81894,9274,89218,897985,897298,9879,9898}
...     """,
...     Path(
...         "c.py"
...     ): """\
... l={0,81894,9874,89218,897985,897498,9879,9298}
...     """,
... }
>>> def check(sources: Dict[Path, str | None], current_filename: Path) -> bool:
...     # current_filename can be used for progress output
...     # print(f"working on {current_filename} ...")
...     sets = []
...     for source in sources.values():
...         if source is not None:
...             globals = {}
...             try:
...                 exec(source, globals)
...             except:
...                 return False
...             if "l" not in globals:
...                 return False
...             sets.append(globals["l"])
...     return (
...         len(sets) >= 2
...         and all(isinstance(s, set) for s in sets)
...         and len(result := set.intersection(*sets)) >= 2
...         and 0 not in result
...     )
>>> pprint(minimize_all(sources, checker=check))
{PosixPath('a.py'): None,
 PosixPath('b.py'): 'l = {81894, 89218}',
 PosixPath('c.py'): 'l = {81894, 89218}'}
```

</details>

<!--[[[cog
import requests,cog

url = "https://raw.githubusercontent.com/15r10nk/sponsors/refs/heads/main/sponsors_readme.md"
response = requests.get(url)
response.raise_for_status()  # Raise an exception for bad status codes
cog.out(response.text)
]]]-->
## Sponsors

I would like to thank my sponsors. Without them, I would not be able to invest so much time in my projects.

### Silver sponsor 🥈

<p align="center">
  <a href="https://pydantic.dev/logfire">
    <img src="https://pydantic.dev/assets/for-external/pydantic_logfire_logo_endorsed_lithium_rgb.svg" alt="logfire" width="300"/>
  </a>
</p>
<!--[[[end]]]-->
