#!/usr/bin/env python3
"""
Ollama Adapter - Interface for Ollama models via HTTP API

This adapter implements the ModelInterface for Ollama models, providing
seamless integration with locally hosted Ollama instances while supporting
the new flexible model configuration system.

Features:
- HTTP API integration with Ollama
- Batch processing optimization
- Context size handling per model
- Cost estimation (compute-based for local models)
- Automatic retry logic with backoff
"""

import asyncio
import aiohttp
import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Optional, Any

from ..model_interface import (
    ModelInterface, ModelResponse, ModelConfig, 
    ModelException, ModelTimeoutException, ModelUnavailableException
)

logger = logging.getLogger(__name__)


class OllamaAdapter(ModelInterface):
    """
    Adapter for Ollama models using HTTP API.
    
    This adapter communicates with a local Ollama instance to provide
    access to various open-source models like Llama, Gemma, DeepSeek, etc.
    """
    
    # Model context limits (approximate)
    CONTEXT_LIMITS = {
        'llama3.3:70b': 128000,
        'llama3.1:8b': 128000,
        'llama3.1:70b': 128000,
        'gemma2:9b': 8192,
        'gemma2:27b': 8192,
        'gemma3n:e4b': 8192,  # WDF-specific model
        'deepseek-r1:latest': 64000,
        'deepseek-coder:6.7b': 16384,
        'qwen2.5:32b': 32768,
        'mixtral:8x7b': 32768,
        'phi3:14b': 16384,
        # Default fallback
        'default': 8192
    }
    
    # Compute cost estimation (approximate relative costs)
    COMPUTE_COSTS = {
        'llama3.3:70b': 0.001,  # Higher cost for larger models
        'llama3.1:70b': 0.001,
        'llama3.1:8b': 0.0002,
        'gemma2:27b': 0.0005,
        'gemma2:9b': 0.0002,
        'gemma3n:e4b': 0.0002,
        'deepseek-r1:latest': 0.0003,
        'deepseek-coder:6.7b': 0.0002,
        'qwen2.5:32b': 0.0006,
        'mixtral:8x7b': 0.0004,
        'phi3:14b': 0.0003,
        # Default fallback
        'default': 0.0002
    }
    
    def __init__(self, config: ModelConfig):
        """
        Initialize Ollama adapter.
        
        Args:
            config: Model configuration
        """
        super().__init__(config)
        self.api_endpoint = config.api_endpoint or "http://localhost:11434"
        self.session = None  # Will be created when needed
        
        logger.info(f"Ollama adapter initialized: {self.model_name} @ {self.api_endpoint}")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def generate(self, 
                      prompt: str,
                      context: Optional[str] = None,
                      mode: str = "default") -> ModelResponse:
        """
        Generate text using Ollama model.
        
        Args:
            prompt: The prompt to send to the model
            context: Optional context content
            mode: Operation mode
            
        Returns:
            ModelResponse with generated content
        """
        start_time = time.time()
        
        try:
            # Prepare the full prompt with context and mode
            full_prompt = self._prepare_full_prompt(prompt, context, mode)
            
            # Call Ollama API
            response_data = await self._call_ollama_api(full_prompt)
            
            # Extract response text
            response_text = response_data.get('response', '').strip()
            
            # Calculate metrics
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Get token counts from Ollama response or estimate
            input_tokens = response_data.get('prompt_eval_count', len(full_prompt) // 4)
            output_tokens = response_data.get('eval_count', len(response_text) // 4)
            total_tokens = input_tokens + output_tokens
            
            cost = self.estimate_cost(input_tokens, output_tokens)
            
            return ModelResponse(
                content=response_text,
                tokens_used=total_tokens,
                cost_estimate=cost,
                model_name=self.model_name,
                latency_ms=latency_ms,
                metadata={
                    'mode': mode,
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'model_size': response_data.get('model', ''),
                    'load_duration': response_data.get('load_duration'),
                    'prompt_eval_duration': response_data.get('prompt_eval_duration'),
                    'eval_duration': response_data.get('eval_duration')
                }
            )
            
        except aiohttp.ClientError as e:
            raise ModelUnavailableException(f"Ollama API error: {e}")
        except asyncio.TimeoutError:
            raise ModelTimeoutException("Ollama request timed out")
        except Exception as e:
            raise ModelException(f"Ollama generation failed: {e}")
    
    async def batch_generate(self,
                            prompts: List[str],
                            context: Optional[str] = None,
                            mode: str = "default") -> List[ModelResponse]:
        """
        Generate responses for multiple prompts.
        
        Ollama can handle concurrent requests well, so we'll process
        them in parallel with some concurrency limiting.
        """
        # Limit concurrency to avoid overwhelming the local instance
        semaphore = asyncio.Semaphore(4)  # Max 4 concurrent requests
        
        async def generate_with_semaphore(prompt: str):
            async with semaphore:
                return await self.generate(prompt, context, mode)
        
        # Process all prompts concurrently
        tasks = [generate_with_semaphore(prompt) for prompt in prompts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error responses
        final_results = []
        for result in results:
            if isinstance(result, Exception):
                error_response = ModelResponse(
                    content="",
                    tokens_used=0,
                    cost_estimate=0.0,
                    model_name=self.model_name,
                    latency_ms=0,
                    metadata={'error': str(result)}
                )
                final_results.append(error_response)
            else:
                final_results.append(result)
        
        return final_results
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate compute cost for local Ollama model.
        
        Since Ollama runs locally, this estimates relative compute cost
        rather than API pricing.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Estimated relative compute cost
        """
        # Get compute cost for this model or use default
        base_cost = self.COMPUTE_COSTS.get(self.model_name, self.COMPUTE_COSTS['default'])
        
        # Cost is proportional to total tokens processed
        total_tokens = input_tokens + output_tokens
        return (total_tokens / 1000) * base_cost
    
    def get_context_limit(self) -> int:
        """
        Get context limit for this Ollama model.
        
        Returns:
            Context limit in tokens
        """
        return self.CONTEXT_LIMITS.get(self.model_name, self.CONTEXT_LIMITS['default'])
    
    async def validate_availability(self) -> bool:
        """
        Check if Ollama instance is available and model is loaded.
        
        Returns:
            True if Ollama and model are available
        """
        try:
            session = await self._get_session()
            
            # Check if Ollama is running
            async with session.get(f"{self.api_endpoint}/api/tags") as response:
                if response.status != 200:
                    return False
                
                # Check if our model is available
                models_data = await response.json()
                model_names = [model['name'] for model in models_data.get('models', [])]
                
                # Check exact match or partial match
                return (self.model_name in model_names or 
                       any(self.model_name.startswith(name.split(':')[0]) for name in model_names))
                
        except Exception as e:
            logger.debug(f"Ollama availability check failed: {e}")
            return False
    
    def supports_mode(self, mode: str) -> bool:
        """
        Most Ollama models support all modes, but some might be optimized for specific tasks.
        """
        return True
    
    def prepare_prompt_for_mode(self, prompt: str, mode: str) -> str:
        """
        Prepare prompt for Ollama models.
        
        Some Ollama models work better with specific prompt formats.
        """
        # For classification, we might want more specific instructions
        if mode == 'classify':
            return f"""You are a precise classification assistant. Analyze the following and provide only the requested output format.

{prompt}

Remember: Provide ONLY the numerical score or classification as requested, with no additional text."""
        
        # For other modes, use base implementation
        return super().prepare_prompt_for_mode(prompt, mode)
    
    def _prepare_full_prompt(self, prompt: str, context: Optional[str], mode: str) -> str:
        """
        Prepare the full prompt with context and mode instructions.
        
        Args:
            prompt: Base prompt
            context: Optional context content
            mode: Operation mode
            
        Returns:
            Complete prompt ready for model
        """
        # Start with mode-prepared prompt
        full_prompt = self.prepare_prompt_for_mode(prompt, mode)
        
        # Add context if provided
        if context:
            full_prompt = f"{context}\n\n{full_prompt}"
        
        # Ensure we don't exceed context limit
        context_limit = self.get_context_limit()
        if len(full_prompt) > context_limit * 3:  # Rough character to token ratio
            # Truncate context but keep the main prompt
            context_part = context if context else ""
            prompt_part = self.prepare_prompt_for_mode(prompt, mode)
            
            max_context_chars = (context_limit * 3) - len(prompt_part) - 100  # Buffer
            if len(context_part) > max_context_chars:
                context_part = context_part[:max_context_chars] + "\n[... truncated for length ...]"
            
            full_prompt = f"{context_part}\n\n{prompt_part}" if context_part else prompt_part
        
        return full_prompt
    
    async def _call_ollama_api(self, prompt: str) -> Dict[str, Any]:
        """
        Call Ollama API to generate response.
        
        Args:
            prompt: The complete prompt to send
            
        Returns:
            Ollama API response data
        """
        session = await self._get_session()
        
        request_data = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,  # Get complete response
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            }
        }
        
        # Add custom parameters if specified
        if self.config.custom_params:
            request_data["options"].update(self.config.custom_params)
        
        url = f"{self.api_endpoint}/api/generate"
        
        async with session.post(url, json=request_data) as response:
            if response.status != 200:
                error_text = await response.text()
                raise ModelException(f"Ollama API error {response.status}: {error_text}")
            
            return await response.json()
    
    async def close(self):
        """Close the HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()