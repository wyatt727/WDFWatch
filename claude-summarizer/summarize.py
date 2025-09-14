#!/usr/bin/env python3
"""
Claude-based transcript summarization with episode memory generation.
This replaces the Gemini summarizer and creates persistent episode memory.
"""

import json
import subprocess
import sys
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import argparse
import logging
import re

# Add claude-classifier to path for episode memory
sys.path.append(str(Path(__file__).parent.parent / "claude-classifier"))
from episode_memory import EpisodeMemory

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Path configuration
SCRIPT_DIR = Path(__file__).parent
PARENT_DIR = SCRIPT_DIR.parent
CLAUDE_MD = SCRIPT_DIR / "CLAUDE.md"

class ClaudeSummarizer:
    """Generate episode summaries and create episode memories."""
    
    def __init__(self, episode_id: str = None):
        """Initialize summarizer with episode ID."""
        self.episode_id = episode_id
        
        # Verify CLAUDE.md exists
        if not CLAUDE_MD.exists():
            raise FileNotFoundError(f"CLAUDE.md not found at {CLAUDE_MD}")
    
    def summarize_transcript(self, transcript: str, podcast_overview: str, 
                            video_url: str = None) -> Dict:
        """
        Generate comprehensive summary and create episode memory.
        
        Args:
            transcript: Full episode transcript
            podcast_overview: General podcast description
            video_url: YouTube URL for the episode
            
        Returns:
            Dictionary with summary, keywords, and memory stats
        """
        logger.info(f"Starting summarization for episode {self.episode_id}")
        
        # Build prompt
        prompt = f"""Analyze this WDF Podcast episode and create a comprehensive summary following the analysis framework.

PODCAST OVERVIEW:
{podcast_overview}

EPISODE TRANSCRIPT:
{transcript}

Generate a detailed analysis with all required sections as specified in the framework."""
        
        # Call Claude
        logger.info("Calling Claude for summarization...")
        start_time = time.time()
        summary_text = self._call_claude(prompt)
        elapsed_time = time.time() - start_time
        logger.info(f"Summarization took {elapsed_time:.2f} seconds")
        
        # Parse the summary
        parsed = self._parse_summary(summary_text)
        
        # Extract keywords separately if not found
        if not parsed['keywords']:
            parsed['keywords'] = self._extract_keywords(summary_text, transcript)
        
        # Generate episode ID if not provided
        if not self.episode_id:
            self.episode_id = hashlib.md5(transcript.encode()).hexdigest()[:8]
        
        # Create episode memory
        logger.info(f"Creating episode memory for {self.episode_id}")
        memory = EpisodeMemory(self.episode_id)
        memory.store_summary_analysis(
            summary=summary_text,
            keywords=parsed['keywords'],
            video_url=video_url
        )
        
        # Prepare output
        result = {
            'episode_id': self.episode_id,
            'summary': summary_text,
            'keywords': parsed['keywords'],
            'guest': parsed.get('guest', {}),
            'themes': parsed.get('themes', []),
            'quotes': parsed.get('quotes', []),
            'controversies': parsed.get('controversies', []),
            'solutions': parsed.get('solutions', []),
            'video_url': video_url,
            'summarization_time': elapsed_time,
            'memory_created': True,
            'memory_stats': memory.get_stats()
        }
        
        return result
    
    def _call_claude(self, prompt: str) -> str:
        """Call Claude CLI with the given prompt."""
        try:
            # Write prompt to temp file
            temp_prompt = SCRIPT_DIR / ".temp_prompt.txt"
            temp_prompt.write_text(prompt)
            
            # Build command
            cmd = [
                "claude",
                "--model", "sonnet",
                "--print",
                f"@{CLAUDE_MD}",
                f"@{temp_prompt}"
            ]
            
            # Execute with longer timeout for summarization
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=SCRIPT_DIR,
                timeout=120  # 2 minute timeout
            )
            
            # Clean up temp file
            temp_prompt.unlink(missing_ok=True)
            
            if result.returncode != 0:
                logger.error(f"Claude CLI error: {result.stderr}")
                return ""
            
            return result.stdout.strip()
            
        except subprocess.TimeoutExpired:
            logger.error("Claude summarization timed out")
            return ""
        except Exception as e:
            logger.error(f"Error calling Claude: {e}")
            return ""
    
    def _parse_summary(self, summary_text: str) -> Dict:
        """Parse structured information from the summary."""
        parsed = {
            'guest': {},
            'themes': [],
            'quotes': [],
            'controversies': [],
            'solutions': [],
            'keywords': []
        }
        
        lines = summary_text.split('\n')
        current_section = None
        
        for line in lines:
            line_lower = line.lower()
            
            # Detect sections
            if 'guest profile' in line_lower:
                current_section = 'guest'
            elif 'core themes' in line_lower or 'themes discussed' in line_lower:
                current_section = 'themes'
            elif 'memorable quotes' in line_lower:
                current_section = 'quotes'
            elif 'controversial points' in line_lower:
                current_section = 'controversies'
            elif 'solutions' in line_lower:
                current_section = 'solutions'
            elif 'keywords' in line_lower:
                current_section = 'keywords'
            
            # Parse content based on section
            elif current_section and line.strip():
                if current_section == 'guest' and not line.startswith('#'):
                    # Extract guest info
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().lower().replace(' ', '_')
                        parsed['guest'][key] = value.strip()
                
                elif current_section == 'themes':
                    if line.startswith(('- ', '* ', '1.', '2.', '3.')):
                        theme = re.sub(r'^[-*\d.]\s*', '', line).strip()
                        if theme:
                            parsed['themes'].append(theme)
                
                elif current_section == 'quotes':
                    if '"' in line or '"' in line or '"' in line:
                        # Extract quoted text
                        quote_match = re.search(r'[""]([^""]+)[""]', line)
                        if quote_match:
                            parsed['quotes'].append(quote_match.group(1))
                
                elif current_section == 'controversies':
                    if line.startswith(('- ', '* ', '1.', '2.', '3.')):
                        controversy = re.sub(r'^[-*\d.]\s*', '', line).strip()
                        if controversy:
                            parsed['controversies'].append(controversy)
                
                elif current_section == 'solutions':
                    if line.startswith(('- ', '* ', '1.', '2.', '3.')):
                        solution = re.sub(r'^[-*\d.]\s*', '', line).strip()
                        if solution:
                            parsed['solutions'].append(solution)
                
                elif current_section == 'keywords':
                    # Parse comma-separated keywords
                    if ',' in line:
                        keywords = [k.strip() for k in line.split(',')]
                        parsed['keywords'].extend(keywords)
        
        return parsed
    
    def _extract_keywords(self, summary: str, transcript: str) -> List[str]:
        """Extract keywords if not found in structured summary."""
        logger.info("Extracting keywords separately...")
        
        prompt = f"""Based on this episode summary and transcript, generate 25-30 keywords for finding relevant tweets.

Include:
- Guest name and organization
- Key political terms discussed
- Trending hashtags if relevant
- Both supportive and opposition terms
- Variations with and without hashtags

Summary excerpt:
{summary[:1000]}

Output keywords as a comma-separated list:"""
        
        response = self._call_claude(prompt)
        
        # Parse keywords
        keywords = []
        if response:
            # Split by comma or newline
            for line in response.split('\n'):
                if ',' in line:
                    keywords.extend([k.strip() for k in line.split(',')])
                elif line.strip() and not line.startswith('#'):
                    keywords.append(line.strip())
        
        # Ensure we have at least some keywords
        if not keywords:
            keywords = [
                "federalism", "state sovereignty", "constitutional",
                "liberty", "freedom", "government overreach",
                "tenth amendment", "state rights", "WDF podcast"
            ]
        
        return keywords[:30]


