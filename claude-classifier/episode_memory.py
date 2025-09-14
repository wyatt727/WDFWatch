#!/usr/bin/env python3
"""
Episode Memory System - Maintains persistent context for each episode across all pipeline stages.
Each episode gets its own memory file that is created during summarization and reused throughout.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class EpisodeMemory:
    """
    Persistent memory for each episode that maintains context across pipeline stages.
    
    Memory is generated ONCE during summarization and then reused for:
    - Tweet classification (lightweight context)
    - Response generation (rich context)  
    - Quality moderation (evaluation context)
    """
    
    def __init__(self, episode_id: str = None):
        """
        Initialize episode memory.
        
        Args:
            episode_id: Unique identifier for the episode (timestamp or hash)
        """
        self.episode_id = episode_id or self._generate_episode_id()
        self.memory_dir = Path(__file__).parent.parent / "episode_memories"
        self.memory_dir.mkdir(exist_ok=True)
        self.memory_file = self.memory_dir / f"episode_{self.episode_id}.json"
        self.memory = self._load_or_initialize()
    
    def _generate_episode_id(self) -> str:
        """Generate unique episode ID from transcript if not provided."""
        transcript_path = Path(__file__).parent.parent / "transcripts" / "latest.txt"
        if transcript_path.exists():
            content = transcript_path.read_text()
            return hashlib.md5(content.encode()).hexdigest()[:8]
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def _load_or_initialize(self) -> Dict:
        """Load existing memory or create new one."""
        if self.memory_file.exists():
            logger.info(f"Loading existing memory for episode {self.episode_id}")
            with open(self.memory_file) as f:
                return json.load(f)
        else:
            logger.info(f"Initializing new memory for episode {self.episode_id}")
            return {
                'episode_id': self.episode_id,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'stages_completed': [],
                'guest': {},
                'themes': [],
                'quotes': [],
                'keywords': [],
                'controversies': [],
                'key_arguments': [],
                'solutions_proposed': [],
                'video_url': '',
                'summary_condensed': '',
                'classification_context': '',
                'response_context': ''
            }
    
    def save(self):
        """Persist memory to disk."""
        self.memory['updated_at'] = datetime.now().isoformat()
        with open(self.memory_file, 'w') as f:
            json.dump(self.memory, f, indent=2)
        logger.info(f"Saved memory for episode {self.episode_id}")
    
    # ======================
    # STAGE 1: SUMMARIZATION
    # ======================
    
    def store_summary_analysis(self, summary: str, keywords: List[str], video_url: str = None):
        """
        Store analysis from summarization stage.
        This is called ONCE at the beginning of the pipeline.
        
        Args:
            summary: Full episode summary
            keywords: Extracted keywords for tweet discovery
            video_url: YouTube URL for the episode
        """
        logger.info(f"Storing summary analysis for episode {self.episode_id}")
        
        # Extract guest information
        self.memory['guest'] = self._extract_guest_info(summary)
        
        # Extract themes and key points
        self.memory['themes'] = self._extract_themes(summary)
        self.memory['key_arguments'] = self._extract_key_arguments(summary)
        self.memory['solutions_proposed'] = self._extract_solutions(summary)
        
        # Extract memorable quotes
        self.memory['quotes'] = self._extract_quotes(summary)
        
        # Identify controversial points
        self.memory['controversies'] = self._extract_controversies(summary)
        
        # Store keywords and URL
        self.memory['keywords'] = keywords[:30]  # Top 30 keywords
        if video_url:
            self.memory['video_url'] = video_url
        
        # Create condensed summary for context
        self.memory['summary_condensed'] = self._create_condensed_summary(summary)
        
        # Pre-generate contexts for other stages
        self._generate_classification_context()
        self._generate_response_context()
        
        # Mark stage complete
        if 'summarization' not in self.memory['stages_completed']:
            self.memory['stages_completed'].append('summarization')
        
        self.save()
    
    def _extract_guest_info(self, summary: str) -> Dict:
        """Extract guest information from summary."""
        guest_info = {
            'name': 'Unknown Guest',
            'title': '',
            'organization': '',
            'expertise': []
        }
        
        lines = summary.lower().split('\n')
        for i, line in enumerate(lines):
            if 'guest' in line or any(name in line for name in ['daniel', 'miller', 'becker']):
                # Look at surrounding lines for context
                context_lines = lines[max(0, i-2):min(len(lines), i+3)]
                for ctx_line in context_lines:
                    # Extract name patterns
                    if 'daniel miller' in ctx_line:
                        guest_info['name'] = 'Daniel Miller'
                    # Extract titles/orgs
                    if 'president' in ctx_line or 'founder' in ctx_line:
                        guest_info['title'] = ctx_line.strip()
                    if 'texas nationalist movement' in ctx_line:
                        guest_info['organization'] = 'Texas Nationalist Movement'
        
        return guest_info
    
    def _extract_themes(self, summary: str) -> List[str]:
        """Extract main themes discussed."""
        themes = []
        theme_keywords = [
            'federalism', 'state sovereignty', 'secession', 'nullification',
            'constitutional', 'liberty', 'freedom', 'government overreach',
            'state rights', 'tenth amendment', 'national divorce'
        ]
        
        for keyword in theme_keywords:
            if keyword in summary.lower():
                themes.append(keyword.title())
        
        # Also look for specific discussion points
        lines = summary.split('\n')
        for line in lines:
            if any(word in line.lower() for word in ['discusses', 'explores', 'argues', 'explains']):
                if len(line) < 200:  # Reasonable length for a theme
                    themes.append(line.strip())
                    if len(themes) >= 10:
                        break
        
        return themes[:10]  # Top 10 themes
    
    def _extract_key_arguments(self, summary: str) -> List[str]:
        """Extract key arguments made in the episode."""
        arguments = []
        argument_indicators = ['argues', 'believes', 'proposes', 'suggests', 'claims']
        
        lines = summary.split('\n')
        for line in lines:
            if any(indicator in line.lower() for indicator in argument_indicators):
                arguments.append(line.strip())
                if len(arguments) >= 5:
                    break
        
        return arguments
    
    def _extract_solutions(self, summary: str) -> List[str]:
        """Extract proposed solutions or calls to action."""
        solutions = []
        solution_indicators = ['solution', 'propose', 'recommend', 'should', 'must', 'need to']
        
        lines = summary.split('\n')
        for line in lines:
            if any(indicator in line.lower() for indicator in solution_indicators):
                solutions.append(line.strip())
                if len(solutions) >= 5:
                    break
        
        return solutions
    
    def _extract_quotes(self, summary: str) -> List[str]:
        """Extract memorable quotes from the summary."""
        quotes = []
        lines = summary.split('\n')
        
        for line in lines:
            # Look for actual quotes
            if '"' in line or '"' in line or '"' in line:
                quote = line.strip()
                if 20 < len(quote) < 200:  # Reasonable quote length
                    quotes.append(quote)
            # Look for powerful statements
            elif any(word in line.lower() for word in ['never', 'always', 'must', 'critical', 'essential']):
                if len(line) < 150:
                    quotes.append(line.strip())
            
            if len(quotes) >= 5:
                break
        
        return quotes
    
    def _extract_controversies(self, summary: str) -> List[str]:
        """Extract controversial or provocative points."""
        controversies = []
        controversy_indicators = [
            'controversial', 'radical', 'extreme', 'provocative',
            'challenges', 'disputes', 'rejects', 'opposes'
        ]
        
        lines = summary.split('\n')
        for line in lines:
            if any(indicator in line.lower() for indicator in controversy_indicators):
                controversies.append(line.strip())
            # Also look for strong language
            elif any(word in line.lower() for word in ['tyranny', 'oppression', 'revolution', 'rebellion']):
                controversies.append(line.strip())
            
            if len(controversies) >= 5:
                break
        
        return controversies
    
    def _create_condensed_summary(self, summary: str) -> str:
        """Create a condensed version of the summary."""
        # Take first paragraph and key points
        paragraphs = summary.split('\n\n')
        condensed = paragraphs[0] if paragraphs else summary[:500]
        
        # Add most important points
        if self.memory['key_arguments']:
            condensed += f"\n\nKey Argument: {self.memory['key_arguments'][0]}"
        
        if self.memory['controversies']:
            condensed += f"\n\nControversial Point: {self.memory['controversies'][0]}"
        
        return condensed[:1000]  # Max 1000 chars
    
    def _generate_classification_context(self):
        """Pre-generate context for classification stage."""
        context_parts = []
        
        # Guest info
        if self.memory['guest'].get('name'):
            context_parts.append(f"Guest: {self.memory['guest']['name']}")
            if self.memory['guest'].get('organization'):
                context_parts.append(f"Organization: {self.memory['guest']['organization']}")
        
        # Top themes
        if self.memory['themes']:
            context_parts.append(f"Main Topics: {', '.join(self.memory['themes'][:5])}")
        
        # Key controversy
        if self.memory['controversies']:
            context_parts.append(f"Hot Topic: {self.memory['controversies'][0][:100]}")
        
        # Keywords for matching
        if self.memory['keywords']:
            context_parts.append(f"Keywords: {', '.join(self.memory['keywords'][:10])}")
        
        self.memory['classification_context'] = '\n'.join(context_parts)
    
    def _generate_response_context(self):
        """Pre-generate context for response generation."""
        context_parts = []
        
        # Guest with title
        if self.memory['guest'].get('name'):
            guest_str = self.memory['guest']['name']
            if self.memory['guest'].get('title'):
                guest_str += f" ({self.memory['guest']['title']})"
            context_parts.append(f"Guest: {guest_str}")
        
        # Best quote
        if self.memory['quotes']:
            context_parts.append(f'Key Quote: "{self.memory["quotes"][0]}"')
        
        # Main argument
        if self.memory['key_arguments']:
            context_parts.append(f"Main Point: {self.memory['key_arguments'][0][:150]}")
        
        # Solution if any
        if self.memory['solutions_proposed']:
            context_parts.append(f"Solution: {self.memory['solutions_proposed'][0][:100]}")
        
        # Video URL
        if self.memory['video_url']:
            context_parts.append(f"Episode: {self.memory['video_url']}")
        
        self.memory['response_context'] = '\n'.join(context_parts)
    
    # ============================
    # CONTEXT RETRIEVAL METHODS
    # ============================
    
    def get_classification_context(self) -> str:
        """
        Get lightweight context for tweet classification.
        Used by classification stage.
        """
        if 'summarization' not in self.memory['stages_completed']:
            logger.warning("Summarization not complete, returning empty context")
            return ""
        
        return self.memory.get('classification_context', '')
    
    def get_response_context(self) -> str:
        """
        Get rich context for response generation.
        Used by response generation stage.
        """
        if 'summarization' not in self.memory['stages_completed']:
            logger.warning("Summarization not complete, returning empty context")
            return ""
        
        return self.memory.get('response_context', '')
    
    def get_moderation_context(self) -> str:
        """
        Get context for quality moderation.
        Used by moderation stage.
        """
        return f"""Episode: {self.memory['episode_id']}
