"""Core components for the unified Claude pipeline."""

from .unified_interface import UnifiedInterface, ClaudeInterface  # ClaudeInterface is an alias for backward compatibility
from .episode_manager import EpisodeManager
from .episode_context import EpisodeContext
from .cache import ResponseCache
from .cost_tracker import CostTracker
from .batch_processor import BatchProcessor
from .model_factory import ModelFactory
from .model_interface import ModelInterface, ModelResponse, ModelConfig, ModelException
from .context_adapter import ContextAdapter

__all__ = [
    'UnifiedInterface',
    'ClaudeInterface',  # Backward compatibility
    'EpisodeManager',
    'EpisodeContext',
    'ResponseCache',
    'CostTracker',
    'BatchProcessor',
    'ModelFactory',
    'ModelInterface',
    'ModelResponse',
    'ModelConfig',
    'ModelException',
    'ContextAdapter'
]