def process_transcript(
    transcript_file: Path,
    output_dir: Path,
    episode_id: str = None,
    video_url: str = None
) -> Dict:
    """
    Process a transcript file and generate summary with memory.
    
    Args:
        transcript_file: Path to transcript file
        output_dir: Directory for output files
        episode_id: Optional episode identifier
        video_url: Optional YouTube URL
        
    Returns:
        Summary results with memory stats
    """
    # Load transcript
    logger.info(f"Loading transcript from {transcript_file}")
    transcript = transcript_file.read_text()
    
    # Load podcast overview
    overview_file = transcript_file.parent / "podcast_overview.txt"
    if overview_file.exists():
        overview = overview_file.read_text()
    else:
        overview = """The War, Divorce, or Federalism podcast explores America's future 
        in the context of political division. Host Rick Becker examines whether the nation 
        will descend into civil war, undergo a peaceful separation, or embrace true federalism 
        as a solution to preserve liberty and unity."""
    
    # Generate episode ID from content if not provided
    if not episode_id:
        episode_id = hashlib.md5(transcript.encode()).hexdigest()[:8]
    
    # Check for video URL
    if not video_url:
        video_file = transcript_file.parent / "VIDEO_URL.txt"
        if video_file.exists():
            video_url = video_file.read_text().strip()
    
    # Initialize summarizer
    summarizer = ClaudeSummarizer(episode_id)
    
    # Generate summary and create memory
    result = summarizer.summarize_transcript(transcript, overview, video_url)
    
    # Save outputs
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save summary
    summary_file = output_dir / "summary.md"
    summary_file.write_text(result['summary'])
    logger.info(f"Saved summary to {summary_file}")
    
    # Save keywords
    keywords_file = output_dir / "keywords.json"
    with open(keywords_file, 'w') as f:
        json.dump(result['keywords'], f, indent=2)
    logger.info(f"Saved {len(result['keywords'])} keywords to {keywords_file}")
    
    # Save full result
    result_file = output_dir / "summary_result.json"
    with open(result_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    # Print summary stats
    logger.info("=" * 60)
    logger.info("SUMMARIZATION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Episode ID: {result['episode_id']}")
    logger.info(f"Guest: {result['guest'].get('name', 'Unknown')}")
    logger.info(f"Themes: {len(result['themes'])}")
    logger.info(f"Quotes: {len(result['quotes'])}")
    logger.info(f"Keywords: {len(result['keywords'])}")
    logger.info(f"Memory Created: {result['memory_created']}")
    logger.info(f"Time: {result['summarization_time']:.2f}s")
    logger.info("=" * 60)
    
    return result


def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(
        description="Summarize podcast transcript with Claude and create episode memory"
    )
    
    parser.add_argument(
        '--transcript', '-t',
        type=Path,
        default=Path("transcripts/latest.txt"),
        help="Path to transcript file"
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        default=Path("transcripts"),
        help="Output directory"
    )
    parser.add_argument(
        '--episode-id', '-e',
        help="Episode identifier"
    )
    parser.add_argument(
        '--video-url', '-v',
        help="YouTube video URL"
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help="Test with sample transcript"
    )
    
    args = parser.parse_args()
    
    if args.test:
        # Create test transcript
        test_transcript = """
        Rick Becker: Welcome to War, Divorce, or Federalism. Today we have Daniel Miller 
        from the Texas Nationalist Movement. Daniel, tell us about your organization.
        
        Daniel Miller: Thanks Rick. The Texas Nationalist Movement advocates for Texas 
        independence through peaceful, democratic means. We believe federal overreach has 
        reached a breaking point.
        
        Rick: That's a controversial position. What's your main argument?
        
        Daniel: The federal government has become exactly what the founders feared - an 
        all-powerful central authority that ignores constitutional limits. States like 
        Texas have the right to chart their own course.
        
        Rick: What about those who say secession is illegal?
        
        Daniel: The Constitution is a compact between states. When the federal government 
        violates that compact repeatedly, states have a natural right to withdraw. We're 
        not talking about violence - we want a referendum, a democratic vote.
        
        Rick: What would independence look like practically?
        
        Daniel: Texas would control its own borders, make its own trade deals, and most 
        importantly, govern according to Texan values without federal interference. We'd 
        show the world that peaceful separation is possible.
        """
        
        # Save test transcript
        test_file = Path("/tmp/test_transcript.txt")
        test_file.write_text(test_transcript)
        
        # Process test transcript
        result = process_transcript(
            test_file,
            Path("/tmp"),
            episode_id="test_001",
            video_url="https://youtube.com/watch?v=test"
        )
        
        print("\nTest Summary Generated!")
        print(f"Memory location: episode_memories/episode_test_001.json")
    else:
        # Process real transcript
        if not args.transcript.exists():
            parser.error(f"Transcript file not found: {args.transcript}")
        
        result = process_transcript(
            args.transcript,
            args.output,
            args.episode_id,
            args.video_url
        )


if __name__ == "__main__":
    main()