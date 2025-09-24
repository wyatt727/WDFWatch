"""
Utilities for loading and using prompt templates from the database.

This module provides functions to:
- Load prompts from environment variables (set by load_prompts.py)
- Perform variable substitution in templates
- Fall back to hardcoded defaults when needed
"""

import os
import re
import json
from typing import Dict, Any, Optional


def substitute_variables(template: str, variables: Dict[str, Any]) -> str:
    """
    Perform variable substitution in a prompt template.
    
    Supports:
    - Simple substitution: {variable}
    - Conditional substitution: {condition ? 'true text' : 'false text'}
    
    Args:
        template: The template string with placeholders
        variables: Dictionary of variable values
        
    Returns:
        The template with variables substituted
    """
    result = template
    
    # Handle conditional blocks first (e.g., {condition ? 'true text' : 'false text'})
    def replace_conditional(match):
        var_name = match.group(1)
        true_text = match.group(2)
        false_text = match.group(3)
        return true_text if variables.get(var_name) else false_text
    
    result = re.sub(
        r'\{(\w+)\s*\?\s*[\'"]([^\'"]*)[\'"]\s*:\s*[\'"]([^\'"]*)[\'"]?\}',
        replace_conditional,
        result
    )
    
    # Handle simple variable substitutions (e.g., {variable})
    def replace_simple(match):
        var_name = match.group(1)
        value = variables.get(var_name)
        return str(value) if value is not None else match.group(0)
    
    result = re.sub(r'\{(\w+)\}', replace_simple, result)
    
    return result


