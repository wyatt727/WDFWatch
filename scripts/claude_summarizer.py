#!/usr/bin/env python3
"""
Claude Transcript Summarizer Wrapper

This script provides a wrapper around the transcript summarization process,
allowing it to use Claude instead of Gemini when configured.

It maintains compatibility with the existing JavaScript summarizer by:
1. Reading the same input files
2. Producing the same output format
3. Supporting the same command-line flags

Usage:
    python scripts/claude_summarizer.py [--verbose] [--mock]
    
This can be called from main.py when Claude is selected for summarization.
"""

import json
import os
import subprocess
import sys
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Get Claude command builder
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.wdf.claude_config import build_claude_command

# Configuration
CONFIG = {
    'transcript_path': Path('transcripts/latest.txt'),
    'overview_path': Path('transcripts/podcast_overview.txt'),
    'summary_path': Path('transcripts/summary.md'),
    'keywords_path': Path('transcripts/keywords.json'),
    'hash_path': Path('transcripts/summary.hash'),
    'max_chunk_size': 50000,  # Claude can handle larger chunks
    'verbose': '--verbose' in sys.argv,
    'use_mock': '--mock' in sys.argv,
}

def log(*args):
    """Log message if verbose mode is enabled"""
    if CONFIG['verbose']:
        print('[claude-summarizer]', *args, file=sys.stderr)

def compute_hash(content: str) -> str:
    """Compute SHA256 hash of content"""
    return hashlib.sha256(content.encode()).hexdigest()

def load_existing_hash() -> Optional[str]:
    """Load existing hash if it exists"""
    try:
        return CONFIG['hash_path'].read_text().strip()
    except:
        return None

def save_hash(hash_value: str):
    """Save hash to file"""
    try:
        CONFIG['hash_path'].write_text(hash_value)
    except Exception as e:
        log(f'Unable to write hash file: {e}')

def read_input_files() -> Tuple[str, str]:
    """Read the transcript and overview files"""
    # Check if files exist, create mock content if not
    if not CONFIG['transcript_path'].exists():
        if CONFIG['use_mock']:
            log(f"Creating mock transcript file: {CONFIG['transcript_path']}")
            CONFIG['transcript_path'].write_text(
                "This is a mock transcript of the War, Divorce, or Federalism podcast. "
                "In this episode, Rick Becker discusses constitutional rights, liberty, "
                "and the importance of federalism in modern governance."
            )
        else:
            raise FileNotFoundError(f"Transcript not found: {CONFIG['transcript_path']}")
    
    # Use database overview if available from environment
    db_overview = os.environ.get('WDF_CONTEXT_PODCAST_OVERVIEW')
    if db_overview:
        overview = db_overview.replace('\\n', '\n')
        log('Using podcast overview from database')
    else:
        if not CONFIG['overview_path'].exists():
            if CONFIG['use_mock']:
                log(f"Creating mock overview file: {CONFIG['overview_path']}")
                CONFIG['overview_path'].write_text(
                    "WDF is a podcast about War, Divorce, and Federalism hosted by Rick Becker. "
                    "It explores political philosophy, constitutional rights, and liberty."
                )
            else:
                raise FileNotFoundError(f"Overview not found: {CONFIG['overview_path']}")
        overview = CONFIG['overview_path'].read_text()
    
    transcript = CONFIG['transcript_path'].read_text()
    
    log(f"Read {len(transcript)} chars from {CONFIG['transcript_path']}")
    log(f"Read {len(overview)} chars from overview")
    
    return transcript, overview

def generate_mock_response() -> Tuple[str, List[str]]:
    """Generate mock response for testing"""
    summary = """## Episode Summary

This episode of War, Divorce, or Federalism explores the fundamental tensions in American governance, 
examining whether the nation can maintain unity through genuine federalism or if deeper divisions 
will lead to conflict or separation.

Rick Becker discusses the importance of constitutional principles and individual liberty in the 
context of modern political challenges. The conversation touches on state sovereignty, federal 
overreach, and the proper balance of governmental powers.

Key themes include the erosion of federalist principles, the concentration of power in Washington DC, 
and potential paths forward for preserving both unity and liberty in America."""
    
    keywords = [
        "federalism",
        "constitutional rights",
        "liberty",
        "Rick Becker",
        "state sovereignty",
        "limited government",
        "founding fathers",
        "freedom",
        "individual rights",
        "WDF podcast",
        "federal overreach",
        "states' rights",
        "civil liberties",
        "separation of powers",
        "governance"
    ]
    
    return summary, keywords

