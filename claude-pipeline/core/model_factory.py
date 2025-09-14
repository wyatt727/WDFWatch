#!/usr/bin/env python3
"""
Model Factory - Creates and configures model instances

This module provides the ModelFactory class which is responsible for:
- Loading LLM configuration from database or environment
- Creating appropriate model adapters based on configuration
- Validating model availability
- Managing model lifecycle

Integrates with:
- Web UI LLM settings (/settings/llm-models)
- Environment variable overrides
- Default fallback configuration
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Any, Type

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from .model_interface import ModelInterface, ModelConfig, ModelException
from .models import ClaudeAdapter, OllamaAdapter

logger = logging.getLogger(__name__)


class ModelFactory:
    """
    Factory class for creating and managing model instances.
    
    This factory handles the creation of appropriate model adapters
    based on configuration, provider detection, and availability checking.
    """
    
    # Model provider mapping
    PROVIDER_MAPPING = {
        # Claude CLI models (use simple names - CLI handles versioning)
        'claude': 'claude',  # Defaults to sonnet (Claude 4) in CLI
        'sonnet': 'claude',  # Explicit sonnet
        'haiku': 'claude',   # Claude 3.5 Haiku
        'opus': 'claude',    # Claude 3 Opus
        
        # Legacy Claude API model names (for backward compatibility)
        'claude-3-haiku': 'claude',
        'claude-3-sonnet': 'claude',
        'claude-3-opus': 'claude',
        'claude-3.5-sonnet': 'claude',
        'claude-3.5-haiku': 'claude',
        
        # Gemini models (will be handled by Claude for now, could be separate later)
        'gemini-2.5-pro': 'claude',  # Assuming Claude CLI handles Gemini
        'gemini-2.5-flash': 'claude',
        'gemini-pro': 'claude',
        
        # Ollama models
        'llama3.3:70b': 'ollama',
        'llama3.1:8b': 'ollama',
        'llama3.1:70b': 'ollama',
        'gemma2:9b': 'ollama',
        'gemma2:27b': 'ollama',
        'gemma3n:e4b': 'ollama',
        'deepseek-r1:latest': 'ollama',
        'deepseek-coder:6.7b': 'ollama',
        'qwen2.5:32b': 'ollama',
        'mixtral:8x7b': 'ollama',
        'phi3:14b': 'ollama',
    }
    
    # Model adapter mapping
    ADAPTER_CLASSES: Dict[str, Type[ModelInterface]] = {
        'claude': ClaudeAdapter,
        'ollama': OllamaAdapter,
    }
    
    # Default model configuration per task
    DEFAULT_TASK_MODELS = {
        'summarization': 'claude',  # CLI defaults to sonnet (Claude 4)
        'fewshot': 'claude',        # CLI defaults to sonnet (Claude 4)
        'classification': 'claude',  # Use Claude for classification with reasoning
        'response': 'claude',       # Use Claude for response generation
        'moderation': 'claude'      # CLI defaults to sonnet (Claude 4)
    }
    
    # Model capability definitions - which tasks each model is good at
    MODEL_CAPABILITIES = {
        # Claude models - excellent at all tasks
        'claude': {
            'can_summarize': True,
            'can_generate_fewshots': True,
            'can_classify': True,
            'can_respond': True,
            'can_moderate': True,
            'quality_rating': 'excellent'
        },
        'sonnet': {
            'can_summarize': True,
            'can_generate_fewshots': True,
            'can_classify': True,
            'can_respond': True,
            'can_moderate': True,
            'quality_rating': 'excellent'
        },
        'haiku': {
            'can_summarize': True,
            'can_generate_fewshots': True,
            'can_classify': True,
            'can_respond': True,
            'can_moderate': True,
            'quality_rating': 'good'
        },
        'opus': {
            'can_summarize': True,
            'can_generate_fewshots': True,
            'can_classify': True,
            'can_respond': True,
            'can_moderate': True,
            'quality_rating': 'excellent'
        },
        
        # Ollama models - specialized capabilities
        'gemma3n:e4b': {
            'can_summarize': False,  # Optimized for classification
            'can_generate_fewshots': False,
            'can_classify': True,
            'can_respond': False,
            'can_moderate': False,
            'quality_rating': 'excellent'  # For classification only
        },
        'llama3.3:70b': {
            'can_summarize': True,
            'can_generate_fewshots': True,
            'can_classify': True,
            'can_respond': True,
            'can_moderate': True,  # Large model can handle evaluation
            'quality_rating': 'good'
        },
        'deepseek-r1:latest': {
            'can_summarize': True,
            'can_generate_fewshots': True,
            'can_classify': True,
            'can_respond': True,
            'can_moderate': False,  # Focused on reasoning, not evaluation
            'quality_rating': 'good'
        },
        'qwen2.5:32b': {
            'can_summarize': True,
            'can_generate_fewshots': True,
            'can_classify': True,
            'can_respond': True,
            'can_moderate': False,
            'quality_rating': 'good'
        },
        'mixtral:8x7b': {
            'can_summarize': True,
            'can_generate_fewshots': True,
            'can_classify': True,
            'can_respond': True,
            'can_moderate': False,
            'quality_rating': 'good'
        },
        'phi3:14b': {
            'can_summarize': False,
            'can_generate_fewshots': False,
            'can_classify': True,
            'can_respond': False,
            'can_moderate': False,
            'quality_rating': 'fair'
        }
    }
    
    def __init__(self):
        """Initialize the model factory."""
        self._model_cache: Dict[str, ModelInterface] = {}
        self._config_cache: Optional[Dict] = None
        logger.info("ModelFactory initialized")
    
    def create_model_for_task(self, task_type: str, config_override: Optional[Dict] = None, check_enabled: bool = True) -> Optional[ModelInterface]:
        """
        Create a model instance for a specific task type.
        
        Args:
            task_type: The task type (summarization, classification, response, etc.)
            config_override: Optional configuration overrides
            check_enabled: Whether to check if the stage is enabled (default: True)
            
        Returns:
            Configured model instance, or None if stage is disabled
        """
        # Check if stage is enabled (if requested)
        if check_enabled and not self.is_stage_enabled(task_type):
            logger.info(f"Stage {task_type} is disabled, skipping model creation")
            return None
        
        # Get model configuration
        model_config = self.load_model_config()
        model_name = model_config.get(task_type, self.DEFAULT_TASK_MODELS.get(task_type, 'claude'))
        
        # Apply task-specific configurations
        task_config = config_override or {}
        
        # Summarization needs much longer timeout for processing long transcripts
        if task_type in ['summarization', 'summarize']:
            task_config['timeout_seconds'] = 1200  # 20 minutes for summarization
            logger.info(f"Using extended timeout for {task_type}: 1200 seconds")
        
        # Create model instance with task-specific config
        return self.create_model(model_name, task_config)
    
    def create_model(self, model_name: str, config_override: Optional[Dict] = None) -> ModelInterface:
        """
        Create a model instance for a specific model name.
        
        Args:
            model_name: Name of the model to create
            config_override: Optional configuration overrides
            
        Returns:
            Configured model instance
        """
        cache_key = f"{model_name}_{hash(str(config_override))}"
        
        # Check cache first
        if cache_key in self._model_cache:
            return self._model_cache[cache_key]
        
        # Determine provider
        provider = self._detect_provider(model_name)
        if not provider:
            raise ModelException(f"Unknown model provider for: {model_name}")
        
        # Get adapter class
        adapter_class = self.ADAPTER_CLASSES.get(provider)
        if not adapter_class:
            raise ModelException(f"No adapter available for provider: {provider}")
        
        # Create model configuration
        model_config = self._create_model_config(model_name, provider, config_override)
        
        # Create and cache model instance
        try:
            model_instance = adapter_class(model_config)
            self._model_cache[cache_key] = model_instance
            
            logger.info(f"Created model instance: {model_name} ({provider})")
            return model_instance
            
        except Exception as e:
            raise ModelException(f"Failed to create model {model_name}: {e}")
    
    def load_model_config(self) -> Dict[str, str]:
        """
        Load LLM model configuration from database or environment.
        
        Returns:
            Dictionary mapping task types to model names
        """
        if self._config_cache is not None:
            return self._config_cache
        
        # Try loading from database first
        db_config = self._load_config_from_database()
        if db_config:
            self._config_cache = db_config
            return db_config
        
        # Fall back to environment variables
        env_config = self._load_config_from_environment()
        if env_config:
            self._config_cache = env_config
            return env_config
        
        # Use defaults
        self._config_cache = self.DEFAULT_TASK_MODELS.copy()
        return self._config_cache
    
    def validate_model_availability(self, model_name: str) -> bool:
        """
        Check if a model is available and properly configured.
        
        Args:
            model_name: Name of the model to validate
            
        Returns:
            True if model is available
        """
        try:
            model_instance = self.create_model(model_name)
            return model_instance.validate_availability()
        except Exception as e:
            logger.debug(f"Model {model_name} validation failed: {e}")
            return False
    
    def get_available_models(self) -> Dict[str, bool]:
        """
        Get a list of all known models and their availability status.
        
        Returns:
            Dictionary mapping model names to availability status
        """
        availability = {}
        
        for model_name in self.PROVIDER_MAPPING.keys():
            availability[model_name] = self.validate_model_availability(model_name)
        
        return availability
    
    def clear_cache(self):
        """Clear the model cache."""
        self._model_cache.clear()
        self._config_cache = None
        logger.info("Model factory cache cleared")
    
    def _detect_provider(self, model_name: str) -> Optional[str]:
        """
        Detect the provider for a given model name.
        
        Args:
            model_name: Name of the model
            
        Returns:
            Provider name or None if unknown
        """
        # Direct mapping
        if model_name in self.PROVIDER_MAPPING:
            return self.PROVIDER_MAPPING[model_name]
        
        # Pattern matching for Ollama models (contain colons typically)
        if ':' in model_name:
            return 'ollama'
        
        # Pattern matching for Claude models
        if any(pattern in model_name.lower() for pattern in ['claude', 'sonnet', 'haiku', 'opus']):
            return 'claude'
        
        # Pattern matching for Gemini models
        if 'gemini' in model_name.lower():
            return 'claude'  # Assuming Claude CLI handles Gemini for now
        
        # Default to Ollama for unknown models (local models)
        logger.warning(f"Unknown model {model_name}, defaulting to Ollama provider")
        return 'ollama'
    
    def _create_model_config(self, model_name: str, provider: str, config_override: Optional[Dict]) -> ModelConfig:
        """
        Create a ModelConfig instance for the given model and provider.
        
        Args:
            model_name: Name of the model
            provider: Provider type
            config_override: Optional configuration overrides
            
        Returns:
            ModelConfig instance
        """
        # Base configuration
        base_config = {
            'model_name': model_name,
            'provider': provider,
            'temperature': 0.3,
            'max_tokens': 4096,
            'timeout_seconds': 120,
            'retry_attempts': 3
        }
        
        # Provider-specific defaults
        if provider == 'claude':
            base_config.update({
                'context_limit': 200000,
                'timeout_seconds': 180  # Claude can be slower
            })
        elif provider == 'ollama':
            base_config.update({
                'api_endpoint': os.environ.get('WDF_OLLAMA_HOST', 'http://localhost:11434'),
                'context_limit': 8192,  # Will be overridden by model-specific limits
                'timeout_seconds': 60
            })
        
        # Apply overrides
        if config_override:
            base_config.update(config_override)
        
        return ModelConfig(**base_config)
    
    def _load_config_from_database(self) -> Optional[Dict[str, str]]:
        """
        Load model configuration from PostgreSQL database.
        
        Returns:
            Model configuration dictionary or None if failed
        """
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            
            # Get database URL
            db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/wdfwatch')
            
            conn = psycopg2.connect(db_url)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT value FROM settings WHERE key = %s", ('llm_models',))
                result = cur.fetchone()
                
                if result and result['value']:
                    config = result['value']
                    logger.info("Loaded model config from database")
                    return config
            
            conn.close()
            
        except ImportError:
            logger.debug("psycopg2 not available, skipping database config")
        except Exception as e:
            logger.debug(f"Failed to load config from database: {e}")
        
        return None
    
    def _load_config_from_environment(self) -> Optional[Dict[str, str]]:
        """
        Load model configuration from environment variables.
        
        Returns:
            Model configuration dictionary or None if not found
        """
        config = {}
        
        # Check for task-specific environment variables
        env_mappings = {
            'summarization': ['WDF_LLM_MODEL_SUMMARIZATION', 'WDF_LLM_MODELS__SUMMARIZATION'],
            'fewshot': ['WDF_LLM_MODEL_FEWSHOT', 'WDF_LLM_MODELS__FEWSHOT'],
            'classification': ['WDF_LLM_MODEL_CLASSIFICATION', 'WDF_LLM_MODELS__CLASSIFICATION'],
            'response': ['WDF_LLM_MODEL_RESPONSE', 'WDF_LLM_MODELS__RESPONSE'],
            'moderation': ['WDF_LLM_MODEL_MODERATION', 'WDF_LLM_MODELS__MODERATION']
        }
        
        for task, env_vars in env_mappings.items():
            for env_var in env_vars:
                if env_var in os.environ:
                    config[task] = os.environ[env_var]
                    break
        
        if config:
            logger.info("Loaded model config from environment variables")
            return config
        
        return None
    
    def is_stage_enabled(self, task_type: str) -> bool:
        """
        Check if a pipeline stage is enabled.
        
        Args:
            task_type: The task/stage type to check
            
        Returns:
            True if stage is enabled, False otherwise
        """
        try:
            # Try loading from database first
            stage_config = self._load_stage_config_from_database()
            if stage_config:
                stage_info = stage_config.get(task_type, {})
                return stage_info.get('enabled', True)  # Default to enabled
            
            # Fall back to environment variables
            env_var = f"WDF_STAGE_{task_type.upper()}_ENABLED"
            if env_var in os.environ:
                return os.environ[env_var].lower() in ['true', '1', 'yes']
            
            # Default stage enablement rules
            default_enabled = {
                'summarization': True,   # Always required
                'fewshot': False,        # Not needed for Claude pipeline
                'scraping': True,        # Always required
                'classification': True,  # Always required
                'response': True,        # Usually wanted
                'moderation': False      # Optional quality check
            }
            
            return default_enabled.get(task_type, True)
            
        except Exception as e:
            logger.debug(f"Failed to check stage enabled status for {task_type}: {e}")
            return True  # Default to enabled on error
    
    def _load_stage_config_from_database(self) -> Optional[Dict]:
        """
        Load stage configuration from PostgreSQL database.
        
        Returns:
            Stage configuration dictionary or None if failed
        """
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            
            # Get database URL
            db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/wdfwatch')
            
            conn = psycopg2.connect(db_url)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT value FROM settings WHERE key = %s", ('pipeline_stages',))
                result = cur.fetchone()
                
                if result and result['value']:
                    config = result['value']
                    logger.info("Loaded stage config from database")
                    return config
            
            conn.close()
            
        except ImportError:
            logger.debug("psycopg2 not available, skipping database stage config")
        except Exception as e:
            logger.debug(f"Failed to load stage config from database: {e}")
        
        return None