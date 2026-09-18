#!/usr/bin/env python3
"""Stable convenience entrypoint; implementation lives with the spec bundle."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "spec" / "tools" / "specctl.py"), run_name="__main__")
