#!/usr/bin/env python3
"""
Model Interface - Abstract base class for all LLM model implementations

This module defines the common interface that all model adapters must implement,
enabling seamless switching between different LLM providers while maintaining
consistent behavior across the pipeline.

Supports:
- Claude (via CLI)
- Gemini (via CLI)
- Ollama (via HTTP API)
- OpenAI (via API)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ModelResponse:
    """Standardized response from model generation"""
    content: str
    tokens_used: int
    cost_estimate: float
    model_name: str
    latency_ms: int
    metadata: Dict[str, Any] = None


@dataclass
class ModelConfig:
    """Configuration for model instances"""
    model_name: str
    provider: str  # 'claude', 'gemini', 'ollama', 'openai'
    temperature: float = 0.3
    max_tokens: int = 4096
    context_limit: int = 200000
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    timeout_seconds: int = 300  # 5 minutes for long transcripts
    retry_attempts: int = 3
    custom_params: Dict[str, Any] = None


class ModelInterface(ABC):
    """
    Abstract base class for all model implementations.
    
    This interface ensures consistent behavior across different LLM providers
    while allowing for provider-specific optimizations and features.
    """
    
    def __init__(self, config: ModelConfig):
        """
        Initialize the model interface.
        
        Args:
            config: Model configuration containing provider-specific settings
        """
        self.config = config
        self.provider = config.provider
        self.model_name = config.model_name
        
    @abstractmethod
    async def generate(self, 
                      prompt: str,
                      context: Optional[str] = None,
                      mode: str = "default") -> ModelResponse:
        """
        Generate text using the model.
        
        Args:
            prompt: The main prompt to send to the model
            context: Optional context (episode-specific or task-specific)
            mode: Operation mode (summarize, classify, respond, moderate)
            
        Returns:
            ModelResponse with generated content and metadata
        """
        pass
    
    @abstractmethod
    async def batch_generate(self,
                            prompts: List[str],
                            context: Optional[str] = None,
                            mode: str = "default") -> List[ModelResponse]:
        """
        Generate responses for multiple prompts efficiently.
        
        Args:
            prompts: List of prompts to process
            context: Optional context for all prompts
            mode: Operation mode
            
        Returns:
            List of ModelResponse objects
        """
        pass
    
    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate the cost for a given token usage.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Estimated cost in USD
        """
        pass
    
    @abstractmethod
    def get_context_limit(self) -> int:
        """
        Get the maximum context size for this model.
        
        Returns:
            Context limit in tokens/characters
        """
        pass
    
    @abstractmethod
    def validate_availability(self) -> bool:
        """
        Check if the model is available and properly configured.
        
        Returns:
            True if model is available, False otherwise
        """
        pass
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about this model instance.
        
        Returns:
            Dictionary with model metadata
        """
        return {
            'provider': self.provider,
            'model_name': self.model_name,
            'context_limit': self.get_context_limit(),
            'config': {
                'temperature': self.config.temperature,
                'max_tokens': self.config.max_tokens,
                'timeout': self.config.timeout_seconds
            }
        }
    
    def supports_mode(self, mode: str) -> bool:
        """
        Check if this model supports a specific operation mode.
        
        Args:
            mode: Operation mode to check
            
        Returns:
            True if mode is supported
        """
        # Default implementation - most models support all modes
        supported_modes = {'summarize', 'classify', 'respond', 'moderate', 'default'}
        return mode in supported_modes
    
    def prepare_prompt_for_mode(self, prompt: str, mode: str) -> str:
        """
        Prepare a prompt for a specific operation mode.
        
        This can be overridden by specific adapters to add mode-specific
        instructions or formatting.
        
        Args:
            prompt: Base prompt
            mode: Operation mode
            
        Returns:
            Mode-prepared prompt
        """
        mode_prefixes = {
            'summarize': "MODE: SUMMARIZE\n\n",
            'classify': "MODE: CLASSIFY\n\n", 
            'respond': "MODE: RESPOND\n\n",
            'moderate': "MODE: MODERATE\n\n"
        }
        
        prefix = mode_prefixes.get(mode, "")
        return f"{prefix}{prompt}"


class ModelException(Exception):
    """Base exception for model-related errors"""
    pass


class ModelUnavailableException(ModelException):
    """Raised when a model is not available or misconfigured"""
    pass


class ModelTimeoutException(ModelException):
    """Raised when a model request times out"""
    pass


class ModelQuotaException(ModelException):
    """Raised when model quota/rate limits are exceeded"""
    pass


class ModelValidationException(ModelException):
    """Raised when model response cannot be parsed or validated"""
    pass