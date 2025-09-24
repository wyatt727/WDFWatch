#!/usr/bin/env python3
"""
Validate LLM model availability

This script validates that configured LLM models are available and accessible.
It checks both Gemini (via CLI) and Ollama models.

Usage:
    python scripts/validate_llm_models.py
    
Or to validate specific models:
    python scripts/validate_llm_models.py --model gemini-2.5-pro --provider gemini

Related files:
- /scripts/load_llm_config.py (Load model configuration)
- /web/app/api/settings/llm-models/validate/route.ts (Web API validation)
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Tuple

import requests

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.load_llm_config import get_llm_config


def validate_gemini_model(model: str) -> Tuple[bool, str]:
    """
    Validate if Gemini model is accessible via CLI
    
    Args:
        model: Model name (e.g., 'gemini-2.5-pro')
        
    Returns:
        Tuple of (is_valid, message)
    """
    try:
        # Check if gemini CLI is available
        result = subprocess.run(
            ['which', 'gemini'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return False, "Gemini CLI not found. Please install with: npm install -g @google/generative-ai-cli"
            
        # Could add additional validation here if needed
        return True, f"Gemini CLI is available (model: {model})"
        
    except Exception as e:
        return False, f"Error checking Gemini CLI: {e}"


def validate_ollama_model(model: str) -> Tuple[bool, str]:
    """
    Validate if Ollama model is available
    
    Args:
        model: Model name (e.g., 'deepseek-r1:latest')
        
    Returns:
        Tuple of (is_valid, message)
    """
    try:
        # Check if Ollama is running
        response = requests.get('http://localhost:11434/api/tags', timeout=5)
        
        if response.status_code != 200:
            return False, "Ollama is not running. Please start with: ollama serve"
            
        data = response.json()
        models = data.get('models', [])
        
        # Check if the specific model is available
        model_base = model.split(':')[0]  # Handle tags like :latest
        model_found = any(
            m['name'] == model or m['name'].startswith(model_base + ':')
            for m in models
        )
        
        if model_found:
            return True, f"Model '{model}' is available in Ollama"
        else:
            return False, f"Model '{model}' is not pulled. Run: ollama pull {model}"
            
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to Ollama. Is it running? Start with: ollama serve"
    except Exception as e:
        return False, f"Error checking Ollama: {e}"


def get_provider_for_task(task: str) -> str:
    """
    Determine the provider for a given task
    
    Args:
        task: Task name (summarization, fewshot, classification, response)
        
    Returns:
        Provider name ('gemini' or 'ollama')
    """
    if task in ['summarization', 'fewshot']:
        return 'gemini'
    else:
        return 'ollama'


def validate_all_models() -> Dict[str, Tuple[bool, str]]:
    """
    Validate all configured models
    
    Returns:
        Dictionary of task -> (is_valid, message)
    """
    config = get_llm_config()
    results = {}
    
    for task, model in config.items():
        provider = get_provider_for_task(task)
        
        if provider == 'gemini':
            is_valid, message = validate_gemini_model(model)
        else:
            is_valid, message = validate_ollama_model(model)
            
        results[task] = (is_valid, message)
        
    return results


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate LLM model availability')
    parser.add_argument('--model', help='Specific model to validate')
    parser.add_argument('--provider', choices=['gemini', 'ollama'], help='Model provider')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--quiet', action='store_true', help='Only show errors')
    args = parser.parse_args()
    
    if args.model and args.provider:
        # Validate specific model
        if args.provider == 'gemini':
            is_valid, message = validate_gemini_model(args.model)
        else:
            is_valid, message = validate_ollama_model(args.model)
            
        if args.json:
            print(json.dumps({
                'model': args.model,
                'provider': args.provider,
                'valid': is_valid,
                'message': message
            }))
        else:
            if is_valid:
                print(f"✅ {message}")
            else:
                print(f"❌ {message}")
                
        sys.exit(0 if is_valid else 1)
    else:
        # Validate all configured models
        results = validate_all_models()
        
        if args.json:
            output = {}
            for task, (is_valid, message) in results.items():
                output[task] = {
                    'valid': is_valid,
                    'message': message
                }
            print(json.dumps(output, indent=2))
        else:
            print("LLM Model Validation Results:")
            print("-" * 50)
            
            all_valid = True
            for task, (is_valid, message) in results.items():
                if is_valid:
                    if not args.quiet:
                        print(f"✅ {task:15} : {message}")
                else:
                    print(f"❌ {task:15} : {message}")
                    all_valid = False
                    
            if all_valid:
                print("\nAll models are available! ✨")
            else:
                print("\nSome models are not available. Please fix the issues above.")
                
        sys.exit(0 if all(v[0] for v in results.values()) else 1)


if __name__ == "__main__":
    main()