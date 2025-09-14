#!/usr/bin/env python3
"""
Summarization stage - Generates comprehensive summary and creates episode context
"""

import logging
import hashlib
import os
import sys
from pathlib import Path
from typing import Dict, List
import json
from datetime import datetime

from core import UnifiedInterface
from core.episode_manager import EpisodeManager

# Add web scripts to path for web_bridge
web_scripts_path = Path(__file__).parent.parent.parent / "web" / "scripts"
if web_scripts_path.exists():
    sys.path.insert(0, str(web_scripts_path))
    try:
        from web_bridge import WebUIBridge
        HAS_WEB_BRIDGE = True
    except ImportError:
        HAS_WEB_BRIDGE = False
else:
    HAS_WEB_BRIDGE = False

logger = logging.getLogger(__name__)

class Summarizer:
    """
    Generates episode summaries and creates episode-specific CLAUDE.md files.
    """
    
    def __init__(self, claude: UnifiedInterface):
        """
        Initialize summarizer.
        
        Args:
            claude: Claude interface instance
        """
        self.claude = claude
        logger.info("Summarizer initialized")
    
    def summarize(self, 
                 transcript: str,
                 podcast_overview: str,
                 episode_id: str = None,
                 video_url: str = None) -> Dict:
        """
        Generate comprehensive summary and create episode context.
        
        Args:
            transcript: Full episode transcript
            podcast_overview: General podcast description
            episode_id: Optional episode identifier
            video_url: YouTube URL for the episode
            
        Returns:
            Dictionary with summary, keywords, and context info
        """
        # Initialize episode manager with correct directory
        episodes_dir = Path(__file__).parent.parent / "episodes"
        episode_mgr = EpisodeManager(episodes_dir=str(episodes_dir))
        
        # Create episode directory structure
        if not episode_id:
            episode_info = episode_mgr.create_episode(transcript, video_url=video_url)
            episode_id = episode_info['episode_id']
        else:
            # Check if episode exists, create if not
            if not episode_mgr.get_episode_dir(episode_id):
                episode_info = episode_mgr.create_episode(transcript, episode_id, video_url)
        
        # Store episode_id for use in other methods
        self.current_episode_id = episode_id
        
        logger.info(f"Summarizing episode {episode_id}")
        
        # Get episode directory and create placeholder files
        episode_dir = episode_mgr.get_episode_dir(episode_id)
        
        # Create placeholder summary.md file BEFORE Claude call
        summary_file = episode_dir / "summary.md"
        summary_file.write_text("# Episode Summary\n\n*Generating summary with Claude API...*\n\nThis file will be updated with the full episode summary once generation is complete.")
        logger.info(f"Created placeholder summary at {summary_file}")
        
        # Create placeholder keywords.json file
        keywords_file = episode_dir / "keywords.json"
        with open(keywords_file, 'w') as f:
            json.dump(["generating", "keywords", "please", "wait"], f, indent=2)
        logger.info(f"Created placeholder keywords at {keywords_file}")
        
        # DO NOT set episode context for summarization - we're creating it from scratch
        # The placeholder summary.md should NOT be used as context
        # self.claude.set_episode_context(episode_id)  # Removed - would load existing context
        self.claude.set_episode_context(None)  # Explicitly clear any episode context
        
        # Save transcript to episode directory if not already there
        transcript_file = episode_dir / "transcript.txt"
        if not transcript_file.exists():
            transcript_file.write_text(transcript)
            logger.info(f"Saved transcript to {transcript_file}")
        
        # Build simple summarization prompt with @ reference to transcript file
        # Include video URL if provided so it becomes part of the summary
        # IMPORTANT: If video_url starts with @, we need to handle it specially
        # to prevent Claude CLI from interpreting it as a file reference
        if video_url:
            # If it's a Twitter handle, remove @ for the prompt to avoid file reference confusion
            if video_url.startswith('@'):
                # Store Twitter handle without @ to prevent file interpretation
                safe_video_url = f"Twitter/X: {video_url[1:]}"  # Remove @ and clarify it's Twitter
                logger.info(f"Converted Twitter handle {video_url} to {safe_video_url} to avoid file reference")
            else:
                safe_video_url = video_url
            
            prompt = f"""Stay in your role and output in the exact format shown in CLAUDE.md.

VIDEO URL: {safe_video_url}

Summarize this transcript: @{transcript_file}"""
        else:
            prompt = f"""Stay in your role and output in the exact format shown in CLAUDE.md.

Summarize this transcript: @{transcript_file}"""
        
        # Generate summary using Claude with better error handling
        # IMPORTANT: Don't pass episode_id to avoid loading placeholder as context
        try:
            logger.info(f"Starting summary generation for episode {episode_id}")
            logger.info(f"Transcript file size: {transcript_file.stat().st_size} bytes")
            logger.info(f"Prompt length: {len(prompt)} characters")
            logger.debug(f"Full prompt being sent:\n{prompt[:500]}...")  # Log first 500 chars of prompt
            
            summary_text = self.claude.call(
                prompt=prompt,
                mode='summarize',
                episode_id=None,  # Don't use episode context for initial summarization
                use_cache=False  # Don't cache summaries
            )
            
            if not summary_text or len(summary_text) < 100:
                logger.error(f"Summary generation returned insufficient content: {len(summary_text)} characters")
                raise ValueError(f"Summary too short: {len(summary_text)} characters")
                
            logger.info(f"Summary generated successfully: {len(summary_text)} characters")
            
        except Exception as e:
            logger.error(f"Summary generation failed: {e}", exc_info=True)
            # Save error information
            error_file = episode_dir / "summary_error.log"
            error_file.write_text(f"Summary generation failed at {datetime.now()}\nError: {e}\n\nPrompt was:\n{prompt[:1000]}...")
            
            # Create a minimal summary to allow pipeline to continue
            summary_text = f"""# Episode Summary
            
**Error**: Summary generation failed. Please check logs for details.

Error message: {e}

This is a placeholder summary to allow the pipeline to continue.
The transcript has been saved and can be manually summarized later.
"""
            logger.warning("Using placeholder summary to allow pipeline to continue")
        
        # Save summary immediately to prevent loss during keyword extraction
        summary_file = episode_dir / "summary.md"
        summary_file.write_text(summary_text)
        logger.info(f"Saved summary to {summary_file}")
        
        # Extract keywords separately if needed
        keywords = self._extract_keywords(summary_text, transcript)
        
        # Update episode's CLAUDE.md with context
        context_file = episode_mgr.update_episode_context(
            episode_id=episode_id,
            summary=summary_text,
            keywords=keywords,
            video_url=video_url
        )
        
        result = {
            'episode_id': episode_id,
            'episode_dir': str(episode_dir),
            'summary': summary_text,
            'keywords': keywords,
            'video_url': video_url,
            'context_file': context_file,
            'context_created': True
        }
        
        # Save outputs to episode directory
        self._save_outputs(result, episode_dir)
        
        logger.info(f"Summary complete for episode {episode_id}")
        logger.info(f"Episode context updated: {context_file}")
        
        return result
    
    def _extract_keywords(self, summary: str, transcript: str = None) -> List[str]:
        """
        Extract keywords from summary or generate them.
        
        Args:
            summary: Generated summary
            transcript: Original transcript
            
        Returns:
            List of keywords
        """
        keywords = []
        
        # Look for keywords section in summary - improved parsing
        lines = summary.split('\n')
        in_keywords_section = False
        keywords_indicators = ['keywords:', 'key terms:', 'search terms:', 'tags:', '## keywords', '### keywords']
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Check if we're entering a keywords section
            if any(indicator in line_lower for indicator in keywords_indicators):
                in_keywords_section = True
                # Check if keywords are on the same line (e.g., "Keywords: term1, term2, term3")
                if ':' in line:
                    potential_keywords = line.split(':', 1)[1].strip()
                    if potential_keywords and ',' in potential_keywords:
                        keywords.extend([k.strip().strip('#').strip('"').strip("'") 
                                       for k in potential_keywords.split(',') 
                                       if k.strip()])
                continue
            
            if in_keywords_section and line.strip():
                # Stop at next section header
                if line.startswith('#') and not line.lower().startswith('### keyword'):
                    break
                    
                # Handle various keyword formats
                clean_line = line.strip()
                
                # Remove common list markers
                for marker in ['- ', '* ', '• ', '+ ', '1. ', '2. ', '3. ', '4. ', '5. ']:
                    if clean_line.startswith(marker):
                        clean_line = clean_line[len(marker):]
                        break
                
                # Handle comma-separated keywords on a single line
                if ',' in clean_line:
                    potential_keywords = [k.strip().strip('#').strip('"').strip("'") 
                                        for k in clean_line.split(',')]
                    keywords.extend([k for k in potential_keywords if k and len(k) > 2])
                # Handle individual keyword lines
                elif clean_line and not clean_line.startswith('#'):
                    # Clean the keyword
                    clean_keyword = clean_line.strip('#').strip('"').strip("'").strip()
                    if clean_keyword and len(clean_keyword) > 2:
                        keywords.append(clean_keyword)
        
        # Also try to extract from lines that look like keyword lists anywhere in the summary
        if len(keywords) < 10:
            for line in lines:
                # Look for lines with multiple hashtags or comma-separated terms
                if line.count('#') > 2 or (line.count(',') > 2 and len(line) < 200):
                    # Extract hashtags
                    import re
                    hashtags = re.findall(r'#\w+', line)
                    keywords.extend([tag.strip('#') for tag in hashtags])
                    
                    # Extract comma-separated terms if not hashtags
                    if not hashtags and ',' in line:
                        terms = [t.strip().strip('#').strip('"').strip("'") 
                                for t in line.split(',')]
                        keywords.extend([t for t in terms if t and len(t) > 2 and len(t) < 50])
        
        # Clean and deduplicate keywords
        cleaned_keywords = []
        seen = set()
        for k in keywords:
            # Remove any remaining special characters at start/end
            clean_k = k.strip().strip('#').strip('@').strip('"').strip("'").strip()
            # Skip if too short, too long, or duplicate
            if clean_k and len(clean_k) > 2 and len(clean_k) < 50 and clean_k.lower() not in seen:
                cleaned_keywords.append(clean_k)
                seen.add(clean_k.lower())
        
        logger.info(f"Extracted {len(cleaned_keywords)} keywords from summary")
        
        # If we didn't find enough keywords, generate them separately
        if len(cleaned_keywords) < 15:
            logger.info(f"Only found {len(cleaned_keywords)} keywords, generating more...")
            
            prompt = f"""Based on this episode summary, generate 60-70 keywords for finding relevant tweets.

Include:
- Guest names and organizations  
- Key political terms and concepts discussed
- Trending hashtags if relevant
- Both supportive and opposition terms
- Variations with and without hashtags
- Specific policy areas mentioned
- Constitutional concepts discussed
- Current events referenced

Summary:
{summary[:3000]}

Output keywords as a comma-separated list on a single line (no other text):"""
            
            # Don't pass episode_id to avoid loading placeholder as context
            response = self.claude.call(prompt, mode='summarize', episode_id=None)
            
            # Parse the response - expecting comma-separated keywords
            for line in response.split('\n'):
                line = line.strip()
                if line and ',' in line:
                    new_keywords = [k.strip().strip('#').strip('"').strip("'") 
                                  for k in line.split(',')]
                    cleaned_keywords.extend([k for k in new_keywords 
                                           if k and len(k) > 2 and len(k) < 50 
                                           and k.lower() not in seen])
                    for k in new_keywords:
                        if k and len(k) > 2:
                            seen.add(k.lower())
        
        # Ensure we have a good mix and reasonable count
        final_keywords = cleaned_keywords[:70] if len(cleaned_keywords) > 70 else cleaned_keywords
        
        # If we still have very few keywords, add some defaults based on common themes
        if len(final_keywords) < 10:
            logger.warning(f"Still only {len(final_keywords)} keywords, adding defaults")
            defaults = [
                "federalism", "states rights", "constitution", "liberty",
                "sovereignty", "WDF", "WarDivorceFederalism", "RickBecker",
                "podcast", "politics", "government", "freedom"
            ]
            for d in defaults:
                if d.lower() not in seen:
                    final_keywords.append(d)
        
        logger.info(f"Final keyword count: {len(final_keywords)}")
        return final_keywords
    
    def _save_outputs(self, result: Dict, episode_dir: Path):
        """
        Save summary and keywords to episode directory.
        
        Args:
            result: Summary result dictionary
            episode_dir: Path to episode directory
        """
        # Save summary to episode directory (may already exist from earlier save)
        summary_file = episode_dir / "summary.md"
        if not summary_file.exists() or summary_file.read_text() != result['summary']:
            summary_file.write_text(result['summary'])
            logger.debug(f"Updated summary at {summary_file}")
        else:
            logger.debug(f"Summary already saved at {summary_file}")
        
        # Save keywords
        keywords_file = episode_dir / "keywords.json"
        with open(keywords_file, 'w') as f:
            json.dump(result['keywords'], f, indent=2)
        logger.debug(f"Saved keywords to {keywords_file}")
        
        # Also save to transcripts dir for backward compatibility
        transcripts_dir = Path(__file__).parent.parent.parent / "transcripts"
        if transcripts_dir.exists():
            (transcripts_dir / "summary.md").write_text(result['summary'])
            with open(transcripts_dir / "keywords.json", 'w') as f:
                json.dump(result['keywords'], f, indent=2)
        
        # Save keywords to database if web bridge is available
        if HAS_WEB_BRIDGE and os.getenv("WDF_WEB_MODE") == "true":
            try:
                episode_id_str = result.get('episode_id', '')
                if episode_id_str:
                    bridge = WebUIBridge()
                    bridge.save_keywords_to_database(
                        episode_dir=episode_id_str,
                        keywords=result['keywords'],
                        source='claude'
                    )
                    bridge.close()
                    logger.info(f"Saved {len(result['keywords'])} keywords to database for episode {episode_id_str}")
                else:
                    logger.warning("No episode_id available for saving keywords to database")
            except Exception as e:
                logger.error(f"Failed to save keywords to database: {e}")
                # Don't fail the pipeline if database save fails