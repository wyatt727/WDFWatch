#!/usr/bin/env python3
"""
Claude CLI Configuration

This module provides the correct path to the Claude CLI executable,
handling both aliases and direct paths.
"""

import os
import subprocess
from pathlib import Path

def get_claude_command():
    """
    Get the correct command to run Claude CLI with optimized settings.
    
    Returns:
        list: Command array for subprocess (just the executable path)
    """
    # First check if 'claude' command is available in PATH
    # This handles aliases and ensures we use the user's preferred setup
    try:
        result = subprocess.run(
            ["which", "claude"],
            capture_output=True,
            text=True,
            timeout=1
        )
        if result.returncode == 0:
            # Use the claude command directly (works with aliases)
            return ["claude"]
    except:
        pass
    
    # Fallback: try the known direct path
    claude_path = Path("/Users/pentester/.claude/local/claude")
    if claude_path.exists():
        return [str(claude_path)]
    
    # Last resort: assume 'claude' is in PATH
    return ["claude"]

def get_claude_flags():
    """
    Get the optimized flags for Claude CLI.
    
    Returns:
        list: Flags for non-interactive use without MCP server
    """
    # Always use absolute path to the project's no-mcp.json file
    # This ensures the file is found regardless of working directory
    project_root = Path(__file__).parent.parent.parent
    no_mcp_config = project_root / "no-mcp.json"
    
    # Ensure the file exists, create if missing
    if not no_mcp_config.exists():
        no_mcp_config.write_text('{\n    "mcpServers": {}\n}')
    
    no_mcp_path = str(no_mcp_config)
    
    return [
        "--mcp-config", no_mcp_path,  # Use empty MCP config
        "--print",  # Print response and exit (non-interactive)
        "--strict-mcp-config",  # Don't load other MCP servers
        "--model", "sonnet"  # Use Sonnet model for cost efficiency
    ]

# Export functions for dynamic command building
# Don't cache these as they may depend on current working directory
def get_cached_command():
    """Get command using the known Claude executable path"""
    # Use the full path to the Claude executable
    # We know this path works from user's environment
    return ["/Users/pentester/.claude/local/claude"]

# Export the command and flags for use in other modules
CLAUDE_COMMAND = get_cached_command()
CLAUDE_FLAGS = get_claude_flags()

def build_claude_command(prompt):
    """
    Build the complete Claude command with correct argument order.
    
    Args:
        prompt: The prompt text
        
    Returns:
        list: Complete command array [claude, prompt, --flags...]
    """
    # Always use fresh flags to get correct relative/absolute path
    return get_cached_command() + [prompt] + get_claude_flags()

def test_claude():
    """Test if Claude CLI is working"""
    try:
        # Test with correct argument order: command, prompt, then flags
        cmd = build_claude_command("Reply with exactly the text: OK")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10  # Should complete in ~7 seconds with no-mcp config
        )
        if result.returncode == 0:
            if "OK" in result.stdout:
                return True
            elif len(result.stdout.strip()) > 0:
                # Claude responded with something - likely still working
                return True
            else:
                print(f"Claude returned success but no output")
                return False
        else:
            print(f"Claude failed with return code {result.returncode}")
            if result.stderr:
                print(f"Error: {result.stderr[:200]}")
            return False
    except subprocess.TimeoutExpired:
        print(f"Claude test timed out after 10 seconds")
        print(f"Check that no-mcp.json exists and Claude CLI is properly configured")
        return False
    except Exception as e:
        print(f"Claude test failed: {e}")
        return False

if __name__ == "__main__":
    print(f"Claude command: {CLAUDE_COMMAND}")
    print(f"Claude flags: {CLAUDE_FLAGS}")
    print(f"Full test command: {build_claude_command('test prompt')}")
    if test_claude():
        print("✓ Claude CLI is working")
    else:
        print("✗ Claude CLI is not working")