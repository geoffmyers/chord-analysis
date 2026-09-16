"""
Entry point for running the package as a module.

Usage:
    python -m chord_analyzer [command] [options]
"""

from .cli import main

if __name__ == "__main__":
    exit(main())
