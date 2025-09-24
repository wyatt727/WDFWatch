"""
Unit tests for the settings module
"""

import os
from pathlib import Path

import pytest

from wdf.settings import WDFSettings, LLMModels


def test_default_settings():
    """Test that default settings are loaded correctly"""
    settings = WDFSettings()
    
    # Check default values
    assert settings.transcript_dir == Path("transcripts")
    assert settings.artefacts_dir == Path("artefacts")
    assert settings.ollama_host == "http://localhost:11434"
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.prefect_workspace == "wdf-prod"
    assert settings.mock_mode is True
    assert settings.debug is False
    assert settings.random_seed == 42
    
    # Check LLM models
    assert settings.llm_models.gemini == "gemini-2.5-pro"
    assert settings.llm_models.gemma == "gemma3n:e4b"
    assert settings.llm_models.deepseek == "deepseek-r1:latest"


def test_env_override():
    """Test that environment variables override default settings"""
    # Set environment variables
    os.environ["WDF_TRANSCRIPT_DIR"] = "custom_transcripts"
    os.environ["WDF_OLLAMA_HOST"] = "http://custom-ollama:11434"
    os.environ["WDF_MOCK_MODE"] = "false"
    os.environ["WDF_LLM_MODELS__GEMINI"] = "custom-gemini"
    
    # Create settings with environment overrides
    settings = WDFSettings()
    
    # Check overridden values
    assert settings.transcript_dir == Path("custom_transcripts")
    assert settings.ollama_host == "http://custom-ollama:11434"
    assert settings.mock_mode is False
    assert settings.llm_models.gemini == "custom-gemini"
    
    # Check values that weren't overridden
    assert settings.artefacts_dir == Path("artefacts")
    assert settings.llm_models.gemma == "gemma3n:e4b"
    
    # Clean up environment
    del os.environ["WDF_TRANSCRIPT_DIR"]
    del os.environ["WDF_OLLAMA_HOST"]
    del os.environ["WDF_MOCK_MODE"]
    del os.environ["WDF_LLM_MODELS__GEMINI"]


def test_run_dir():
    """Test the get_run_dir method"""
    settings = WDFSettings()
    run_id = "test_run_123"
    
    run_dir = settings.get_run_dir(run_id)
    
    assert run_dir == Path("artefacts") / run_id 