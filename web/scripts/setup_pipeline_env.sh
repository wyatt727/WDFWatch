#!/bin/bash
# Setup script for testing Claude pipeline environment
# This sets up the proper PATH for Node.js and Claude CLI

echo "Setting up environment for Claude pipeline..."

# Add Node.js and Claude CLI to PATH
export PATH="/usr/bin:/usr/local/bin:/bin:/usr/sbin:/sbin:$HOME/.claude/local:/home/debian/.claude/local:$PATH"

# Set other critical environment variables
export CLAUDE_CLI_PATH="/home/debian/.claude/local/claude"
export NODE_PATH="/usr/lib/node_modules"
export PYTHONUNBUFFERED="1"

# Verify Node.js is available
echo "Checking Node.js..."
which node
node --version

# Verify Claude CLI is available
echo "Checking Claude CLI..."
which claude
claude --version

echo "Environment setup complete!"
echo "PATH: $PATH"
echo ""
echo "You can now test the pipeline with:"
echo "python3 web/scripts/claude_pipeline_fixed.py --episode-id test_123 --stages summarize --transcript transcripts/latest.txt -d"