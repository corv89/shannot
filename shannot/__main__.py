"""CLI entrypoint for shannot package.

This module allows running shannot as a module:
    python -m shannot run ls /
"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
