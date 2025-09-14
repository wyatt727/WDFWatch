"""
Model Adapters Package

This package contains adapters for different LLM providers, all implementing
the common ModelInterface to ensure consistent behavior across the pipeline.

Available adapters:
- ClaudeAdapter: Claude models via CLI
- GeminiAdapter: Gemini models via CLI
- OllamaAdapter: Ollama models via HTTP API
- OpenAIAdapter: OpenAI models via API
"""

from .claude_adapter import ClaudeAdapter
from .ollama_adapter import OllamaAdapter

__all__ = ['ClaudeAdapter', 'OllamaAdapter']