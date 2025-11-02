#!/usr/bin/env python3
"""
Claude Summarization Task - Pipeline integration for Claude-based summarization.
Creates episode summaries AND generates episode memory for the entire pipeline.
"""

import json
import subprocess
import sys
import time
import hashlib
from pathlib import Path
from typing import Optional, Dict, List
import logging

# Add claude-summarizer to path
CLAUDE_SUMMARIZER_DIR = Path(__file__).parent.parent.parent.parent / "claude-summarizer"
sys.path.insert(0, str(CLAUDE_SUMMARIZER_DIR))

from summarize import ClaudeSummarizer

# Conditional imports for web bridge
try:
    from src.wdf.web_bridge import WebBridge
    web_bridge = WebBridge()
except ImportError:
    web_bridge = None

logger = logging.getLogger(__name__)

def run(
    run_id: str = None,
    episode_id: str = None,
    force: bool = False
) -> Dict:
    """
    Run Claude summarization task as part of the pipeline.
    This creates the episode memory that all other stages will use.
    
    Args:
        run_id: Unique run identifier
        episode_id: Episode identifier for memory
        force: Force regeneration even if summary exists
        
    Returns:
        Dictionary with summary results and memory stats
    """
    run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
    logger.info(f"Starting Claude summarization for run {run_id}")
    
    # Set up paths
    base_dir = Path(__file__).parent.parent.parent.parent
    transcripts_dir = base_dir / "transcripts"
    artefacts_dir = base_dir / "artefacts" / run_id
    artefacts_dir.mkdir(parents=True, exist_ok=True)
    
    # Input and output files
    transcript_file = transcripts_dir / "latest.txt"
    overview_file = transcripts_dir / "podcast_overview.txt"
    video_url_file = transcripts_dir / "VIDEO_URL.txt"
    summary_file = transcripts_dir / "summary.md"
    keywords_file = transcripts_dir / "keywords.json"
    
    # Check if already summarized (unless forced)
    if not force and summary_file.exists() and keywords_file.exists():
        # Check if transcript changed
        transcript_hash = hashlib.md5(transcript_file.read_bytes()).hexdigest()
        hash_file = transcripts_dir / "summary.hash"
        
        if hash_file.exists() and hash_file.read_text() == transcript_hash:
            logger.info("Summary already exists and transcript unchanged, skipping")
            
            # Load existing summary
            summary = summary_file.read_text()
            keywords = json.loads(keywords_file.read_text())
            
            # Check if memory exists
            if not episode_id:
                episode_id = transcript_hash[:8]
            
            memory_file = base_dir / "episode_memories" / f"episode_{episode_id}.json"
            if memory_file.exists():
                logger.info(f"Episode memory already exists for {episode_id}")
                with open(memory_file) as f:
                    memory_stats = json.load(f)
                
                return {
                    'summary': summary,
                    'keywords': keywords,
                    'episode_id': episode_id,
                    'memory_exists': True,
                    'memory_stats': memory_stats,
                    'cached': True
                }
    
    # Check for transcript
    if not transcript_file.exists():
        logger.error(f"No transcript file found at {transcript_file}")
        raise FileNotFoundError(f"Transcript not found: {transcript_file}")
    
    # Load transcript
    transcript = transcript_file.read_text()
    
    # Load overview
    if overview_file.exists():
        overview = overview_file.read_text()
    else:
        overview = """The War, Divorce, or Federalism podcast explores America's future 
        in the context of political division. Host Rick Becker examines whether the nation 
        will descend into civil war, undergo a peaceful separation, or embrace true federalism 
        as a solution to preserve liberty and unity."""
    
    # Get video URL
    video_url = None
    if video_url_file.exists():
        video_url = video_url_file.read_text().strip()
    
    # Generate episode ID from transcript if not provided
    if not episode_id:
        episode_id = hashlib.md5(transcript.encode()).hexdigest()[:8]
    
    logger.info(f"Episode ID: {episode_id}")
    
    # Notify web UI
    if web_bridge:
        web_bridge.send_event({
            'type': 'summarization_started',
            'run_id': run_id,
            'episode_id': episode_id,
            'transcript_length': len(transcript)
        })
    
    # Initialize summarizer
    summarizer = ClaudeSummarizer(episode_id)
    
    # Generate summary and create memory
    logger.info("Generating summary and creating episode memory...")
    start_time = time.time()
    
    result = summarizer.summarize_transcript(
        transcript=transcript,
        podcast_overview=overview,
        video_url=video_url
    )
    
    elapsed_time = time.time() - start_time
    
    # Save outputs
    summary_file.write_text(result['summary'])
    logger.info(f"Saved summary to {summary_file}")

    # Check if this is a keyword-based episode (preserve user's keywords)
    # Try to find metadata in episode directory if episode_id provided
    is_keyword_episode = False
    metadata_file = None

    if episode_id:
        # Try to find episode directory
        from src.wdf.episode_files import get_episode_file_manager
        try:
            file_manager = get_episode_file_manager(episode_id)
            episode_dir = file_manager.episode_dir
            metadata_file = episode_dir / "metadata.json"
        except Exception as e:
            logger.debug(f"Could not get episode directory: {e}")

    # Fallback to transcripts directory
    if metadata_file is None or not metadata_file.exists():
        metadata_file = transcripts_dir / "metadata.json"

    if metadata_file.exists():
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
                is_keyword_episode = metadata.get('episodeType') == 'keyword_search'
                logger.info(f"Detected episode type: {metadata.get('episodeType', 'normal')}")
        except Exception as e:
            logger.warning(f"Could not read metadata: {e}")

    # Determine target directories for keywords
    if episode_id and metadata_file and metadata_file != transcripts_dir / "metadata.json":
        # Episode directory - save keywords there
        keywords_target_file = episode_dir / "keywords.json"
        extracted_keywords_target = episode_dir / "extracted_keywords.json"
    else:
        # Transcripts directory
        keywords_target_file = keywords_file
        extracted_keywords_target = transcripts_dir / "extracted_keywords.json"

    if is_keyword_episode:
        # For keyword-based episodes, save extracted keywords separately
        # to preserve the user's manually specified keywords in keywords.json
        with open(extracted_keywords_target, 'w') as f:
            json.dump(result['keywords'], f, indent=2)
        logger.info(f"Keyword-based episode detected - saved {len(result['keywords'])} extracted keywords to {extracted_keywords_target}")
        logger.info(f"Preserving user's search keywords in {keywords_target_file}")
    else:
        # Normal episode - save keywords as usual
        with open(keywords_target_file, 'w') as f:
            json.dump(result['keywords'], f, indent=2)
        logger.info(f"Saved {len(result['keywords'])} keywords to {keywords_target_file}")
    
    # Save hash for caching
    transcript_hash = hashlib.md5(transcript.encode()).hexdigest()
    hash_file = transcripts_dir / "summary.hash"
    hash_file.write_text(transcript_hash)
    
    # Save to artefacts
    artefact_summary = artefacts_dir / "summary.md"
    artefact_summary.write_text(result['summary'])
    
    artefact_keywords = artefacts_dir / "keywords.json"
    with open(artefact_keywords, 'w') as f:
        json.dump(result['keywords'], f, indent=2)
    
    artefact_result = artefacts_dir / "summary_result.json"
    with open(artefact_result, 'w') as f:
        json.dump(result, f, indent=2)
    
    # Update web UI if available
    if web_bridge:
        web_bridge.send_event({
            'type': 'summarization_complete',
            'run_id': run_id,
            'episode_id': episode_id,
            'guest': result.get('guest', {}),
            'themes': len(result.get('themes', [])),
            'keywords': len(result['keywords']),
            'time_seconds': elapsed_time
        })
        
        # Create episode in database
        web_bridge.create_episode({
            'id': episode_id,
            'title': f"Episode {episode_id}",
            'guest_name': result.get('guest', {}).get('name'),
            'summary': result['summary'],
            'keywords': result['keywords'],
            'video_url': video_url
        })
    
    # Log summary
    logger.info("=" * 60)
    logger.info("CLAUDE SUMMARIZATION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Episode ID: {episode_id}")
    logger.info(f"Guest: {result.get('guest', {}).get('name', 'Unknown')}")
    logger.info(f"Themes: {len(result.get('themes', []))}")
    logger.info(f"Quotes: {len(result.get('quotes', []))}")
    logger.info(f"Keywords: {len(result['keywords'])}")
    logger.info(f"Memory Created: {result['memory_created']}")
    logger.info(f"Time: {elapsed_time:.2f}s")
    logger.info("=" * 60)
    
    # Important notice about memory
    logger.info("")
    logger.info("🧠 EPISODE MEMORY CREATED 🧠")
    logger.info(f"Memory ID: {episode_id}")
    logger.info("This memory will be used by:")
    logger.info("  - Classification (lightweight context)")
    logger.info("  - Response generation (rich context)")
    logger.info("  - Quality moderation (evaluation context)")
    logger.info("")
    
    return result