def get_prompt_template(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get a prompt template from environment variables.
    
    Args:
        key: The prompt key (e.g., 'summarization', 'classification')
        default: Default template to use if not found
        
    Returns:
        The prompt template string, or default if not found
    """
    env_key = f"WDF_PROMPT_{key.upper()}"
    template = os.environ.get(env_key)
    
    if template:
        # Unescape newlines that were escaped for shell export
        template = template.replace('\\n', '\n')
    
    return template or default


def get_prompt_variables(key: str) -> list:
    """
    Get the list of variables for a prompt template.
    
    Args:
        key: The prompt key
        
    Returns:
        List of variable names
    """
    env_key = f"WDF_PROMPT_{key.upper()}_VARS"
    vars_json = os.environ.get(env_key, '[]')
    
    try:
        return json.loads(vars_json)
    except json.JSONDecodeError:
        return []


def get_context_file(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get a context file content from environment variables.
    
    Args:
        key: The context file key (e.g., 'podcast_overview', 'video_url')
        default: Default content to use if not found
        
    Returns:
        The context file content, or default if not found
    """
    env_key = f"WDF_CONTEXT_{key.upper()}"
    content = os.environ.get(env_key)
    
    if content:
        # Unescape newlines that were escaped for shell export
        content = content.replace('\\n', '\n')
    
    return content or default


def build_prompt(template_key: str, variables: Dict[str, Any], default_template: Optional[str] = None) -> str:
    """
    Build a prompt by loading template and substituting variables.
    
    Args:
        template_key: The prompt template key
        variables: Dictionary of variable values
        default_template: Default template to use if not found
        
    Returns:
        The formatted prompt with variables substituted
    """
    template = get_prompt_template(template_key, default_template)
    
    if not template:
        raise ValueError(f"No prompt template found for key '{template_key}' and no default provided")
    
    return substitute_variables(template, variables)


# Specific prompt builders for each pipeline task

def build_summarization_prompt(
    is_first_chunk: bool,
    is_last_chunk: bool,
    overview: str,
    chunk: str
) -> str:
    """Build the summarization prompt with variables."""
    default_template = """You are an expert social media manager for the "War, Divorce, or Federalism" podcast hosted by Rick Becker.
{is_first_chunk ? 'Your task is to create an EXTREMELY lengthy and comprehensive summary of this podcast episode, touching on all the topics discussed.
The summary should be detailed enough for someone who hasn't listened to understand all key points.
Include how it relates to the podcast as a whole.
DO NOT start with phrases like "Here is the summary" or "In this episode". Start directly with the summary content.' : 'Continue analyzing this podcast transcript chunk. Add to the summary you've been building.'}
{is_last_chunk ? 'This is the final chunk. Please finalize your summary and then add a section titled "### Keywords signaling tweet relevance" 
with a list of 20 specific keywords or phrases that would indicate a tweet is relevant to this episode, including WDF and Rick Becker.

FORMAT REQUIREMENTS FOR KEYWORDS:
- List each keyword or phrase on its own line with a bullet point (- ) prefix
- Use proper names exactly as they appear
- Include both specific terms and broader concepts
- Make sure each keyword/phrase is truly distinctive to this episode's content

These keywords will be used to find relevant social media posts to engage with.' : ''}

PODCAST OVERVIEW:
{overview}

TRANSCRIPT CHUNK:
{chunk}"""
    
    return build_prompt('summarization', {
        'is_first_chunk': is_first_chunk,
        'is_last_chunk': is_last_chunk,
        'overview': overview,
        'chunk': chunk
    }, default_template)


def build_fewshot_prompt(
    required_examples: int,
    overview: str,
    summary: str
) -> str:
    """Build the few-shot generation prompt with variables."""
    default_template = """<start_of_turn>system
You are a tweet relevancy scorer for the 'War, Divorce, or Federalism' podcast.
Your task is to generate {required_examples} example tweets and score their relevancy from 0.00 to 1.00.

CRITICAL: You MUST use NUMERICAL SCORES only, not text labels like "RELEVANT" or "SKIP".

A score of 1.00 means the tweet is highly relevant to the podcast topic and perfect for engagement.
A score of 0.00 means the tweet is completely irrelevant to the podcast topic.

SCORING GUIDELINES:
- 0.85-1.00: Highly relevant - directly discusses podcast topics, perfect for engagement
- 0.70-0.84: Relevant - relates to podcast themes, good for engagement
- 0.30-0.69: Somewhat relevant - tangentially related, might be worth reviewing
- 0.00-0.29: Not relevant - unrelated to podcast topics, skip

FORMAT REQUIREMENTS - STRICTLY ENFORCED:
1. Generate EXACTLY {required_examples} example tweets.
2. Each line must contain a tweet text, followed by a TAB (\\t), then a NUMERICAL score between 0.00 and 1.00.
3. NEVER use words like "RELEVANT", "SKIP", "HIGH", "LOW" - ONLY use decimal numbers (e.g., 0.85, 0.42, 1.00).
4. Scores should have a realistic distribution - not all high or low.
5. At least 30% of examples should score >= 0.70 (relevant range).
6. Include examples across the full score range (0.00 to 1.00).
7. Do not include any explanations or additional text.
8. Start immediately with the examples.
9. Randomize the order of scores.

EXAMPLE OUTPUT FORMAT:
This is a tweet about federalism and state rights	0.92
My cat is sleeping on my keyboard	0.05
Rick Becker discusses constitutional issues	0.89
Just made coffee this morning	0.02

TWEET DIVERSITY REQUIREMENTS:
1. Some high-scoring tweets should NOT include any hashtags.
2. Some low-scoring tweets SHOULD include hashtags that seem related to the podcast topics (like #liberty, #federalism, etc.) but the tweet content itself should be about something unrelated.
3. Create a mix of tweet styles, lengths, and tones to represent realistic social media content.
4. Include tweets with scores in the middle range (0.40-0.60) that are somewhat related but not clearly relevant.

PODCAST OVERVIEW:
{overview}

SUMMARY:
{summary}
<end_of_turn>
<start_of_turn>model"""
    
    # Check if we should force use of default template (bypass database)
    if os.environ.get('WDF_USE_DEFAULT_FEWSHOT_PROMPT', 'false').lower() == 'true':
        print("INFO: Using default few-shot prompt template (bypassing database)")
        return substitute_variables(default_template, {
            'required_examples': required_examples,
            'overview': overview,
            'summary': summary
        })
    
    return build_prompt('fewshot_generation', {
        'required_examples': required_examples,
        'overview': overview,
        'summary': summary
    }, default_template)


def build_classification_prompt(topic_summary: Optional[str] = None) -> str:
    """Build the classification system prompt with optional topic summary."""
    default_template = """You are an assistant that scores tweet relevancy from 0.00 to 1.00 by using few-shot examples.
You must follow these rules exactly:
1. Analyze the tweet's relevance to the topic based on the few-shot examples.
2. Reply with ONLY a decimal number between 0.00 and 1.00.
3. Use two decimal places (e.g., 0.85, 0.42, 1.00).
4. Higher scores mean more relevant to the topic.
5. Do not include any other text, explanations, or formatting.

SCORING GUIDELINES:
- 0.85-1.00: Highly relevant - directly discusses topic themes
- 0.70-0.84: Relevant - relates to topic, good for engagement
- 0.30-0.69: Somewhat relevant - tangentially related
- 0.00-0.29: Not relevant - unrelated to topic

NEVER deviate from the numeric format. Accuracy is critical.
{topic_summary ? '\\n\\nTOPIC CONTEXT:\\n{topic_summary}' : ''}"""
    
    return build_prompt('tweet_classification', {
        'topic_summary': topic_summary
    }, default_template)


def build_response_prompt(
    max_length: int,
    video_url: str,
    podcast_overview: str,
    summary: str
) -> str:
    """Build the response generation prompt with variables."""
    default_template = """You are a controversial social media manager for the WDF Podcast (War, Divorce or Federalism)
The podcast has a strong libertarian/constitutionalist audience that values liberty, limited government, and individual rights.

CRITICAL RULES:
1. The user message is a tweet you are responding to.
2. ASSUME THE USER HAS NEVER HEARD OF THE WDF PODCAST BEFORE.
3. Your response MUST be LESS THAN {max_length} characters - this is ABSOLUTELY REQUIRED.
4. Every response must reference the WDF Podcast by name.
5. Make the user want to listen to the podcast.
6. Briefly mention what the latest episode discusses.
7. Use language that resonates with liberty-minded, constitutionalist audiences.
8. Be provocative and engaging, not just informational.
9. ALWAYS include the link {video_url}.
10. Only output the tweet text—no extra formatting.
11. No emojis allowed!
12. Double check your response is less than {max_length} characters.
13. Triple check that your response is less than {max_length} characters!

PODCAST OVERVIEW:
{podcast_overview}

EPISODE SUMMARY:
{summary}"""
    
    return build_prompt('response_generation', {
        'max_length': max_length,
        'video_url': video_url,
        'podcast_overview': podcast_overview,
        'summary': summary
    }, default_template)