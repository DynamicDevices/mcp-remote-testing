#!/bin/bash
# Setup repository metadata using GitHub CLI

set -e

if ! command -v gh &> /dev/null; then
    echo "GitHub CLI (gh) not found. Install from: https://cli.github.com/"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "Not authenticated with GitHub. Run: gh auth login"
    exit 1
fi

REPO="DynamicDevices/lab-testing"

echo "Setting up repository metadata for $REPO..."

# Set repository description
gh repo edit "$REPO" --description "MCP server for remote embedded hardware testing" || true

# Set repository topics
gh repo edit "$REPO" --add-topic "mcp" --add-topic "model-context-protocol" --add-topic "embedded-hardware" --add-topic "lab-testing" --add-topic "python" || true

# Set visibility (if needed)
# gh repo edit "$REPO" --visibility private

# Enable features
gh api repos/"$REPO" -X PATCH -f has_issues=true -f has_projects=false -f has_wiki=false || true

echo "Repository metadata updated."

