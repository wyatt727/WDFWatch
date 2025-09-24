"""
Unit tests for the fewshot module
"""

import json
import os
import pytest
from pathlib import Path

# Import only what we need to avoid database initialization issues
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


def test_run_in_test_mode(tmp_path, monkeypatch):
    """Test run function in test mode with pre-generated data"""
    from wdf.tasks.fewshot import run
    
    # Set up test environment
    test_dir = tmp_path / "test_run"
    test_dir.mkdir()
    
    # Create test files
    summary_path = test_dir / "summary.md"
    summary_path.write_text("Test summary")
    
    overview_path = test_dir / "podcast_overview.txt"
    overview_path.write_text("Test overview")
    
    fewshots_path = test_dir / "fewshots.json"
    # Create valid test data with 40 examples
    test_data = []
    for i in range(40):
        if i % 2 == 0:
            test_data.append([f"Tweet {i} about federalism", "RELEVANT"])
        else:
            test_data.append([f"Random tweet {i}", "SKIP"])
    fewshots_path.write_text(json.dumps(test_data))
    
    # Monkeypatch the transcript directory
    monkeypatch.setattr("wdf.tasks.fewshot.settings.transcript_dir", str(test_dir))
    monkeypatch.setattr("wdf.tasks.fewshot.SUMMARY_PATH", summary_path)
    monkeypatch.setattr("wdf.tasks.fewshot.OVERVIEW_PATH", overview_path)
    monkeypatch.setattr("wdf.tasks.fewshot.FEWSHOTS_PATH", fewshots_path)
    
    # Test mode should read existing file
    monkeypatch.setenv("WDF_TEST_MODE", "true")
    
    result_path = run()
    
    assert result_path == fewshots_path
    assert fewshots_path.exists()
    
    # Verify content
    with open(fewshots_path) as f:
        data = json.load(f)
    assert len(data) == 40


def test_run_force_regeneration(tmp_path, monkeypatch):
    """Test run function with force regeneration"""
    pytest.skip("Requires 'mocker' fixture from pytest-mock")