Guest: {self.memory['guest'].get('name', 'Unknown')}
Themes: {', '.join(self.memory['themes'][:3])}
Video: {self.memory['video_url']}"""
    
    # ============================
    # UTILITY METHODS
    # ============================
    
    def is_valid(self, max_age_hours: int = 48) -> bool:
        """Check if memory is still fresh."""
        if not self.memory_file.exists():
            return False
        
        created = datetime.fromisoformat(self.memory['created_at'])
        age = datetime.now() - created
        return age.total_seconds() < (max_age_hours * 3600)
    
    def mark_stage_complete(self, stage: str):
        """Mark a pipeline stage as complete."""
        if stage not in self.memory['stages_completed']:
            self.memory['stages_completed'].append(stage)
            self.save()
    
    def get_stats(self) -> Dict:
        """Get memory statistics."""
        return {
            'episode_id': self.episode_id,
            'created': self.memory['created_at'],
            'updated': self.memory['updated_at'],
            'stages_completed': self.memory['stages_completed'],
            'has_guest': bool(self.memory['guest'].get('name')),
            'theme_count': len(self.memory['themes']),
            'keyword_count': len(self.memory['keywords']),
            'quote_count': len(self.memory['quotes'])
        }
    
    @classmethod
    def list_episodes(cls) -> List[str]:
        """List all episodes with memories."""
        memory_dir = Path(__file__).parent.parent / "episode_memories"
        if not memory_dir.exists():
            return []
        
        episodes = []
        for memory_file in memory_dir.glob("episode_*.json"):
            episode_id = memory_file.stem.replace("episode_", "")
            episodes.append(episode_id)
        
        return sorted(episodes)
    
    @classmethod
    def cleanup_old_memories(cls, max_age_days: int = 30):
        """Remove memories older than specified days."""
        memory_dir = Path(__file__).parent.parent / "episode_memories"
        if not memory_dir.exists():
            return
        
        now = datetime.now()
        removed = 0
        
        for memory_file in memory_dir.glob("episode_*.json"):
            with open(memory_file) as f:
                memory = json.load(f)
            
            created = datetime.fromisoformat(memory['created_at'])
            age = now - created
            
            if age.days > max_age_days:
                memory_file.unlink()
                removed += 1
                logger.info(f"Removed old memory: {memory_file.name}")
        
        if removed:
            logger.info(f"Cleaned up {removed} old episode memories")


# Example usage for testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Test memory creation
        memory = EpisodeMemory("test_episode_001")
        
        # Simulate summarization stage
        test_summary = """
        In this episode, Daniel Miller from the Texas Nationalist Movement discusses 
        the growing movement for Texas independence. He argues that federal overreach 
        has reached a breaking point and proposes peaceful secession as the solution.
        
        Miller explains that "The federal government has become what the founders feared most - 
        an all-powerful central authority that ignores constitutional limits."
        
        The conversation explores controversial topics like state nullification and the 
        legal framework for peaceful separation. Miller believes that Texas has both the 
        moral and legal right to withdraw from the union.
        
        Key solutions proposed include a statewide referendum on independence and 
        establishing parallel state institutions to replace federal agencies.
        """
        
        test_keywords = ["Texas independence", "secession", "Daniel Miller", "state sovereignty"]
        test_url = "https://youtube.com/watch?v=test123"
        
        memory.store_summary_analysis(test_summary, test_keywords, test_url)
        
        print("Episode Memory Created!")
        print(f"Classification Context:\n{memory.get_classification_context()}\n")
        print(f"Response Context:\n{memory.get_response_context()}\n")
        print(f"Stats: {json.dumps(memory.get_stats(), indent=2)}")
    
    elif len(sys.argv) > 1 and sys.argv[1] == "list":
        # List all episodes
        episodes = EpisodeMemory.list_episodes()
        print(f"Found {len(episodes)} episodes with memories:")
        for ep in episodes:
            print(f"  - {ep}")
    
    elif len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        # Cleanup old memories
        EpisodeMemory.cleanup_old_memories(max_age_days=30)
    
    else:
        print("Usage:")
        print("  python episode_memory.py test      # Create test memory")
        print("  python episode_memory.py list      # List all episodes")
        print("  python episode_memory.py cleanup   # Remove old memories")