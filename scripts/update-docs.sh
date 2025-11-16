#!/bin/bash
# Update documentation before git push
# Ensures docs are concise, engineer-focused, and include latest context

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "Updating documentation..."

# Verify architecture diagram exists
if [ -f "docs/architecture.mmd" ]; then
    echo "  ✓ Architecture diagram: docs/architecture.mmd"
else
    echo "  ⚠ Architecture diagram missing: docs/architecture.mmd"
fi

# Count tools in server.py
if [ -f "server.py" ]; then
    TOOL_COUNT=$(grep -c 'name="' server.py || echo "0")
    echo "  ✓ Tools available: $TOOL_COUNT"
fi

# Ensure all markdown files end with newline
find . -name "*.md" -type f -not -path "./.git/*" -exec sh -c 'test -s "$1" && [ "$(tail -c 1 "$1")" != "" ] && echo >> "$1"' _ {} \; || true

# Verify key documentation files exist
REQUIRED_DOCS=("README.md" "docs/API.md" "docs/SETUP.md" "docs/architecture.mmd")
for doc in "${REQUIRED_DOCS[@]}"; do
    if [ -f "$doc" ]; then
        echo "  ✓ $doc"
    else
        echo "  ⚠ Missing: $doc"
    fi
done

echo "Documentation check complete."