def process_with_claude(transcript: str, overview: str) -> Tuple[str, List[str]]:
    """
    Process transcript with Claude to generate summary and keywords
    
    Args:
        transcript: The podcast transcript
        overview: The podcast overview
        
    Returns:
        Tuple of (summary, keywords)
    """
    # Use mock if requested
    if CONFIG['use_mock']:
        return generate_mock_response()
    
    # Build the prompt
    db_prompt = os.environ.get('WDF_PROMPT_SUMMARIZATION')
    
    if db_prompt:
        # Use database prompt with variable substitution
        prompt = db_prompt.replace('\\n', '\n')
        prompt = prompt.replace('{overview}', overview)
        prompt = prompt.replace('{chunk}', transcript)
        prompt = prompt.replace('{is_first_chunk}', 'true')
        prompt = prompt.replace('{is_last_chunk}', 'true')
        log('Using summarization prompt from database')
    else:
        # Use default prompt
        prompt = f"""You are an expert social media manager for the "War, Divorce, or Federalism" podcast hosted by Rick Becker.

Your task is to create an EXTREMELY lengthy and comprehensive summary of this podcast episode, touching on all the topics discussed.
The summary should be detailed enough for someone who hasn't listened to understand all key points.
Include how it relates to the podcast as a whole.
DO NOT start with phrases like "Here is the summary" or "In this episode". Start directly with the summary content.

After the summary, add a section titled "### Keywords signaling tweet relevance" 
with a list of 20 specific keywords or phrases that would indicate a tweet is relevant to this episode, including WDF and Rick Becker.

FORMAT REQUIREMENTS FOR KEYWORDS:
- List each keyword or phrase on its own line with a bullet point (- ) prefix
- Use proper names exactly as they appear
- Include both specific terms and broader concepts
- Make sure each keyword/phrase is truly distinctive to this episode's content

These keywords will be used to find relevant social media posts to engage with.

PODCAST OVERVIEW:
{overview}

TRANSCRIPT:
{transcript}"""
    
    log("Calling Claude CLI for summarization")
    
    # Call Claude CLI with optimized no-MCP config
    result = subprocess.run(
        build_claude_command(prompt),
        capture_output=True,
        text=True,
        encoding='utf-8',
        timeout=30  # Reduced timeout with no-MCP config
    )
    
    if result.returncode != 0:
        log(f'Claude failed: {result.stderr}')
        raise RuntimeError(f'Claude exited with code {result.returncode}')
    
    response = result.stdout.strip()
    
    # Clean up the response by removing introductory text
    response = response.replace('Of course.', '').strip()
    response = response.replace('Here is', '').strip()
    response = response.replace("I'll provide", '').strip()
    response = response.replace('Sure.', '').strip()
    response = response.replace('Let me', '').strip()
    
    # Extract keywords from the response
    keywords = extract_keywords(response)
    
    return response, keywords

def extract_keywords(summary: str) -> List[str]:
    """Extract keywords from the summary"""
    # Look for the keywords section
    keywords_section = None
    lines = summary.split('\n')
    
    in_keywords = False
    keywords = []
    
    for line in lines:
        if '### Keywords signaling tweet relevance' in line:
            in_keywords = True
            continue
        
        if in_keywords:
            # Stop at next section
            if line.startswith('###') or line.startswith('##'):
                break
            
            # Extract keyword from bullet point line
            line = line.strip()
            if line.startswith('- ') or line.startswith('* ') or line.startswith('• '):
                keyword = line[2:].strip()
                # Remove quotes if present
                if keyword.startswith('"') and keyword.endswith('"'):
                    keyword = keyword[1:-1]
                if keyword:
                    keywords.append(keyword)
    
    # Fallback: extract some keywords from the summary if none found
    if not keywords:
        log('Could not find keywords section, extracting from summary')
        # Extract proper nouns and key terms
        words = summary.split()
        seen = set()
        for word in words:
            if len(word) > 4 and word[0].isupper() and word not in seen:
                seen.add(word)
                keywords.append(word)
                if len(keywords) >= 15:
                    break
    
    log(f'Extracted {len(keywords)} keywords')
    return keywords

def write_output_files(summary: str, keywords: List[str]):
    """Write output files atomically using temp files"""
    # Write summary
    temp_summary = CONFIG['summary_path'].with_suffix('.tmp')
    temp_summary.write_text(summary)
    temp_summary.rename(CONFIG['summary_path'])
    log(f"Wrote summary to {CONFIG['summary_path']}")
    
    # Write keywords
    temp_keywords = CONFIG['keywords_path'].with_suffix('.tmp')
    with open(temp_keywords, 'w') as f:
        json.dump(keywords, f, indent=2)
    temp_keywords.rename(CONFIG['keywords_path'])
    log(f"Wrote {len(keywords)} keywords to {CONFIG['keywords_path']}")

def main():
    """Main entry point"""
    try:
        # Read input files
        transcript, overview = read_input_files()
        
        # Check if we can skip processing (cached)
        current_hash = compute_hash(transcript + overview)
        existing_hash = load_existing_hash()
        
        if existing_hash == current_hash and CONFIG['summary_path'].exists() and CONFIG['keywords_path'].exists():
            log("Summary already exists and inputs unchanged, skipping")
            print(json.dumps({
                'status': 'success',
                'cached': True,
                'summary_file': str(CONFIG['summary_path']),
                'keywords_file': str(CONFIG['keywords_path'])
            }))
            return 0
        
        # Process with Claude
        summary, keywords = process_with_claude(transcript, overview)
        
        # Write output files
        write_output_files(summary, keywords)
        
        # Save hash
        save_hash(current_hash)
        
        # Print success message
        print(json.dumps({
            'status': 'success',
            'cached': False,
            'summary_file': str(CONFIG['summary_path']),
            'keywords_file': str(CONFIG['keywords_path']),
            'summary_length': len(summary),
            'keyword_count': len(keywords)
        }))
        
        return 0
        
    except Exception as e:
        log(f"Error: {e}")
        print(json.dumps({
            'status': 'error',
            'error': str(e)
        }), file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())