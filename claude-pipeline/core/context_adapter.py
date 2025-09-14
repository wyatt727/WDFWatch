#!/usr/bin/env python3
"""
Context Adapter - Converts context between different model formats

This module handles the adaptation of context (episode information, instructions, etc.)
from Claude's CLAUDE.md format to formats suitable for different LLM providers.

Features:
- CLAUDE.md parsing and extraction
- Model-specific context formatting
- Context truncation for models with smaller context windows
- Intelligent context prioritization
- Template management for different providers
"""

import logging
import re
from pathlib import Path
from typing import Dict, Optional, List, Any

logger = logging.getLogger(__name__)


class ContextAdapter:
    """
    Adapts context content for different LLM providers and models.
    
    This class takes context in various formats (CLAUDE.md files, raw text, etc.)
    and converts it to the optimal format for the target model, considering
    context limits, prompt structure preferences, and provider-specific features.
    """
    
    def __init__(self):
        """Initialize the context adapter."""
        self.claude_section_parsers = {
            'identity': self._extract_identity_section,
            'podcast': self._extract_podcast_section,
            'themes': self._extract_themes_section,
            'capabilities': self._extract_capabilities_section,
            'episode_context': self._extract_episode_context
        }
    
    def adapt_context_for_model(self, 
                               context_content: str,
                               model_name: str,
                               provider: str,
                               mode: str = "default",
                               max_context_length: Optional[int] = None) -> str:
        """
        Adapt context content for a specific model and provider.
        
        Args:
            context_content: Raw context content (CLAUDE.md format or plain text)
            model_name: Target model name
            provider: Target provider (claude, ollama, etc.)
            mode: Operation mode (summarize, classify, respond, moderate)
            max_context_length: Maximum context length in characters
            
        Returns:
            Adapted context string
        """
        # Parse the context content
        parsed_context = self._parse_context_content(context_content)
        
        # Adapt for specific provider
        if provider == 'claude':
            # Claude can use the original format
            adapted_context = context_content
        elif provider == 'ollama':
            # Convert to Ollama-friendly format
            adapted_context = self._format_for_ollama(parsed_context, mode)
        else:
            # Generic format for other providers
            adapted_context = self._format_generic(parsed_context, mode)
        
        # Truncate if necessary
        if max_context_length and len(adapted_context) > max_context_length:
            adapted_context = self._intelligent_truncate(
                adapted_context, max_context_length, mode
            )
        
        return adapted_context
    
    def load_context_from_files(self, 
                               context_files: List[str],
                               mode: str = "default") -> str:
        """
        Load and combine context from multiple files.
        
        Args:
            context_files: List of file paths
            mode: Operation mode for context prioritization
            
        Returns:
            Combined context content
        """
        combined_context = []
        
        for file_path in context_files:
            path = Path(file_path)
            if not path.exists():
                logger.warning(f"Context file not found: {file_path}")
                continue
            
            try:
                content = path.read_text(encoding='utf-8')
                combined_context.append(f"# {path.name}\n\n{content}")
            except Exception as e:
                logger.error(f"Failed to read context file {file_path}: {e}")
        
        return "\n\n" + "="*50 + "\n\n".join(combined_context)
    
    def _parse_context_content(self, content: str) -> Dict[str, Any]:
        """
        Parse CLAUDE.md style content into structured sections.
        
        Args:
            content: Raw content to parse
            
        Returns:
            Dictionary of parsed sections
        """
        parsed = {
            'identity': '',
            'podcast_info': '',
            'themes': [],
            'capabilities': '',
            'episode_context': '',
            'raw_content': content
        }
        
        # Try to parse as CLAUDE.md format
        if '## YOUR IDENTITY' in content or '# WDF' in content:
            # Parse structured sections
            for section_name, parser in self.claude_section_parsers.items():
                try:
                    parsed[section_name] = parser(content)
                except Exception as e:
                    logger.debug(f"Failed to parse {section_name}: {e}")
        else:
            # Treat as raw content
            parsed['raw_content'] = content
        
        return parsed
    
    def _format_for_ollama(self, parsed_context: Dict[str, Any], mode: str) -> str:
        """
        Format context for Ollama models.
        
        Ollama models generally work better with clear, structured instructions
        and explicit role definitions.
        """
        sections = []
        
        # Add system role definition
        if parsed_context.get('identity'):
            sections.append(f"SYSTEM ROLE:\n{parsed_context['identity']}")
        
        # Add podcast information
        if parsed_context.get('podcast_info'):
            sections.append(f"PODCAST INFORMATION:\n{parsed_context['podcast_info']}")
        
        # Add key themes
        if parsed_context.get('themes'):
            themes_text = "\n".join([f"- {theme}" for theme in parsed_context['themes']])
            sections.append(f"KEY THEMES:\n{themes_text}")
        
        # Add mode-specific instructions
        mode_instructions = self._get_ollama_mode_instructions(mode)
        if mode_instructions:
            sections.append(f"TASK INSTRUCTIONS:\n{mode_instructions}")
        
        # Add episode context if available
        if parsed_context.get('episode_context'):
            sections.append(f"EPISODE CONTEXT:\n{parsed_context['episode_context']}")
        
        # Fall back to raw content if nothing was parsed
        if not sections and parsed_context.get('raw_content'):
            sections.append(f"CONTEXT:\n{parsed_context['raw_content']}")
        
        return "\n\n".join(sections)
    
    def _format_generic(self, parsed_context: Dict[str, Any], mode: str) -> str:
        """
        Format context for generic models.
        
        Uses a simple, clear format that should work with most models.
        """
        sections = []
        
        # Simple context header
        sections.append("CONTEXT AND INSTRUCTIONS:")
        
        # Add all available information
        for key, value in parsed_context.items():
            if key == 'raw_content' or not value:
                continue
            
            if isinstance(value, list):
                value = "\n".join([f"- {item}" for item in value])
            
            sections.append(f"{key.upper().replace('_', ' ')}:\n{value}")
        
        # Add raw content if nothing else
        if len(sections) == 1 and parsed_context.get('raw_content'):
            sections.append(parsed_context['raw_content'])
        
        return "\n\n".join(sections)
    
    def _get_ollama_mode_instructions(self, mode: str) -> str:
        """
        Get mode-specific instructions for Ollama models.
        """
        instructions = {
            'summarize': """
Your task is to analyze podcast transcripts and generate comprehensive summaries.
- Extract key themes, arguments, and solutions discussed
- Identify guest information and credentials  
- Find memorable quotes and controversial points
- Generate 25-30 keywords for social media discovery
- Create structured output for episode memory
            """.strip(),
            
            'classify': """
Your task is to score tweet relevance from 0.00 to 1.00 based on episode themes.
- Analyze tweet content against podcast topics
- Consider constitutional, federalism, and political themes
- Score 0.85-1.00 for highly relevant content
- Score 0.70-0.84 for relevant content
- Score below 0.70 for less relevant content
- Output ONLY the numerical score (e.g., 0.85)
            """.strip(),
            
            'respond': """
Your task is to generate engaging tweet responses under 200 characters.
- Connect the tweet to episode themes naturally
- Include the podcast name and episode URL
- Maintain a provocative but respectful tone
- Reference specific episode content when relevant
- Never use emojis in responses
- Keep responses concise and engaging
            """.strip(),
            
            'moderate': """
Your task is to evaluate response quality and appropriateness.
- Check relevance to original tweet (0-10)
- Assess engagement potential (0-10) 
- Verify character count is under 200
- Confirm URL is included
- Ensure tone is appropriate
- Provide specific feedback for improvements
            """.strip()
        }
        
        return instructions.get(mode, "")
    
    def _intelligent_truncate(self, content: str, max_length: int, mode: str) -> str:
        """
        Intelligently truncate content while preserving important information.
        
        Priority order based on mode:
        - Always keep task instructions
        - Keep episode context for specific tasks
        - Keep themes for classification/response
        - Truncate background information last
        """
        if len(content) <= max_length:
            return content
        
        # Split into sections
        sections = content.split('\n\n')
        
        # Define priority order based on mode
        priority_keywords = {
            'classify': ['TASK INSTRUCTIONS', 'KEY THEMES', 'EPISODE CONTEXT'],
            'respond': ['TASK INSTRUCTIONS', 'EPISODE CONTEXT', 'PODCAST INFORMATION'],
            'summarize': ['TASK INSTRUCTIONS', 'SYSTEM ROLE', 'PODCAST INFORMATION'],
            'moderate': ['TASK INSTRUCTIONS', 'SYSTEM ROLE', 'KEY THEMES']
        }
        
        mode_priorities = priority_keywords.get(mode, ['TASK INSTRUCTIONS', 'SYSTEM ROLE'])
        
        # Keep high priority sections
        kept_sections = []
        remaining_length = max_length
        
        # First pass: keep essential sections
        for section in sections:
            section_header = section.split('\n')[0].upper()
            if any(priority in section_header for priority in mode_priorities):
                if len(section) <= remaining_length - 50:  # Leave some buffer
                    kept_sections.append(section)
                    remaining_length -= len(section) + 2  # +2 for \n\n
        
        # Second pass: add other sections if space allows
        for section in sections:
            if section not in kept_sections and len(section) <= remaining_length - 50:
                kept_sections.append(section)
                remaining_length -= len(section) + 2
        
        # If still too long, truncate the last section
        result = '\n\n'.join(kept_sections)
        if len(result) > max_length:
            truncate_at = max_length - 50
            result = result[:truncate_at] + "\n\n[... truncated for length ...]"
        
        return result
    
    # Section parsers for CLAUDE.md format
    def _extract_identity_section(self, content: str) -> str:
        """Extract the identity/role section."""
        match = re.search(r'## YOUR IDENTITY\s*\n(.*?)(?=\n##|\n#|\Z)', content, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # Alternative format
        match = re.search(r'# WDF.*?AI System\s*\n(.*?)(?=\n##|\n#|\Z)', content, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        return ""
    
    def _extract_podcast_section(self, content: str) -> str:
        """Extract podcast foundation/information."""
        match = re.search(r'## PODCAST FOUNDATION\s*\n(.*?)(?=\n##|\n#|\Z)', content, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        return ""
    
    def _extract_themes_section(self, content: str) -> List[str]:
        """Extract core themes as a list."""
        match = re.search(r'## CORE THEMES\s*\n(.*?)(?=\n##|\n#|\Z)', content, re.DOTALL)
        if match:
            themes_text = match.group(1).strip()
            # Extract bullet points
            themes = []
            for line in themes_text.split('\n'):
                line = line.strip()
                if line.startswith('-') or line.startswith('•'):
                    themes.append(line[1:].strip())
            return themes
        
        return []
    
    def _extract_capabilities_section(self, content: str) -> str:
        """Extract capabilities/modes section."""
        match = re.search(r'## YOUR CAPABILITIES\s*\n(.*?)(?=\n##|\n#|\Z)', content, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        return ""
    
    def _extract_episode_context(self, content: str) -> str:
        """Extract episode-specific context."""
        match = re.search(r'## EPISODE CONTEXT\s*\n(.*?)(?=\n##|\n#|\Z)', content, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # Look for episode-specific information
        episode_patterns = [
            r'### Guest:.*?(?=\n###|\n##|\Z)',
            r'### Episode Date:.*?(?=\n###|\n##|\Z)',
            r'### KEY THEMES.*?(?=\n###|\n##|\Z)',
            r'### MEMORABLE QUOTES.*?(?=\n###|\n##|\Z)'
        ]
        
        episode_info = []
        for pattern in episode_patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                episode_info.append(match.group(0))
        
        return '\n\n'.join(episode_info) if episode_info else ""