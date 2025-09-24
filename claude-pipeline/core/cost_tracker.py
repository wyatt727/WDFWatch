#!/usr/bin/env python3
"""
Cost tracking for multi-provider LLM usage
"""

import json
from pathlib import Path
from typing import Dict, Union
import logging

logger = logging.getLogger(__name__)

class CostTracker:
    """Cost tracking for multiple LLM providers."""
    
    def __init__(self):
        """Initialize cost tracker."""
        self.costs = {
            'total': 0.0,
            'by_mode': {},
            'by_model': {},
            'calls': 0,
            'tokens_used': 0
        }
        logger.debug("Cost tracker initialized")
    
    def track(self, prompt: str, response: str, mode: str):
        """Legacy track method for backward compatibility."""
        # Rough estimate: ~4 chars per token
        input_tokens = len(prompt) / 4
        output_tokens = len(response) / 4
        
        # Claude 3.5 Sonnet pricing (per 1M tokens) as fallback
        cost = (input_tokens * 3.00 + output_tokens * 15.00) / 1_000_000
        
        self._add_to_costs(cost, mode, 'claude-3.5-sonnet', int(input_tokens + output_tokens))
        
        logger.debug(f"Tracked {mode} call: ${cost:.4f}")
    
    def track_response(self, model_response):
        """
        Track cost from a ModelResponse object.
        
        Args:
            model_response: ModelResponse instance with cost and metadata
        """
        from .model_interface import ModelResponse
        
        if not isinstance(model_response, ModelResponse):
            logger.warning("Invalid response type for cost tracking")
            return
        
        cost = model_response.cost_estimate or 0.0
        mode = model_response.metadata.get('mode', 'default')
        model_name = model_response.model_name
        tokens = model_response.tokens_used or 0
        
        self._add_to_costs(cost, mode, model_name, tokens)
        
        logger.debug(f"Tracked {model_name} {mode} call: ${cost:.4f}")
    
    def _add_to_costs(self, cost: float, mode: str, model_name: str, tokens: int):
        """Add cost to tracking data."""
        self.costs['total'] += cost
        self.costs['by_mode'][mode] = self.costs['by_mode'].get(mode, 0) + cost
        self.costs['by_model'][model_name] = self.costs['by_model'].get(model_name, 0) + cost
        self.costs['calls'] += 1
        self.costs['tokens_used'] += tokens
    
    def get_report(self) -> Dict:
        """Get comprehensive cost report."""
        return {
            'total_cost': round(self.costs['total'], 4),
            'calls': self.costs['calls'],
            'tokens_used': self.costs['tokens_used'],
            'avg_cost_per_call': round(self.costs['total'] / max(1, self.costs['calls']), 4),
            'by_mode': {k: round(v, 4) for k, v in self.costs['by_mode'].items()},
            'by_model': {k: round(v, 4) for k, v in self.costs['by_model'].items()}
        }