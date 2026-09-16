#!/bin/bash
# Installation script for Chord Analysis dependencies

set -e

echo "🎵 Chord Analysis - Dependency Installation"
echo "============================================="
echo ""

# Check if we're in a virtual environment
if [[ -z "${VIRTUAL_ENV}" ]]; then
    echo "⚠️  Not in a virtual environment. Creating one..."
    echo ""

    # Create virtual environment
    python3 -m venv venv

    echo "✓ Virtual environment created"
    echo ""
    echo "To activate the virtual environment, run:"
    echo "  source venv/bin/activate"
    echo ""
    echo "Then re-run this script."
    exit 0
fi

echo "✓ Virtual environment detected: ${VIRTUAL_ENV}"
echo ""

# Install system dependencies (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Installing system dependencies via Homebrew..."
    if command -v brew &> /dev/null; then
        brew install libsndfile
        echo "✓ libsndfile installed"
    else
        echo "⚠️  Homebrew not found. Please install libsndfile manually:"
        echo "   brew install libsndfile"
    fi
fi

echo ""
echo "Installing Python packages..."
echo ""

# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

echo ""
echo "============================================="
echo "✓ Installation complete!"
echo ""
echo "To run the web UI:"
echo "  streamlit run run_web.py"
echo ""
