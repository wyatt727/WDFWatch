#!/usr/bin/env python3
"""
Quality moderation stage - Claude evaluates its own responses for quality
"""

import logging
import json
from pathlib import Path
from typing import Dict, List

from core import UnifiedInterface
from core.episode_manager import EpisodeManager

logger = logging.getLogger(__name__)

class QualityModerator:
    """
    Claude evaluates response quality using episode context.
    """
    
    def __init__(self, claude: UnifiedInterface):
        """
        Initialize quality moderator.
        
        Args:
            claude: Claude interface instance
        """
        self.claude = claude
        self.episode_mgr = EpisodeManager()
        logger.info("Quality moderator initialized")
    
    def moderate_responses(self, responses: List[Dict], episode_id: str) -> List[Dict]:
        """
        Evaluate quality of all responses.
        
        Args:
            responses: List of tweets with responses
            episode_id: Episode ID for context
            
        Returns:
            Responses with quality scores and feedback
        """
        if not responses:
            return []
        
        logger.info(f"Moderating {len(responses)} responses for episode {episode_id}")
        
        # Set episode context
        self.claude.set_episode_context(episode_id)
        
        # Get episode directory
        episode_dir = self.episode_mgr.get_episode_dir(episode_id)
        
        # Moderate each response
        moderated = []
        approved_count = 0
        
        for response_data in responses:
            tweet = response_data.get('text', response_data.get('full_text', ''))
            response = response_data.get('response', '')
            
            if not response:
                continue
            
            # Evaluate quality
            evaluation = self.moderate_single(response, tweet, episode_id)
            
            # Add evaluation to response data
            response_data['moderation'] = evaluation
            response_data['quality_approved'] = evaluation['approved']
            response_data['quality_score'] = evaluation['overall_score']
            
            if evaluation['approved']:
                approved_count += 1
            
            moderated.append(response_data)
        
        # Save moderated responses
        if episode_dir:
            moderated_file = episode_dir / "moderated_responses.json"
            with open(moderated_file, 'w') as f:
                json.dump(moderated, f, indent=2)
            logger.info(f"Saved moderated responses to {moderated_file}")
        
        logger.info(f"Moderation complete: {approved_count}/{len(moderated)} approved")
        
        return moderated
    
    def moderate_single(self, response: str, tweet: str, episode_id: str) -> Dict:
        """
        Evaluate a single response.
        
        Args:
            response: Generated response
            tweet: Original tweet
            episode_id: Episode ID for context
            
        Returns:
            Evaluation results
        """
        # Episode CLAUDE.md provides all context
        evaluation = self.claude.moderate_response(
            response=response,
            tweet=tweet,
            episode_id=episode_id
        )
        
        # Add automatic checks
        evaluation = self._add_automatic_checks(evaluation, response)
        
        return evaluation
    
    def _add_automatic_checks(self, evaluation: Dict, response: str) -> Dict:
        """
        Add automatic quality checks.
        
        Args:
            evaluation: Claude's evaluation
            response: Response text
            
        Returns:
            Enhanced evaluation
        """
        # Check character count
        char_count = len(response)
        evaluation['char_count'] = char_count
        evaluation['char_limit_ok'] = char_count <= 200
        
        # Check for required elements
        has_wdf = 'WDF' in response or 'War, Divorce' in response
        evaluation['mentions_podcast'] = has_wdf
        
        # Check for URL
        has_url = 'http' in response or 'youtu' in response
        evaluation['has_url'] = has_url
        
        # Check for emojis
        import re
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F6FF"
            "]+", flags=re.UNICODE)
        has_emojis = bool(emoji_pattern.search(response))
        evaluation['no_emojis'] = not has_emojis
        
        # Update approval based on hard requirements
        if not evaluation['char_limit_ok'] or not has_wdf or has_emojis:
            evaluation['approved'] = False
            evaluation['auto_rejected'] = True
            evaluation['rejection_reason'] = []
            
            if not evaluation['char_limit_ok']:
                evaluation['rejection_reason'].append(f"Too long ({char_count} chars)")
            if not has_wdf:
                evaluation['rejection_reason'].append("Doesn't mention WDF Podcast")
            if has_emojis:
                evaluation['rejection_reason'].append("Contains emojis")
        
        return evaluation
    
    def get_quality_report(self, moderated: List[Dict]) -> Dict:
        """
        Generate quality report for moderated responses.
        
        Args:
            moderated: List of moderated responses
            
        Returns:
            Quality statistics
        """
        if not moderated:
            return {
                'total': 0,
                'approved': 0,
                'rejected': 0,
                'approval_rate': 0
            }
        
        approved = sum(1 for r in moderated if r.get('quality_approved'))
        rejected = len(moderated) - approved
        
        # Calculate average scores
        scores = {
            'relevance': [],
            'engagement': [],
            'connection': [],
            'tone': [],
            'overall': []
        }
        
        for response in moderated:
            mod = response.get('moderation', {})
            scores['relevance'].append(mod.get('relevance', 0))
            scores['engagement'].append(mod.get('engagement', 0))
            scores['connection'].append(mod.get('connection', 0))
            scores['tone'].append(mod.get('tone', 0))
            scores['overall'].append(mod.get('overall_score', 0))
        
        avg_scores = {
            key: sum(values) / len(values) if values else 0
            for key, values in scores.items()
        }
        
        # Find common rejection reasons
        rejection_reasons = {}
        for response in moderated:
            if not response.get('quality_approved'):
                reasons = response.get('moderation', {}).get('rejection_reason', [])
                if isinstance(reasons, list):
                    for reason in reasons:
                        rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                elif reasons:
                    rejection_reasons[str(reasons)] = rejection_reasons.get(str(reasons), 0) + 1
        
        return {
            'total': len(moderated),
            'approved': approved,
            'rejected': rejected,
            'approval_rate': round(approved / len(moderated) * 100, 1),
            'average_scores': avg_scores,
            'rejection_reasons': rejection_reasons
        }