def compare_with_gemini(run_id: str = None) -> Dict:
    """
    Compare Claude summarization with Gemini summarization.
    Useful for validation and quality assessment.
    """
    run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
    base_dir = Path(__file__).parent.parent.parent.parent
    
    # Run both summarizers
    logger.info("Running comparison between Claude and Gemini...")
    
    # Run Gemini summarizer (if available)
    gemini_script = base_dir / "scripts" / "transcript_summarizer.js"
    gemini_result = {}
    
    if gemini_script.exists():
        logger.info("Running Gemini summarizer...")
        start = time.time()
        result = subprocess.run(
            ["node", str(gemini_script)],
            capture_output=True,
            text=True,
            cwd=base_dir
        )
        gemini_time = time.time() - start
        
        if result.returncode == 0:
            # Load Gemini outputs
            summary_file = base_dir / "transcripts" / "summary_gemini.md"
            keywords_file = base_dir / "transcripts" / "keywords_gemini.json"
            
            if summary_file.exists():
                gemini_result['summary'] = summary_file.read_text()
                gemini_result['time'] = gemini_time
            
            if keywords_file.exists():
                with open(keywords_file) as f:
                    gemini_result['keywords'] = json.load(f)
    
    # Run Claude summarizer
    logger.info("Running Claude summarizer...")
    claude_result = run(run_id=run_id, force=True)
    
    # Compare results
    comparison = {
        'run_id': run_id,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'claude': {
            'summary_length': len(claude_result.get('summary', '')),
            'keyword_count': len(claude_result.get('keywords', [])),
            'time_seconds': claude_result.get('summarization_time', 0),
            'has_memory': claude_result.get('memory_created', False),
            'themes': len(claude_result.get('themes', [])),
            'quotes': len(claude_result.get('quotes', []))
        },
        'gemini': {
            'summary_length': len(gemini_result.get('summary', '')),
            'keyword_count': len(gemini_result.get('keywords', [])),
            'time_seconds': gemini_result.get('time', 0)
        }
    }
    
    # Calculate differences
    if gemini_result and claude_result:
        comparison['differences'] = {
            'summary_length_diff': comparison['claude']['summary_length'] - comparison['gemini']['summary_length'],
            'keyword_overlap': len(set(claude_result.get('keywords', [])) & set(gemini_result.get('keywords', [])))
        }
    
    # Save comparison
    comparison_file = base_dir / "artefacts" / run_id / "summarization_comparison.json"
    comparison_file.parent.mkdir(parents=True, exist_ok=True)
    with open(comparison_file, 'w') as f:
        json.dump(comparison, f, indent=2)
    
    logger.info(f"Comparison saved to {comparison_file}")
    
    return comparison


# CLI usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Claude summarization task")
    parser.add_argument("--run-id", help="Run identifier")
    parser.add_argument("--episode-id", help="Episode identifier")
    parser.add_argument("--force", action="store_true", help="Force regeneration")
    parser.add_argument("--compare", action="store_true", help="Compare with Gemini")
    
    args = parser.parse_args()
    
    if args.compare:
        results = compare_with_gemini(args.run_id)
        print(json.dumps(results, indent=2))
    else:
        result = run(
            run_id=args.run_id,
            episode_id=args.episode_id,
            force=args.force
        )
        print(f"Summarization complete for episode {result['episode_id']}")