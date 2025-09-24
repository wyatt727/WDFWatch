#!/usr/bin/env python3
"""Quick script to post I'M ALIVE!!!! without shell escaping issues."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.safe_twitter_post import post_safe_tweet

# Post the message directly without shell interpretation
result = post_safe_tweet("I'M ALIVE!!!!")
sys.exit(0 if result else 1)