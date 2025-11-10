#!/bin/bash
# Installation script for Python Runtime Provenance Tracking

set -e

echo "Installing Python Runtime Provenance Tracking..."
echo ""

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Install the package
echo "Installing package..."
pip install -e .

echo ""
echo "✅ Installation complete!"
echo ""
echo "To enable tracking, set:"
echo "  export PYTHON_TRACKING_ENABLED=1"
echo ""
echo "To disable tracking, set:"
echo "  export PYTHON_TRACKING_ENABLED=0"
echo ""
echo "Or add to your ~/.bashrc or ~/.zshrc:"
echo "  export PYTHON_TRACKING_ENABLED=1"
echo ""
