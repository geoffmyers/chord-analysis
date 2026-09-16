#!/bin/bash

###############################################################################
# Chord Analysis Web UI Launcher
#
# This script performs all necessary setup steps and launches the Streamlit
# web interface for the chord analysis tool.
#
# Usage: ./launch-web-ui.sh [options]
#
# Options:
#   --db PATH        Path to database file (default: auto-detect)
#   --port PORT      Port to run on (default: 8501)
#   --host HOST      Host to bind to (default: localhost)
#   --no-browser     Don't open browser automatically
#   --help           Show this help message
###############################################################################

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Default options
DB_PATH=""
PORT="8501"
HOST="localhost"
OPEN_BROWSER="true"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --db)
            DB_PATH="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --no-browser)
            OPEN_BROWSER="false"
            shift
            ;;
        --help)
            echo "Chord Analysis Web UI Launcher"
            echo ""
            echo "Usage: ./launch-web-ui.sh [options]"
            echo ""
            echo "Options:"
            echo "  --db PATH        Path to database file (default: auto-detect)"
            echo "  --port PORT      Port to run on (default: 8501)"
            echo "  --host HOST      Host to bind to (default: localhost)"
            echo "  --no-browser     Don't open browser automatically"
            echo "  --help           Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                                                          ║${NC}"
echo -e "${BLUE}║         🎵  Chord Analysis Web UI Launcher  🎵          ║${NC}"
echo -e "${BLUE}║                                                          ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

###############################################################################
# Step 1: Check Python version
###############################################################################
echo -e "${YELLOW}[1/6]${NC} Checking Python version..."

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 not found!${NC}"
    echo "Please install Python 3.9 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [[ $PYTHON_MAJOR -lt 3 ]] || [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -lt 9 ]]; then
    echo -e "${RED}✗ Python $PYTHON_VERSION found, but 3.9+ is required${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"

###############################################################################
# Step 2: Create/activate virtual environment
###############################################################################
echo -e "${YELLOW}[2/6]${NC} Setting up virtual environment..."

VENV_DIR="venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment exists${NC}"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"
echo -e "${GREEN}✓ Virtual environment activated${NC}"

###############################################################################
# Step 3: Upgrade pip
###############################################################################
echo -e "${YELLOW}[3/6]${NC} Checking pip..."

python -m pip install --upgrade pip --quiet
echo -e "${GREEN}✓ pip up to date${NC}"

###############################################################################
# Step 4: Install dependencies
###############################################################################
echo -e "${YELLOW}[4/6]${NC} Installing dependencies..."

# Check if requirements are already satisfied
NEEDS_INSTALL=false

# Check for key dependencies
if ! python -c "import streamlit" 2>/dev/null; then
    NEEDS_INSTALL=true
fi

if ! python -c "import rich" 2>/dev/null; then
    NEEDS_INSTALL=true
fi

if [ "$NEEDS_INSTALL" = true ]; then
    echo "  Installing required packages..."

    # Install in development mode with web extras
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt --quiet
    else
        # Fallback to minimal install
        pip install streamlit rich pandas matplotlib --quiet
    fi

    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${GREEN}✓ Dependencies already satisfied${NC}"
fi

# Always ensure the package is installed in editable mode
if ! python -c "import chord_analyzer" 2>/dev/null; then
    echo "  Installing chord_analyzer package..."
    pip install -e . --quiet
    echo -e "${GREEN}✓ chord_analyzer package installed${NC}"
fi

# Check optional dependencies
if python -c "import librosa" 2>/dev/null; then
    echo -e "${GREEN}  • librosa available (tempo detection enabled)${NC}"
else
    echo -e "${YELLOW}  • librosa not available (tempo detection disabled)${NC}"
    echo "    To enable: pip install librosa"
fi

###############################################################################
# Step 5: Locate or create database
###############################################################################
echo -e "${YELLOW}[5/6]${NC} Checking database..."

# Auto-detect database if not specified
if [ -z "$DB_PATH" ]; then
    # Look for databases in common locations
    if [ -f "output/splice-samples.db" ]; then
        DB_PATH="output/splice-samples.db"
    elif [ -f "samples.db" ]; then
        DB_PATH="samples.db"
    elif [ -f "*.db" ] 2>/dev/null; then
        DB_PATH=$(ls -t *.db 2>/dev/null | head -n1)
    fi
fi

if [ -n "$DB_PATH" ] && [ -f "$DB_PATH" ]; then
    echo -e "${GREEN}✓ Database found: $DB_PATH${NC}"

    # Get database stats
    SAMPLE_COUNT=$(python3 -c "
import sqlite3
try:
    conn = sqlite3.connect('$DB_PATH')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM samples')
    count = cursor.fetchone()[0]
    conn.close()
    print(count)
except:
    print(0)
" 2>/dev/null || echo "0")

    if [ "$SAMPLE_COUNT" -gt 0 ]; then
        echo -e "${GREEN}  • $SAMPLE_COUNT samples loaded${NC}"
    else
        echo -e "${YELLOW}  • Database is empty${NC}"
    fi

    # Export for Streamlit to use
    export STREAMLIT_DB_PATH="$DB_PATH"
else
    echo -e "${YELLOW}⚠ No database found${NC}"
    echo ""
    echo "The web UI will start, but you'll need to analyze samples first."
    echo "To analyze samples, run:"
    echo ""
    echo -e "${BLUE}  python -m chord_analyzer analyze --csv-dir ./chord_data --db samples.db${NC}"
    echo ""

    # Create empty database so web UI doesn't error
    DB_PATH="samples.db"
    export STREAMLIT_DB_PATH="$DB_PATH"
fi

###############################################################################
# Step 6: Launch Streamlit
###############################################################################
echo -e "${YELLOW}[6/6]${NC} Launching web UI..."
echo ""

# Build streamlit arguments
STREAMLIT_ARGS=(
    "run_web.py"
    "--server.port=$PORT"
    "--server.address=$HOST"
)

if [ "$OPEN_BROWSER" = "false" ]; then
    STREAMLIT_ARGS+=("--server.headless=true")
fi

# Set Streamlit config
export STREAMLIT_SERVER_MAX_UPLOAD_SIZE=200

echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                          ║${NC}"
echo -e "${GREEN}║  ✓ Web UI is starting!                                  ║${NC}"
echo -e "${GREEN}║                                                          ║${NC}"
echo -e "${GREEN}║  Open your browser to:                                  ║${NC}"
echo -e "${GREEN}║    http://$HOST:$PORT                                   ║${NC}"
echo -e "${GREEN}║                                                          ║${NC}"
echo -e "${GREEN}║  Press Ctrl+C to stop                                   ║${NC}"
echo -e "${GREEN}║                                                          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Launch Streamlit
exec streamlit run "${STREAMLIT_ARGS[@]}"
