"""
Snapshot tests for LLM prompts

These tests ensure that the prompts used for LLM interactions remain consistent
and that any changes to them are intentional.
"""

import pytest
from wdf.tasks.fewshot import build_prompt as build_fewshot_prompt
from wdf.tasks.deepseek import build_prompt as build_deepseek_prompt


def test_fewshot_prompt_snapshot(snapshot):
    """Test that the few-shot prompt remains consistent"""
    overview = "WDF is a podcast about War, Divorce, and Federalism hosted by Rick Becker."
    summary = "In this episode, Rick discusses constitutional rights and liberty."
    
    prompt = build_fewshot_prompt(overview, summary)
    
    # Compare with snapshot
    snapshot.assert_match(prompt, "fewshot_prompt.txt")


def test_deepseek_prompt_snapshot(snapshot):
    """Test that the DeepSeek prompt remains consistent"""
    tweet = "I think liberty is important. What do you all think?"
    summary = "In this episode, Rick discusses constitutional rights and liberty."
    video_url = "https://example.com/wdf-podcast-episode"
    
    prompt = build_deepseek_prompt(tweet, summary, video_url)
    
    # Compare with snapshot
    snapshot.assert_match(prompt, "deepseek_prompt.txt") 