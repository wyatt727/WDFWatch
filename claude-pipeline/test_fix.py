#!/usr/bin/env python3
"""
Quick test to verify the Claude CLI fix
"""

import sys
import os
from pathlib import Path

# Add the pipeline directory to Python path
pipeline_dir = Path(__file__).parent
sys.path.insert(0, str(pipeline_dir))

from core.unified_interface import UnifiedInterface

def test_claude_fix():
    """Test that Claude CLI calls work now."""
    print("Testing Claude CLI fix...")
    
    # Create a simple test prompt
    test_transcript = "This is a test transcript about federalism and states' rights. Rick Becker interviews a guest about constitutional issues."
    
    # Initialize unified interface
    claude = UnifiedInterface()
    
    # Test a simple summarization call
    try:
        response = claude.call(
            prompt=f"Summarize this brief transcript: {test_transcript}",
            mode="summarize",
            use_cache=False
        )
        
        print(f"Response length: {len(response)}")
        print(f"Response preview: {response[:200]}...")
        
        if "Execution error" in response:
            print("❌ Still getting 'Execution error'")
            return False
        elif "[ERROR:" in response:
            print("❌ Getting new error format")
            print(f"Error: {response}")
            return False
        else:
            print("✅ Got valid response!")
            return True
            
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        return False

if __name__ == "__main__":
    success = test_claude_fix()
    sys.exit(0 if success else 1)