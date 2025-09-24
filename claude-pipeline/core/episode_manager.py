#!/usr/bin/env python3
"""
Episode Manager - Manages episode directories with self-contained CLAUDE.md files
Each episode gets its own directory with all related files
"""

import hashlib
import json
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class EpisodeManager:
    """
    Manages episode directories where each episode has its own CLAUDE.md.
    This is the optimal architecture - each episode is self-contained.
    """
    
    def __init__(self, episodes_dir: str = None):
        """
        Initialize episode manager.
        
        Args:
            episodes_dir: Base directory for all episodes
        """
        self.episodes_dir = Path(episodes_dir) if episodes_dir else Path("episodes")
        self.episodes_dir.mkdir(exist_ok=True)
        
        # Template for new episodes
        self.template_file = Path(__file__).parent.parent / "CLAUDE_TEMPLATE.md"
        if not self.template_file.exists():
            # Use the master CLAUDE.md as template
            self.template_file = Path(__file__).parent.parent / "CLAUDE.md"
        
        logger.info(f"Episode manager initialized with directory: {self.episodes_dir}")
    
    def create_episode(self, 
                      transcript: str,
                      episode_id: str = None,
                      video_url: str = None) -> Dict:
        """
        Create a new episode directory with initial structure.
        
        Args:
            transcript: Episode transcript
            episode_id: Optional episode ID (generated if not provided)
            video_url: Optional YouTube URL
            
        Returns:
            Episode information dictionary
        """
        # Generate episode ID if not provided
        if not episode_id:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            hash_suffix = hashlib.md5(transcript.encode()).hexdigest()[:6]
            episode_id = f"{timestamp}_{hash_suffix}"
        
        # Create episode directory using episode ID directly
        episode_dir = self.episodes_dir / episode_id
        episode_dir.mkdir(exist_ok=True)
        
        logger.info(f"Creating episode directory: {episode_dir}")
        
        # Save transcript
        (episode_dir / "transcript.txt").write_text(transcript)
        
        # Save video URL if provided
        if video_url:
            (episode_dir / "video_url.txt").write_text(video_url)
        
        # Note: summary.md will be created during summarization stage
        # No need to create EPISODE_CONTEXT.md - summary.md serves as episode context
        
        # Create metadata file
        metadata = {
            'episode_id': episode_id,
            'created_at': datetime.now().isoformat(),
            'transcript_length': len(transcript),
            'video_url': video_url,
            'status': 'created',
            'stages_completed': []
        }
        
        with open(episode_dir / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Update current symlink
        self._update_current_link(episode_dir)
        
        logger.info(f"Episode {episode_id} created successfully")
        
        return {
            'episode_id': episode_id,
            'episode_dir': str(episode_dir),
            'files_created': [
                'transcript.txt',
                'CLAUDE.md',
                'metadata.json',
                'video_url.txt' if video_url else None
            ]
        }
    
    def update_episode_context(self,
                              episode_id: str,
                              summary: str,
                              keywords: List[str],
                              video_url: str = None) -> str:
        """
        Update episode metadata after summarization.
        Note: summary.md is now used as the comprehensive episode context.
        
        Args:
            episode_id: Episode identifier
            summary: Generated summary (already saved to summary.md)
            keywords: Extracted keywords
            video_url: Optional video URL
            
        Returns:
            Path to summary.md file (used as episode context)
        """
        episode_dir = self.get_episode_dir(episode_id)
        if not episode_dir:
            raise ValueError(f"Episode {episode_id} not found")
        
        logger.info(f"Updating episode metadata for episode {episode_id}")
        
        # Extract structured information from summary for metadata
        context_data = self._extract_context_from_summary(summary)
        context_data['keywords'] = keywords
        context_data['video_url'] = video_url or self._get_video_url(episode_dir)
        
        # Update metadata only (summary.md already contains all context)
        self._update_metadata(episode_dir, 'summarized', context_data)
        
        # Return path to summary.md (used as episode context)
        summary_file = episode_dir / "summary.md"
        logger.info(f"Episode context available in summary.md for episode {episode_id}")
        
        return str(summary_file)
    
    def _extract_context_from_summary(self, summary: str) -> Dict:
        """Extract structured context from summary text."""
        context = {
            'guest': {},
            'themes': [],
            'quotes': [],
            'arguments': [],
            'controversies': [],
            'solutions': []
        }
        
        lines = summary.split('\n')
        current_section = None
        
        for line in lines:
            line_lower = line.lower()
            
            # Detect sections
            if 'guest' in line_lower and 'profile' in line_lower:
                current_section = 'guest'
            elif 'theme' in line_lower:
                current_section = 'themes'
            elif 'quote' in line_lower:
                current_section = 'quotes'
            elif 'argument' in line_lower:
                current_section = 'arguments'
            elif 'controvers' in line_lower:
                current_section = 'controversies'
            elif 'solution' in line_lower:
                current_section = 'solutions'
            
            # Extract content
            elif current_section and line.strip():
                if current_section == 'guest' and ':' in line:
                    key, value = line.split(':', 1)
                    context['guest'][key.strip().lower()] = value.strip()
                elif current_section in ['themes', 'arguments', 'solutions', 'controversies']:
                    if line.strip().startswith(('-', '*', '•', '1', '2', '3')):
                        content = line.strip().lstrip('-*•0123456789. ')
                        if content:
                            context[current_section].append(content)
                elif current_section == 'quotes':
                    if '"' in line or '"' in line:
                        import re
                        quotes = re.findall(r'[""]([^""]+)[""]', line)
                        context['quotes'].extend(quotes)
        
        return context
    
    def _build_episode_context(self, context_data: Dict, episode_id: str) -> str:
        """Build pure episode context (no task instructions)."""
        parts = [
            f"# Episode Context: {episode_id}",
            f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            ""
        ]
        
        # Guest information
        if context_data.get('guest'):
            parts.append("## GUEST INFORMATION")
            for key, value in context_data['guest'].items():
                if value:  # Only add non-empty values
                    parts.append(f"**{key.title()}**: {value}")
            parts.append("")
        
        # Themes
        if context_data.get('themes'):
            parts.append("## KEY THEMES DISCUSSED")
            for i, theme in enumerate(context_data['themes'][:10], 1):
                parts.append(f"{i}. {theme}")
            parts.append("")
        
        # Arguments
        if context_data.get('arguments'):
            parts.append("## MAIN ARGUMENTS")
            for i, arg in enumerate(context_data['arguments'][:5], 1):
                parts.append(f"{i}. {arg}")
            parts.append("")
        
        # Quotes
        if context_data.get('quotes'):
            parts.append("## MEMORABLE QUOTES")
            for quote in context_data['quotes'][:5]:
                parts.append(f'- "{quote}"')
            parts.append("")
        
        # Controversies
        if context_data.get('controversies'):
            parts.append("## CONTROVERSIAL POINTS")
            for i, controversy in enumerate(context_data['controversies'][:3], 1):
                parts.append(f"{i}. {controversy}")
            parts.append("")
        
        # Solutions
        if context_data.get('solutions'):
            parts.append("## SOLUTIONS & ACTIONS")
            for solution in context_data['solutions'][:5]:
                parts.append(f"- {solution}")
            parts.append("")
        
        # Keywords
        if context_data.get('keywords'):
            parts.append("## KEYWORDS FOR DISCOVERY")
            parts.append(', '.join(context_data['keywords'][:30]))
            parts.append("")
        
        # Video URL
        if context_data.get('video_url'):
            parts.append("## EPISODE VIDEO")
            parts.append(f"**URL**: {context_data['video_url']}")
            parts.append("*Include this URL in all tweet responses*")
            parts.append("")
        
        return '\n'.join(parts)
    
    def get_episode_dir(self, episode_id: str) -> Optional[Path]:
        """Get directory path for an episode."""
        # Handle None case
        if episode_id is None:
            return None
            
        # Use episode ID directly as directory name
        episode_dir = self.episodes_dir / episode_id
        
        if episode_dir.exists():
            return episode_dir
        return None
    
    def get_current_episode(self) -> Optional[str]:
        """Get the current episode ID."""
        current_link = self.episodes_dir / "current"
        if current_link.exists() and current_link.is_symlink():
            target = current_link.resolve()
            return target.name
        return None
    
    def set_current_episode(self, episode_id: str):
        """Set the current episode."""
        episode_dir = self.get_episode_dir(episode_id)
        if episode_dir:
            self._update_current_link(episode_dir)
        else:
            raise ValueError(f"Episode {episode_id} not found")
    
    def _update_current_link(self, episode_dir: Path):
        """Update the 'current' symlink to point to episode directory."""
        current_link = self.episodes_dir / "current"
        
        # Remove existing link
        if current_link.exists():
            if current_link.is_symlink():
                current_link.unlink()
            else:
                # If it's a real directory, don't delete it
                logger.warning(f"{current_link} is not a symlink, not updating")
                return
        
        # Create new symlink (relative path for portability)
        try:
            current_link.symlink_to(episode_dir.name)
            logger.debug(f"Updated current link to {episode_dir.name}")
        except OSError as e:
            # Symlinks might not work on all systems
            logger.warning(f"Could not create symlink: {e}")
    
    def _get_video_url(self, episode_dir: Path) -> Optional[str]:
        """Get video URL from episode directory."""
        video_file = episode_dir / "video_url.txt"
        if video_file.exists():
            return video_file.read_text().strip()
        return None
    
    def _update_metadata(self, episode_dir: Path, stage: str, data: Dict = None):
        """Update episode metadata."""
        metadata_file = episode_dir / "metadata.json"
        
        if metadata_file.exists():
            with open(metadata_file) as f:
                metadata = json.load(f)
        else:
            metadata = {}
        
        # Update metadata
        metadata['updated_at'] = datetime.now().isoformat()
        metadata['status'] = stage
        
        if stage not in metadata.get('stages_completed', []):
            metadata.setdefault('stages_completed', []).append(stage)
        
        if data:
            if stage == 'moderation':
                metadata[f'{stage}_data'] = {
                    'total_responses': data.get('total_responses', 0),
                    'approved_responses': data.get('approved_responses', 0),
                    'rejected_responses': data.get('rejected_responses', 0),
                    'approval_rate': data.get('approval_rate', 0),
                    'average_scores': data.get('average_scores', {}),
                    'model_used': data.get('model_used', 'unknown')
                }
            else:
                metadata[f'{stage}_data'] = {
                    'guest': data.get('guest', {}),
                    'themes_count': len(data.get('themes', [])),
                    'quotes_count': len(data.get('quotes', [])),
                    'keywords_count': len(data.get('keywords', []))
                }
        
        # Save updated metadata
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def list_episodes(self) -> List[Dict]:
        """List all episodes with their metadata."""
        episodes = []
        
        for episode_dir in self.episodes_dir.glob("episode_*"):
            if episode_dir.is_dir():
                episode_id = episode_dir.name.replace("episode_", "")
                
                # Load metadata
                metadata_file = episode_dir / "metadata.json"
                if metadata_file.exists():
                    with open(metadata_file) as f:
                        metadata = json.load(f)
                else:
                    metadata = {'episode_id': episode_id}
                
                episodes.append(metadata)
        
        # Sort by creation date
        episodes.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        return episodes
    
    def cleanup_old_episodes(self, max_age_days: int = 30):
        """Remove episodes older than specified days."""
        now = datetime.now()
        removed = 0
        
        for episode_dir in self.episodes_dir.glob("episode_*"):
            if not episode_dir.is_dir():
                continue
            
            metadata_file = episode_dir / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file) as f:
                    metadata = json.load(f)
                
                created = datetime.fromisoformat(metadata.get('created_at', ''))
                age = now - created
                
                if age.days > max_age_days:
                    logger.info(f"Removing old episode: {episode_dir.name}")
                    shutil.rmtree(episode_dir)
                    removed += 1
        
        if removed:
            logger.info(f"Cleaned up {removed} old episodes")