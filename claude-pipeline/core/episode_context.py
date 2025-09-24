#!/usr/bin/env python3
"""
Episode Context System - Creates episode-specific CLAUDE.md files
Each episode gets its own context file that extends the master CLAUDE.md
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class EpisodeContext:
    """
    Creates and manages episode-specific CLAUDE.md context files.
    Instead of JSON memories, we create markdown context files that Claude reads directly.
    """
    
    def __init__(self, episode_id: str = None):
        """
        Initialize episode context.
        
        Args:
            episode_id: Unique identifier for the episode
        """
        self.episode_id = episode_id or self._generate_episode_id()
        self.pipeline_dir = Path(__file__).parent.parent
        self.contexts_dir = self.pipeline_dir / "episode_contexts"
        self.contexts_dir.mkdir(exist_ok=True)
        
        # Episode-specific CLAUDE.md file
        self.context_file = self.contexts_dir / f"episode_{self.episode_id}_CLAUDE.md"
        
        # Master CLAUDE.md to use as base
        self.master_context = self.pipeline_dir / "CLAUDE.md"
        
        logger.info(f"Episode context initialized: {self.episode_id}")
    
    def _generate_episode_id(self) -> str:
        """Generate unique episode ID from transcript if not provided."""
        transcript_path = Path(__file__).parent.parent.parent / "transcripts" / "latest.txt"
        if transcript_path.exists():
            content = transcript_path.read_text()
            return hashlib.md5(content.encode()).hexdigest()[:8]
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def create_from_summary(self, 
                           summary: str,
                           keywords: List[str],
                           video_url: str = None) -> str:
        """
        Create episode-specific CLAUDE.md from summary analysis.
        
        Args:
            summary: Full episode summary
            keywords: Extracted keywords
            video_url: YouTube URL for the episode
            
        Returns:
            Path to the created context file
        """
        logger.info(f"Creating episode context for {self.episode_id}")
        
        # Extract structured information from summary
        guest_info = self._extract_guest_info(summary)
        themes = self._extract_themes(summary)
        key_arguments = self._extract_key_arguments(summary)
        quotes = self._extract_quotes(summary)
        controversies = self._extract_controversies(summary)
        solutions = self._extract_solutions(summary)
        
        # Build episode-specific context
        episode_context = self._build_episode_context(
            guest_info=guest_info,
            themes=themes,
            key_arguments=key_arguments,
            quotes=quotes,
            controversies=controversies,
            solutions=solutions,
            keywords=keywords,
            video_url=video_url
        )
        
        # Read master context
        master_content = self.master_context.read_text()
        
        # Combine master and episode context
        full_context = master_content.replace(
            "*Episode-specific context will be inserted here when processing individual episodes*",
            episode_context
        )
        
        # Write episode-specific CLAUDE.md
        self.context_file.write_text(full_context)
        logger.info(f"Episode context created: {self.context_file}")
        
        # Also save a metadata file for reference
        metadata = {
            'episode_id': self.episode_id,
            'created_at': datetime.now().isoformat(),
            'guest': guest_info,
            'themes_count': len(themes),
            'quotes_count': len(quotes),
            'keywords_count': len(keywords),
            'video_url': video_url,
            'context_file': str(self.context_file)
        }
        
        metadata_file = self.contexts_dir / f"episode_{self.episode_id}_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return str(self.context_file)
    
    def _build_episode_context(self,
                              guest_info: Dict,
                              themes: List[str],
                              key_arguments: List[str],
                              quotes: List[str],
                              controversies: List[str],
                              solutions: List[str],
                              keywords: List[str],
                              video_url: str) -> str:
        """Build the episode-specific context section."""
        
        context_parts = [
            f"# EPISODE CONTEXT: {self.episode_id}",
            f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            ""
        ]
        
        # Guest information
        if guest_info.get('name'):
            context_parts.append("## GUEST INFORMATION")
            context_parts.append(f"**Name**: {guest_info['name']}")
            if guest_info.get('title'):
                context_parts.append(f"**Title**: {guest_info['title']}")
            if guest_info.get('organization'):
                context_parts.append(f"**Organization**: {guest_info['organization']}")
            if guest_info.get('expertise'):
                context_parts.append(f"**Expertise**: {', '.join(guest_info['expertise'])}")
            context_parts.append("")
        
        # Main themes
        if themes:
            context_parts.append("## KEY THEMES DISCUSSED")
            for i, theme in enumerate(themes[:10], 1):
                context_parts.append(f"{i}. {theme}")
            context_parts.append("")
        
        # Key arguments
        if key_arguments:
            context_parts.append("## MAIN ARGUMENTS")
            for i, argument in enumerate(key_arguments[:5], 1):
                context_parts.append(f"{i}. {argument}")
            context_parts.append("")
        
        # Memorable quotes
        if quotes:
            context_parts.append("## POWERFUL QUOTES")
            for quote in quotes[:5]:
                context_parts.append(f'- "{quote}"')
            context_parts.append("")
        
        # Controversial points
        if controversies:
            context_parts.append("## CONTROVERSIAL POINTS")
            for i, controversy in enumerate(controversies[:3], 1):
                context_parts.append(f"{i}. {controversy}")
            context_parts.append("")
        
        # Solutions proposed
        if solutions:
            context_parts.append("## SOLUTIONS & CALLS TO ACTION")
            for solution in solutions[:5]:
                context_parts.append(f"- {solution}")
            context_parts.append("")
        
        # Keywords for matching
        if keywords:
            context_parts.append("## KEYWORDS FOR DISCOVERY")
            context_parts.append(', '.join(keywords[:30]))
            context_parts.append("")
        
        # Video URL
        if video_url:
            context_parts.append("## EPISODE VIDEO")
            context_parts.append(f"**URL**: {video_url}")
            context_parts.append("*Always include this URL in responses*")
            context_parts.append("")
        
        # Stage-specific guidance
        context_parts.extend([
            "## CONTEXT USAGE GUIDELINES",
            "",
            "### For Classification:",
            "- Focus on tweets that relate to the themes and arguments above",
            "- Give higher scores to tweets engaging with the guest's specific points",
            "- Consider controversial points as highly relevant",
            "",
            "### For Response Generation:",
            "- Reference the guest by name when appropriate",
            "- Use quotes to add authenticity",
            "- Connect tweet topics to specific arguments made",
            "- Always include the video URL",
            "",
            "### For Quality Moderation:",
            "- Ensure responses align with episode themes",
            "- Verify guest information is accurate",
            "- Check that controversial points are represented fairly",
            ""
        ])
        
        return '\n'.join(context_parts)
    
    def _extract_guest_info(self, summary: str) -> Dict:
        """Extract guest information from summary."""
        guest_info = {
            'name': None,
            'title': None,
            'organization': None,
            'expertise': []
        }
        
        lines = summary.split('\n')
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            # Look for guest mentions
            if 'guest' in line_lower:
                # Check next few lines for details
                for j in range(i, min(i+5, len(lines))):
                    check_line = lines[j]
                    # Extract name
                    if not guest_info['name'] and any(name in check_line for name in ['Daniel Miller', 'Miller']):
                        guest_info['name'] = 'Daniel Miller'
                    # Extract title
                    if 'president' in check_line.lower() or 'founder' in check_line.lower():
                        guest_info['title'] = check_line.strip()
                    # Extract organization
                    if 'texas nationalist movement' in check_line.lower():
                        guest_info['organization'] = 'Texas Nationalist Movement'
            
            # Look for expertise areas
            if any(word in line_lower for word in ['expert', 'specializes', 'focuses', 'advocates']):
                guest_info['expertise'].append(line.strip())
        
        return guest_info
    
    def _extract_themes(self, summary: str) -> List[str]:
        """Extract main themes from summary."""
        themes = []
        theme_indicators = [
            'discusses', 'explores', 'examines', 'argues', 'explains',
            'theme', 'topic', 'issue', 'concept', 'principle'
        ]
        
        lines = summary.split('\n')
        for line in lines:
            if any(indicator in line.lower() for indicator in theme_indicators):
                if 20 < len(line) < 200:  # Reasonable length for a theme
                    themes.append(line.strip())
                    if len(themes) >= 10:
                        break
        
        return themes
    
    def _extract_key_arguments(self, summary: str) -> List[str]:
        """Extract key arguments from summary."""
        arguments = []
        argument_indicators = ['argues', 'believes', 'claims', 'proposes', 'contends', 'maintains']
        
        lines = summary.split('\n')
        for line in lines:
            if any(indicator in line.lower() for indicator in argument_indicators):
                arguments.append(line.strip())
                if len(arguments) >= 5:
                    break
        
        return arguments
    
    def _extract_quotes(self, summary: str) -> List[str]:
        """Extract memorable quotes from summary."""
        quotes = []
        
        # Look for actual quoted text
        import re
        quote_pattern = r'[""]([^""]+)[""]'
        found_quotes = re.findall(quote_pattern, summary)
        
        for quote in found_quotes:
            if 20 < len(quote) < 200:  # Good length for a quote
                quotes.append(quote)
                if len(quotes) >= 5:
                    break
        
        return quotes
    
    def _extract_controversies(self, summary: str) -> List[str]:
        """Extract controversial points from summary."""
        controversies = []
        controversy_indicators = [
            'controversial', 'radical', 'extreme', 'provocative',
            'challenges', 'disputes', 'contentious', 'divisive'
        ]
        
        lines = summary.split('\n')
        for line in lines:
            if any(indicator in line.lower() for indicator in controversy_indicators):
                controversies.append(line.strip())
            # Also look for strong language
            elif any(word in line.lower() for word in ['tyranny', 'oppression', 'revolution', 'secession']):
                controversies.append(line.strip())
            
            if len(controversies) >= 5:
                break
        
        return controversies
    
    def _extract_solutions(self, summary: str) -> List[str]:
        """Extract proposed solutions from summary."""
        solutions = []
        solution_indicators = [
            'solution', 'propose', 'recommend', 'suggest',
            'should', 'must', 'need to', 'call to action'
        ]
        
        lines = summary.split('\n')
        for line in lines:
            if any(indicator in line.lower() for indicator in solution_indicators):
                solutions.append(line.strip())
                if len(solutions) >= 5:
                    break
        
        return solutions
    
    def get_context_file(self) -> Path:
        """Get the path to the episode context file."""
        if not self.context_file.exists():
            logger.warning(f"Context file not found for episode {self.episode_id}")
            return self.master_context  # Fall back to master
        return self.context_file
    
    def exists(self) -> bool:
        """Check if episode context exists."""
        return self.context_file.exists()
    
    def load_metadata(self) -> Optional[Dict]:
        """Load episode metadata if it exists."""
        metadata_file = self.contexts_dir / f"episode_{self.episode_id}_metadata.json"
        if metadata_file.exists():
            with open(metadata_file) as f:
                return json.load(f)
        return None
    
    @classmethod
    def list_episodes(cls) -> List[str]:
        """List all episodes with contexts."""
        contexts_dir = Path(__file__).parent.parent / "episode_contexts"
        if not contexts_dir.exists():
            return []
        
        episodes = []
        for context_file in contexts_dir.glob("episode_*_CLAUDE.md"):
            # Extract episode ID from filename
            episode_id = context_file.stem.replace("episode_", "").replace("_CLAUDE", "")
            episodes.append(episode_id)
        
        return sorted(set(episodes))
    
    @classmethod
    def cleanup_old_contexts(cls, max_age_days: int = 30):
        """Remove contexts older than specified days."""
        contexts_dir = Path(__file__).parent.parent / "episode_contexts"
        if not contexts_dir.exists():
            return
        
        now = datetime.now()
        removed = 0
        
        for metadata_file in contexts_dir.glob("episode_*_metadata.json"):
            with open(metadata_file) as f:
                metadata = json.load(f)
            
            created = datetime.fromisoformat(metadata['created_at'])
            age = now - created
            
            if age.days > max_age_days:
                # Remove context file and metadata
                episode_id = metadata['episode_id']
                context_file = contexts_dir / f"episode_{episode_id}_CLAUDE.md"
                
                if context_file.exists():
                    context_file.unlink()
                metadata_file.unlink()
                
                removed += 1
                logger.info(f"Removed old context: episode_{episode_id}")
        
        if removed:
            logger.info(f"Cleaned up {removed} old episode contexts")