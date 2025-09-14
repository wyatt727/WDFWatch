#!/usr/bin/env python3
"""
Test the simplified response generation
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from stages.respond import ResponseGenerator
from core import UnifiedInterface

def test_simplified_response():
    """Test that response generation works with simplified prompts."""
    
    # Initialize Claude interface
    claude = UnifiedInterface()
    
    # Initialize response generator
    responder = ResponseGenerator(claude)
    
    # Test single tweet response
    test_tweet = "The federal government keeps expanding its power beyond constitutional limits"
    
    # Use a known episode ID (or create a test one)
    episode_id = "test_simplified"
    
    try:
        response = responder.generate_single_response(test_tweet, episode_id)
        print(f"Test Tweet: {test_tweet}")
        print(f"Generated Response: {response}")
        print(f"Response Length: {len(response)} characters")
        
        # Verify response meets requirements
        assert len(response) <= 200, f"Response too long: {len(response)} > 200"
        assert "WDF" in response, "Response doesn't mention WDF"
        print("\n✅ All checks passed!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Testing simplified response generation...")
    print("=" * 50)
    test_simplified_response()