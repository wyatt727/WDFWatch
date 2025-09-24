#!/bin/bash
# Setup environment variables for Claude pipeline execution from web UI
# This ensures Node.js and Claude CLI are in PATH

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Export the required paths for Node.js and Claude CLI
# Adjust these paths based on your Linux server setup

# Add Node.js to PATH (common locations)
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# Add Node.js if installed via nvm
if [ -d "$HOME/.nvm" ]; then
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
fi

# Add Node.js if installed via NodeSource or system package
if [ -d "/usr/bin/node" ]; then
    export PATH="/usr/bin:$PATH"
fi

# Add claude CLI to PATH
if [ -d "$HOME/.claude/local" ]; then
    export PATH="$HOME/.claude/local:$PATH"
fi

# Claude CLI binary location (from the adapter code)
export CLAUDE_CLI_PATH="/home/debian/.claude/local/claude"

# Print environment for debugging
echo "Environment setup for Claude pipeline:"
echo "PATH: $PATH"
echo "NODE: $(which node 2>/dev/null || echo 'not found')"
echo "CLAUDE: $(which claude 2>/dev/null || echo 'not found')"
echo "CLAUDE_CLI_PATH: $CLAUDE_CLI_PATH"

# Export all variables
export PATH