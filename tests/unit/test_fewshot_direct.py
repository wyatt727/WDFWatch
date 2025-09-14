"""
Direct tests for the fewshot module's parse_examples function

This test file contains a copy of the parse_examples function to test it in isolation,
avoiding any database initialization issues.
"""

import pytest
import logging
import structlog

# Constants from the original module
REQUIRED_EXAMPLES = 40
MIN_RELEVANT_PERCENT = 20

# Set up a test logger
logger = structlog.get_logger()


def parse_examples(response):
    """
    Parse the model response into a list of (tweet, label) tuples
    
    Args:
        response: Model response text
        
    Returns:
        List of (tweet, label) tuples
    """
    # Clean up the response
    # Remove any introductory text before the first tweet
    if "<end_of_turn>" in response:
        response = response.split("<end_of_turn>")[-1].strip()
    
    # Remove any model preamble text that might explain what it's doing
    lines_original = [l.strip() for l in response.splitlines() if l.strip()]
    lines = []
    started_examples = False
    
    for line in lines_original:
        # Skip any lines that look like explanations or instructions
        if not started_examples and not (("\t" in line) or ("RELEVANT" in line) or ("SKIP" in line)):
            continue
        
        # Once we find a line with a tab or classification, we've started the examples
        if ("\t" in line) or ("RELEVANT" in line) or ("SKIP" in line):
            started_examples = True
            lines.append(line)
        elif started_examples and line:  # Only include non-empty lines after we've started examples
            lines.append(line)
    
    # If we still have too many lines, just take the first REQUIRED_EXAMPLES
    if len(lines) > REQUIRED_EXAMPLES:
        logger.warning(f"Too many lines in response, truncating to {REQUIRED_EXAMPLES}")
        lines = lines[:REQUIRED_EXAMPLES]
    
    # If we don't have enough lines, raise an error
    if len(lines) < REQUIRED_EXAMPLES:
        raise ValueError(f"Expected {REQUIRED_EXAMPLES} lines, got {len(lines)}")
    
    pairs = []
    for l in lines:
        # Try to split by tab first
        if "\t" in l:
            tweet, label = l.split("\t", 1)
        # If no tab, try to find RELEVANT or SKIP at the end
        elif "RELEVANT" in l:
            tweet = l.replace("RELEVANT", "").strip()
            label = "RELEVANT"
        elif "SKIP" in l:
            tweet = l.replace("SKIP", "").strip()
            label = "SKIP"
        else:
            raise ValueError(f"Cannot parse line, missing TAB and label: {l}")
            
        label = label.strip()
        
        if label not in ("RELEVANT", "SKIP"):
            raise ValueError(f"Bad label '{label}' in line: {l}")
            
        pairs.append([tweet.strip(), label])
    
    # Validate that at least MIN_RELEVANT_PERCENT% are RELEVANT
    relevant_count = sum(1 for _, label in pairs if label == "RELEVANT")
    relevant_percent = (relevant_count / len(pairs)) * 100
    
    if relevant_percent < MIN_RELEVANT_PERCENT:
        logger.warning(
            "Few-shot examples have low percentage of RELEVANT labels",
            relevant_percent=relevant_percent,
            min_expected=MIN_RELEVANT_PERCENT
        )
    
    return pairs


def test_parse_examples_valid():
    """Test parsing valid examples"""
    # Generate 40 examples (20 RELEVANT, 20 SKIP)
    response = ""
    for i in range(20):
        response += f"This is a RELEVANT tweet {i}\tRELEVANT\n"
    for i in range(20):
        response += f"This is a SKIP tweet {i}\tSKIP\n"
    
    examples = parse_examples(response)
    
    assert len(examples) == 40
    assert examples[0][1] == "RELEVANT"
    assert examples[20][1] == "SKIP"
    assert sum(1 for _, label in examples if label == "RELEVANT") == 20
    assert sum(1 for _, label in examples if label == "SKIP") == 20


def test_parse_examples_wrong_count():
    """Test parsing examples with wrong count"""
    # Only 39 examples instead of 40
    response = ""
    for i in range(20):
        response += f"This is a RELEVANT tweet {i}\tRELEVANT\n"
    for i in range(19):  # One less than needed
        response += f"This is a SKIP tweet {i}\tSKIP\n"
    
    with pytest.raises(ValueError, match=f"Expected {REQUIRED_EXAMPLES} lines"):
        parse_examples(response)


def test_parse_examples_no_labels():
    """Test parsing examples with no recognizable labels"""
    # Generate 40 examples but without labels
    response = ""
    for i in range(40):
        response += f"This is tweet number {i}\n"
    
    with pytest.raises(ValueError, match=f"Expected {REQUIRED_EXAMPLES} lines, got 0"):
        parse_examples(response)


def test_parse_examples_invalid_label():
    """Test parsing examples with invalid label"""
    # Generate 40 examples with one invalid label
    response = ""
    for i in range(20):
        if i == 10:
            response += f"This has an invalid label\tMAYBE\n"  # Invalid label
        else:
            response += f"This is a RELEVANT tweet {i}\tRELEVANT\n"
    for i in range(20):
        response += f"This is a SKIP tweet {i}\tSKIP\n"
    
    with pytest.raises(ValueError, match="Bad label"):
        parse_examples(response)


def test_parse_examples_low_relevant_percentage():
    """Test parsing examples with low percentage of RELEVANT labels"""
    # Only 4 RELEVANT examples (10%, below the 20% threshold)
    response = ""
    for i in range(4):
        response += f"This is a RELEVANT tweet {i}\tRELEVANT\n"
    for i in range(36):
        response += f"This is a SKIP tweet {i}\tSKIP\n"
    
    # This should not raise an exception, but log a warning
    examples = parse_examples(response)
    
    assert len(examples) == 40
    assert sum(1 for _, label in examples if label == "RELEVANT") == 4
    assert sum(1 for _, label in examples if label == "SKIP") == 36 