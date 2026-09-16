#!/usr/bin/env python3
"""
Chord Analysis Web UI Launcher (Python version)

This script performs all necessary setup steps and launches the Streamlit
web interface for the chord analysis tool.

Usage:
    python launch_web_ui.py [options]

    or make it executable:
    chmod +x launch_web_ui.py
    ./launch_web_ui.py [options]

Options:
    --db PATH        Path to database file (default: auto-detect)
    --port PORT      Port to run on (default: 8501)
    --host HOST      Host to bind to (default: localhost)
    --no-browser     Don't open browser automatically
    --help           Show this help message
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path
import sqlite3


# ANSI color codes
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color
    BOLD = '\033[1m'


def print_header(text: str, color: str = Colors.BLUE):
    """Print a formatted header."""
    width = 58
    print(f"\n{color}{'═' * (width + 4)}{Colors.NC}")
    print(f"{color}║{' ' * (width + 2)}║{Colors.NC}")
    padding = (width - len(text)) // 2
    print(f"{color}║  {' ' * padding}{text}{' ' * (width - padding - len(text))}║{Colors.NC}")
    print(f"{color}║{' ' * (width + 2)}║{Colors.NC}")
    print(f"{color}{'═' * (width + 4)}{Colors.NC}\n")


def print_step(step: int, total: int, message: str):
    """Print a step header."""
    print(f"{Colors.YELLOW}[{step}/{total}]{Colors.NC} {message}")


def print_success(message: str, indent: bool = False):
    """Print a success message."""
    prefix = "  " if indent else ""
    print(f"{prefix}{Colors.GREEN}✓ {message}{Colors.NC}")


def print_warning(message: str, indent: bool = False):
    """Print a warning message."""
    prefix = "  " if indent else ""
    print(f"{prefix}{Colors.YELLOW}⚠ {message}{Colors.NC}")


def print_error(message: str):
    """Print an error message."""
    print(f"{Colors.RED}✗ {message}{Colors.NC}")


def check_python_version():
    """Check if Python version is 3.9 or higher."""
    print_step(1, 6, "Checking Python version...")

    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print_error(f"Python {version.major}.{version.minor} found, but 3.9+ is required")
        sys.exit(1)

    print_success(f"Python {version.major}.{version.minor} found")


def setup_venv():
    """Create and/or verify virtual environment."""
    print_step(2, 6, "Setting up virtual environment...")

    venv_dir = Path("venv")

    if not venv_dir.exists():
        print("  Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print_success("Virtual environment created")
    else:
        print_success("Virtual environment exists")

    # Get the python executable in the venv
    if sys.platform == "win32":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"

    if not venv_python.exists():
        print_error(f"Virtual environment Python not found at {venv_python}")
        sys.exit(1)

    return str(venv_python)


def upgrade_pip(venv_python: str):
    """Upgrade pip in the virtual environment."""
    print_step(3, 6, "Checking pip...")

    try:
        subprocess.run(
            [venv_python, "-m", "pip", "install", "--upgrade", "pip", "--quiet"],
            check=True,
            capture_output=True
        )
        print_success("pip up to date")
    except subprocess.CalledProcessError:
        print_warning("Failed to upgrade pip, continuing anyway...")


def install_dependencies(venv_python: str):
    """Install required dependencies."""
    print_step(4, 6, "Installing dependencies...")

    # Check if key dependencies are installed
    needs_install = False

    try:
        subprocess.run(
            [venv_python, "-c", "import streamlit"],
            check=True,
            capture_output=True
        )
    except subprocess.CalledProcessError:
        needs_install = True

    try:
        subprocess.run(
            [venv_python, "-c", "import rich"],
            check=True,
            capture_output=True
        )
    except subprocess.CalledProcessError:
        needs_install = True

    if needs_install:
        print("  Installing required packages...")

        # Install from requirements.txt if available
        requirements_file = Path("requirements.txt")
        if requirements_file.exists():
            subprocess.run(
                [venv_python, "-m", "pip", "install", "-r", "requirements.txt", "--quiet"],
                check=True
            )
        else:
            # Fallback to minimal install
            subprocess.run(
                [venv_python, "-m", "pip", "install", "streamlit", "rich", "pandas", "matplotlib", "--quiet"],
                check=True
            )

        print_success("Dependencies installed")
    else:
        print_success("Dependencies already satisfied")

    # Always ensure the package is installed in editable mode
    try:
        subprocess.run(
            [venv_python, "-c", "import chord_analyzer"],
            check=True,
            capture_output=True
        )
    except subprocess.CalledProcessError:
        print("  Installing chord_analyzer package...")
        subprocess.run(
            [venv_python, "-m", "pip", "install", "-e", ".", "--quiet"],
            check=True
        )
        print_success("chord_analyzer package installed")

    # Check optional dependencies
    try:
        subprocess.run(
            [venv_python, "-c", "import librosa"],
            check=True,
            capture_output=True
        )
        print_success("librosa available (tempo detection enabled)", indent=True)
    except subprocess.CalledProcessError:
        print_warning("librosa not available (tempo detection disabled)", indent=True)
        print("    To enable: pip install librosa")


def find_database(db_path: str = None):
    """Find or create database file."""
    print_step(5, 6, "Checking database...")

    # Auto-detect database if not specified
    if not db_path:
        candidates = [
            Path("output/splice-samples.db"),
            Path("samples.db"),
        ]

        # Add any .db files in current directory
        candidates.extend(Path(".").glob("*.db"))

        for candidate in candidates:
            if candidate.exists():
                db_path = str(candidate)
                break

    if db_path and Path(db_path).exists():
        print_success(f"Database found: {db_path}")

        # Get database stats
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM samples")
            count = cursor.fetchone()[0]
            conn.close()

            if count > 0:
                print_success(f"{count} samples loaded", indent=True)
            else:
                print_warning("Database is empty", indent=True)
        except Exception:
            print_warning("Could not read database stats", indent=True)

        return db_path
    else:
        print_warning("No database found")
        print()
        print("The web UI will start, but you'll need to analyze samples first.")
        print("To analyze samples, run:")
        print()
        print(f"{Colors.BLUE}  python -m chord_analyzer analyze --csv-dir ./chord_data --db samples.db{Colors.NC}")
        print()

        # Return default database name
        return "samples.db"


def launch_streamlit(venv_python: str, db_path: str, port: int, host: str, open_browser: bool):
    """Launch the Streamlit web UI."""
    print_step(6, 6, "Launching web UI...")
    print()

    # Build streamlit arguments
    streamlit_args = [
        venv_python,
        "-m",
        "streamlit",
        "run",
        "run_web.py",
        f"--server.port={port}",
        f"--server.address={host}",
    ]

    if not open_browser:
        streamlit_args.append("--server.headless=true")

    # Set environment variables
    env = os.environ.copy()
    env["STREAMLIT_DB_PATH"] = db_path
    env["STREAMLIT_SERVER_MAX_UPLOAD_SIZE"] = "200"

    # Print success message
    print(f"{Colors.GREEN}{'═' * 62}{Colors.NC}")
    print(f"{Colors.GREEN}║{' ' * 60}║{Colors.NC}")
    print(f"{Colors.GREEN}║  ✓ Web UI is starting!{' ' * 37}║{Colors.NC}")
    print(f"{Colors.GREEN}║{' ' * 60}║{Colors.NC}")
    print(f"{Colors.GREEN}║  Open your browser to:{' ' * 37}║{Colors.NC}")
    url = f"http://{host}:{port}"
    padding = 60 - len(url) - 4
    print(f"{Colors.GREEN}║    {url}{' ' * padding}║{Colors.NC}")
    print(f"{Colors.GREEN}║{' ' * 60}║{Colors.NC}")
    print(f"{Colors.GREEN}║  Press Ctrl+C to stop{' ' * 37}║{Colors.NC}")
    print(f"{Colors.GREEN}║{' ' * 60}║{Colors.NC}")
    print(f"{Colors.GREEN}{'═' * 62}{Colors.NC}\n")

    # Launch Streamlit
    try:
        subprocess.run(streamlit_args, env=env)
    except KeyboardInterrupt:
        print("\n\nShutting down web UI...")
        sys.exit(0)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Launch Chord Analysis Web UI with automatic setup",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--db", type=str, help="Path to database file (default: auto-detect)")
    parser.add_argument("--port", type=int, default=8501, help="Port to run on (default: 8501)")
    parser.add_argument("--host", type=str, default="localhost", help="Host to bind to (default: localhost)")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")

    args = parser.parse_args()

    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    # Print header
    print_header("🎵  Chord Analysis Web UI Launcher  🎵")

    # Run setup steps
    check_python_version()
    venv_python = setup_venv()
    upgrade_pip(venv_python)
    install_dependencies(venv_python)
    db_path = find_database(args.db)

    # Launch
    launch_streamlit(
        venv_python=venv_python,
        db_path=db_path,
        port=args.port,
        host=args.host,
        open_browser=not args.no_browser
    )


if __name__ == "__main__":
    main()
