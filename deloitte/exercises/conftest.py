"""Load the learner's implementation, or the reference solution.

    pytest exercises                         # your code in exercises/starter/
    EXERCISE_IMPL=solutions pytest exercises # reference solutions (what CI runs)
"""

import importlib.util
import os
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


@pytest.fixture
def impl(request):
    def load(name: str):
        folder = os.getenv("EXERCISE_IMPL", "starter")
        path = HERE / folder / f"{name}.py"
        spec = importlib.util.spec_from_file_location(f"{folder}_{name}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    return load
