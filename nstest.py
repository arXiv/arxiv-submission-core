"""Test that there is no core/arxiv/__init__.py
that will mess up the namespaces"""

import os

file = "core/arxiv/__init__.py"
print(f"The existance of {file} will cuase modules "
      "from other packages to not be found.\n"
      "It only exits due to deficiences with mypy.\n"
      "See https://packaging.python.org/guides/packaging-namespace-packages\n")
try:
    os.remove(file)
    print(f"GOOD: found and deleted {file}")
    exit(0)
except FileNotFoundError:
    print(f"GOOD: {file} clear")
    exit(0)
# anything else causes an error
