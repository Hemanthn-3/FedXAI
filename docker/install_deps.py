"""Install all project runtime dependencies from pyproject.toml, skipping torch.

This script is used during Docker builds to install deps in a cacheable layer
BEFORE the source code is copied. Torch must already be installed (CPU-only)
before this runs so pip skips the CUDA variant.
"""
import subprocess
import sys

import tomllib

with open("pyproject.toml", "rb") as f:
    data = tomllib.load(f)

deps = [
    d for d in data["project"]["dependencies"]
    if not d.lower().startswith("torch")
]

if deps:
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--no-cache-dir"] + deps
    )
