"""
Direct unit tests for the fewshot parser functionality
Tests the parse_examples function in isolation
"""

import pytest
from wdf.tasks.fewshot import parse_examples, REQUIRED_EXAMPLES


def test_parse_examples_valid():
    """Test parsing valid examples - should have exactly 40 lines"""
    response = "\n".join([
        f"Tweet {i} about federalism\tRELEVANT" if i % 2 == 0 
        else f"Random tweet {i}\tSKIP" 
        for i in range(40)
    ])
    
    examples = parse_examples(response)
    
    assert len(examples) == 40
    assert examples[0] == ["Tweet 0 about federalism", "RELEVANT"]
    assert examples[1] == ["Random tweet 1", "SKIP"]
    assert sum(1 for _, label in examples if label == "RELEVANT") == 20
    assert sum(1 for _, label in examples if label == "SKIP") == 20


def test_parse_examples_wrong_count():
    """Test parsing examples with wrong count - only 39 examples"""
    response = "\n".join([
        f"Tweet {i} about federalism\tRELEVANT" if i % 2 == 0 
        else f"Random tweet {i}\tSKIP" 
        for i in range(39)  # Only 39 instead of 40
    ])
    
    with pytest.raises(ValueError, match="Expected 40 lines"):
        parse_examples(response)


def test_parse_examples_missing_tab():
    """Test parsing examples with missing tab separator"""
    lines = []
    for i in range(40):
        if i == 5:  # Make the 6th line missing a tab
            lines.append("War and peace discussion RELEVANT")
        elif i % 2 == 0:
            lines.append(f"Tweet {i} about federalism\tRELEVANT")
        else:
            lines.append(f"Random tweet {i}\tSKIP")
    
    response = "\n".join(lines)
    
    # This should now work since the parser can handle missing tabs
    examples = parse_examples(response)
    assert len(examples) == 40


def test_parse_examples_invalid_label():
    """Test parsing examples with invalid label"""
    lines = []
    for i in range(40):
        if i == 5:  # Make the 6th line have an invalid label
            lines.append(f"Tweet {i}\tMAYBE")
        elif i % 2 == 0:
            lines.append(f"Tweet {i} about federalism\tRELEVANT")
        else:
            lines.append(f"Random tweet {i}\tSKIP")
    
    response = "\n".join(lines)
    
    with pytest.raises(ValueError, match="Bad label"):
        parse_examples(response)


def test_parse_examples_low_relevant_percentage():
    """Test parsing examples with low percentage of RELEVANT labels"""
    # Only 7 RELEVANT examples (17.5% - below 20% threshold)
    lines = []
    for i in range(40):
        if i < 7:  # First 7 are RELEVANT
            lines.append(f"Tweet {i} about federalism\tRELEVANT")
        else:  # Rest are SKIP
            lines.append(f"Random tweet {i}\tSKIP")
    
    response = "\n".join(lines)
    
    # Should fail because less than 20% (8) are RELEVANT
    with pytest.raises(ValueError, match="Not enough RELEVANT examples"):
        examples = parse_examples(response)
        # Trigger the percentage check
        relevant_count = sum(1 for _, label in examples if label == "RELEVANT")
        if relevant_count < REQUIRED_EXAMPLES * 0.2:
            raise ValueError(f"Not enough RELEVANT examples: {relevant_count}/{REQUIRED_EXAMPLES}")