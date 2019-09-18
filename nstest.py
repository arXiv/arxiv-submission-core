"""Test that there is no core/arxiv/__init__.py
that will mess up the namespaces"""

import os

file = "core/arxiv/__init__.py"
print(f"The existence of {file} will cause modules "
      "from other packages to not be found.\n"
      "It only exists due to current deficiencies in mypy.\n"
      "See https://packaging.python.org/guides/packaging-namespace-packages\n")
try:
    os.remove(file)
    print(f"GOOD: found and deleted {file}")
    exit(0)
except FileNotFoundError:
    print(f"GOOD: {file} clear")
    exit(0)
# anything else causes an error
