#!/bin/bash
# Initialize repository and set up GitHub metadata

set -e

REPO="DynamicDevices/mcp-remote-testing"

echo "Initializing repository..."

# Check if gh is available
if ! command -v gh &> /dev/null; then
    echo "GitHub CLI (gh) not found. Skipping metadata setup."
    echo "Install from: https://cli.github.com/"
    echo ""
    echo "To set up metadata manually, run after installing gh:"
    echo "  bash scripts/setup-repo.sh"
    exit 0
fi

# Check authentication
if ! gh auth status &> /dev/null; then
    echo "Not authenticated with GitHub."
    echo "Run: gh auth login"
    exit 1
fi

# Check if repo exists
if ! gh repo view "$REPO" &> /dev/null; then
    echo "Repository $REPO not found. Creating..."
    gh repo create "$REPO" --private --source=. --remote=origin --push || {
        echo "Failed to create repository. It may already exist."
    }
else
    echo "Repository $REPO exists."
fi

# Set up metadata
echo "Setting repository metadata..."
bash scripts/setup-repo.sh

echo ""
echo "Repository initialized!"
echo "Next steps:"
echo "  1. git add -A"
echo "  2. git commit -m 'Initial commit'"
echo "  3. git push -u origin main"

