"""Load the repository root as the ``pantheon`` package: the plugin's folder name is not importable."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if "pantheon" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "pantheon", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["pantheon"] = module
    spec.loader.exec_module(module)
