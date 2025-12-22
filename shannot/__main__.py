#!/usr/bin/env python3
"""
Main entry point for shannot CLI.

This file establishes package context by importing from the shannot package,
which allows relative imports in shannot.cli to work correctly when compiled with Nuitka.
"""

import os
import sys

# Force unbuffered - exactly like the working test
os.environ["PYTHONUNBUFFERED"] = "1"

# Import from the package (not relative import) - exactly like the working test
from shannot.cli import main

if __name__ == "__main__":
    # Call main exactly like the working test
    exit_code = main()
    sys.exit(exit_code)
