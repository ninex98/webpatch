"""Read the single version declaration without importing the application."""
import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def package_version():
    tree = ast.parse((ROOT / "src/webpatch/__init__.py").read_text())
    values = [ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets)]
    if len(values) != 1 or not isinstance(values[0], str):
        raise ValueError("Invalid package version")
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", values[0]):
        raise ValueError("Release version must be MAJOR.MINOR.PATCH")
    return values[0]


if __name__ == "__main__":
    print(package_version())
