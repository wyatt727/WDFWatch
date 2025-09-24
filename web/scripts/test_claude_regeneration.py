#!/usr/bin/env python3
"""
Test script for Claude CLI regeneration command
Tests the exact command used in the regeneration API endpoint
"""

import subprocess
import os
import sys
import tempfile
import time
from pathlib import Path

def test_claude_cli():
    """Test the Claude CLI command with various approaches"""
    
    # Setup paths
    claude_path = "/Users/pentester/.claude/local/claude"
    specialized_dir = Path(__file__).parent.parent.parent / "claude-pipeline" / "specialized"
    episode_dir = specialized_dir.parent / "episodes" / "episode_12_mike_maharrey_tenth_amendment_center"
    summary_path = episode_dir / "summary.md"
    
    print("Testing Claude CLI Regeneration")
    print("=" * 50)
    print(f"Claude path: {claude_path}")
    print(f"Specialized dir: {specialized_dir}")
    print(f"Episode dir: {episode_dir}")
    print(f"Summary path: {summary_path}")
    print()
    
    # Check if files exist
    if not os.path.exists(claude_path):
        print(f"❌ Claude CLI not found at {claude_path}")
        return
    else:
        print(f"✅ Claude CLI exists")
    
    if not specialized_dir.exists():
        print(f"❌ Specialized dir not found at {specialized_dir}")
        return
    else:
        print(f"✅ Specialized dir exists")
    
    if not summary_path.exists():
        print(f"❌ Summary file not found at {summary_path}")
    else:
        print(f"✅ Summary file exists ({summary_path.stat().st_size} bytes)")
    
    no_mcp_path = specialized_dir.parent / "no-mcp.json"
    if not no_mcp_path.exists():
        print(f"❌ no-mcp.json not found at {no_mcp_path}")
    else:
        print(f"✅ no-mcp.json exists")
    
    claude_md_path = specialized_dir / "responder" / "CLAUDE.md"
    if not claude_md_path.exists():
        print(f"❌ CLAUDE.md not found at {claude_md_path}")
    else:
        print(f"✅ CLAUDE.md exists ({claude_md_path.stat().st_size} bytes)")
    
    print("\n" + "=" * 50)
    
    # Test tweet
    test_tweet = "The federal government's overreach is getting out of control. States need to push back!"
    
    # Test 1: Simple command without MCP
    print("\nTest 1: Simple command without MCP config")
    print("-" * 40)
    cmd = [claude_path, "--model", "sonnet", "--print", "Just say: Hello from Claude"]
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(specialized_dir),
            capture_output=True,
            text=True,
            timeout=30
        )
        print(f"Return code: {result.returncode}")
        if result.returncode == 0:
            print(f"✅ Success! Output: {result.stdout.strip()}")
        else:
            print(f"❌ Failed!")
            print(f"Stdout: {result.stdout[:200]}")
            print(f"Stderr: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        print("❌ Command timed out!")
    except Exception as e:
        print(f"❌ Exception: {e}")
    
    # Test 2: Command with file input
    print("\n\nTest 2: Command with file input and MCP config")
    print("-" * 40)
    
    # Prepare prompt
    if summary_path.exists():
        summary_ref = f"Refer to @../episodes/episode_12_mike_maharrey_tenth_amendment_center/summary.md for episode specific details."
    else:
        summary_ref = "Use your general WDF podcast knowledge to create a relevant response."
    
    prompt = f'Create a response to the provided tweet and DO NOT include any other text. {summary_ref} The response must be relevant and original. Here is the tweet you must generate a response to: "{test_tweet}"'
    
    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, dir=str(specialized_dir)) as f:
        f.write(prompt)
        temp_file = f.name
    
    print(f"Temp file: {temp_file}")
    print(f"Prompt ({len(prompt)} chars): {prompt[:200]}...")
    
    cmd = [
        claude_path,
        "--model", "sonnet",
        "--strict-mcp-config",
        "--mcp-config", "../no-mcp.json",
        "--print",
        "--dangerously-skip-permissions",
        "--file", temp_file
    ]
    
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(specialized_dir),
            capture_output=True,
            text=True,
            timeout=45,
            env={**os.environ, "DEBUG": "1"}
        )
        print(f"Return code: {result.returncode}")
        if result.returncode == 0:
            print(f"✅ Success!")
            print(f"Output ({len(result.stdout)} chars): {result.stdout.strip()[:280]}")
        else:
            print(f"❌ Failed with code {result.returncode}")
            print(f"Stdout: {result.stdout[:500]}")
            print(f"Stderr: {result.stderr[:500]}")
    except subprocess.TimeoutExpired:
        print("❌ Command timed out after 45 seconds!")
    except Exception as e:
        print(f"❌ Exception: {e}")
    finally:
        # Clean up temp file
        try:
            os.unlink(temp_file)
            print("Cleaned up temp file")
        except:
            pass
    
    # Test 3: Try with stdin instead of file
    print("\n\nTest 3: Command with stdin input")
    print("-" * 40)
    
    cmd = [
        claude_path,
        "--model", "sonnet",
        "--strict-mcp-config",
        "--mcp-config", "../no-mcp.json",
        "--print",
        "--dangerously-skip-permissions"
    ]
    
    print(f"Command: {' '.join(cmd)}")
    print(f"Stdin: {prompt[:200]}...")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(specialized_dir),
            input=prompt,
            capture_output=True,
            text=True,
            timeout=45,
            env={**os.environ, "DEBUG": "1"}
        )
        print(f"Return code: {result.returncode}")
        if result.returncode == 0:
            print(f"✅ Success!")
            print(f"Output ({len(result.stdout)} chars): {result.stdout.strip()[:280]}")
        else:
            print(f"❌ Failed with code {result.returncode}")
            print(f"Stdout: {result.stdout[:500]}")
            print(f"Stderr: {result.stderr[:500]}")
    except subprocess.TimeoutExpired:
        print("❌ Command timed out after 45 seconds!")
    except Exception as e:
        print(f"❌ Exception: {e}")
    
    print("\n" + "=" * 50)
    print("Testing complete!")

if __name__ == "__main__":
    test_claude_cli()