# minimize source code

If you build a linter, formatter or any other tool which has to analyse python source code you might end up searching bugs in pretty large input files.


`pysource_minimize` is able to remove everything from the python source which is not related to the problem.

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
