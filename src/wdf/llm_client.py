"""
Unified LLM Client
==================

Provides a unified interface for interacting with different LLM providers:
- Ollama (local models)
- OpenAI (GPT models)
- Gemini (via gemini CLI)

This module abstracts the differences between providers and provides
a consistent interface for the pipeline tasks.

Related files:
- /scripts/load_llm_config.py (loads model configuration)
- /scripts/load_api_keys.py (loads API keys)
- /web/lib/llm-models.ts (model definitions)
"""

import os
import subprocess
import json
import logging
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
import tempfile

# Try to import optional dependencies
try:
    from ollama import Client as OllamaClient
except ImportError:
    OllamaClient = None

try:
    import openai
except ImportError:
    openai = None

logger = logging.getLogger(__name__)


class UnifiedLLMClient:
    """Unified client for all LLM providers"""
    
    def __init__(self):
        self.ollama_client = None
        self.openai_client = None
        self._init_clients()
    
    def _init_clients(self):
        """Initialize available clients"""
        # Initialize Ollama client
        if OllamaClient:
            try:
                self.ollama_client = OllamaClient(
                    host=os.environ.get("WDF_OLLAMA_HOST", "http://localhost:11434")
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Ollama client: {e}")
        
        # Initialize OpenAI client
        if openai:
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key:
                try:
                    self.openai_client = openai.OpenAI(api_key=api_key)
                except Exception as e:
                    logger.warning(f"Failed to initialize OpenAI client: {e}")
    
    def get_provider(self, model: str) -> str:
        """Determine the provider from the model name"""
        if model.startswith("gpt-"):
            return "openai"
        elif model.startswith("gemini"):
            return "gemini"
        else:
            # Assume Ollama for all other models
            return "ollama"
    
    def generate(
        self, 
        model: str, 
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Generate text using the specified model"""
        provider = self.get_provider(model)
        
        if provider == "ollama":
            return self._generate_ollama(model, prompt, system, temperature, **kwargs)
        elif provider == "openai":
            return self._generate_openai(model, prompt, system, temperature, max_tokens, **kwargs)
        elif provider == "gemini":
            return self._generate_gemini(model, prompt, system, temperature, **kwargs)
        else:
            raise ValueError(f"Unknown provider for model: {model}")
    
    def _generate_ollama(self, model: str, prompt: str, system: Optional[str], temperature: float, **kwargs) -> str:
        """Generate using Ollama"""
        if not self.ollama_client:
            raise RuntimeError("Ollama client not available. Please install ollama package.")
        
        # Build messages
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        # Use raw format if specified (for models like gemma that need special formatting)
        if kwargs.get("raw_format"):
            # Format as raw prompt for models that need it
            full_prompt = kwargs.get("formatted_prompt", prompt)
            response = self.ollama_client.generate(
                model=model,
                prompt=full_prompt,
                options={"temperature": temperature}
            )
            return response["response"]
        else:
            # Use chat format
            response = self.ollama_client.chat(
                model=model,
                messages=messages,
                options={"temperature": temperature}
            )
            return response["message"]["content"]
    
    def _generate_openai(
        self, 
        model: str, 
        prompt: str, 
        system: Optional[str], 
        temperature: float,
        max_tokens: Optional[int],
        **kwargs
    ) -> str:
        """Generate using OpenAI"""
        if not self.openai_client:
            raise RuntimeError("OpenAI client not available. Please set OPENAI_API_KEY.")
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        # Create completion
        params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if max_tokens:
            params["max_tokens"] = max_tokens
        
        response = self.openai_client.chat.completions.create(**params)
        return response.choices[0].message.content
    
    def _generate_gemini(self, model: str, prompt: str, system: Optional[str], temperature: float, **kwargs) -> str:
        """Generate using Gemini CLI"""
        # Check if gemini CLI is available
        try:
            subprocess.run(["gemini", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("Gemini CLI not available. Please install gemini-cli.")
        
        # Combine system and prompt
        full_prompt = prompt
        if system:
            full_prompt = f"{system}\n\n{prompt}"
        
        # Write prompt to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(full_prompt)
            prompt_file = f.name
        
        try:
            # Run gemini CLI
            cmd = ["gemini", "-m", model, "-f", prompt_file]
            
            # Add temperature if not default
            if temperature != 0.7:
                cmd.extend(["-t", str(temperature)])
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        
        finally:
            # Clean up temp file
            if os.path.exists(prompt_file):
                os.unlink(prompt_file)
    
    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Chat completion with message history"""
        provider = self.get_provider(model)
        
        if provider == "openai":
            if not self.openai_client:
                raise RuntimeError("OpenAI client not available. Please set OPENAI_API_KEY.")
            
            params = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
            
            if max_tokens:
                params["max_tokens"] = max_tokens
            
            response = self.openai_client.chat.completions.create(**params)
            return response.choices[0].message.content
        
        elif provider == "ollama":
            if not self.ollama_client:
                raise RuntimeError("Ollama client not available. Please install ollama package.")
            
            response = self.ollama_client.chat(
                model=model,
                messages=messages,
                options={"temperature": temperature}
            )
            return response["message"]["content"]
        
        else:
            # For Gemini, convert to single prompt
            system_msgs = [m["content"] for m in messages if m["role"] == "system"]
            user_msgs = [m["content"] for m in messages if m["role"] == "user"]
            assistant_msgs = [m["content"] for m in messages if m["role"] == "assistant"]
            
            # Build prompt
            prompt_parts = []
            if system_msgs:
                prompt_parts.append("\n".join(system_msgs))
            
            # Interleave user and assistant messages
            for i, user_msg in enumerate(user_msgs):
                prompt_parts.append(f"User: {user_msg}")
                if i < len(assistant_msgs):
                    prompt_parts.append(f"Assistant: {assistant_msgs[i]}")
            
            return self._generate_gemini(model, "\n\n".join(prompt_parts), None, temperature)


# Singleton instance
_client = None

def get_llm_client() -> UnifiedLLMClient:
    """Get the singleton LLM client instance"""
    global _client
    if _client is None:
        _client = UnifiedLLMClient()
    return _client


# Convenience functions for backward compatibility
def generate_text(
    model: str,
    prompt: str,
    system: Optional[str] = None,
    temperature: float = 0.7,
    **kwargs
) -> str:
    """Generate text using the specified model"""
    client = get_llm_client()
    return client.generate(model, prompt, system, temperature, **kwargs)


def chat_completion(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    **kwargs
) -> str:
    """Chat completion with message history"""
    client = get_llm_client()
    return client.chat(model, messages, temperature, **kwargs)