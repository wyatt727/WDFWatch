#!/usr/bin/env python3
"""
Claude Adapter - Interface for Claude models via CLI

This adapter implements the ModelInterface for Claude models, providing
seamless integration with the existing Claude CLI while supporting the
new flexible model configuration system.

Features:
- Uses existing Claude CLI for API calls
- Supports specialized CLAUDE.md context files
- Cost tracking and estimation
- Batch processing optimization
- Automatic retry logic
"""

import asyncio
import logging
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Optional, Any

from ..model_interface import ModelInterface, ModelResponse, ModelConfig, ModelException, ModelTimeoutException

logger = logging.getLogger(__name__)


class ClaudeAdapter(ModelInterface):
    """
    Adapter for Claude models using the Claude CLI.
    
    This adapter maintains compatibility with the existing Claude CLI
    while providing the new standardized interface for model interactions.
    """
    
    # Claude model pricing (approximate, as of 2025)
    PRICING = {
        'claude-3-haiku-20240307': {'input': 0.00025, 'output': 0.00125},
        'claude-3-sonnet-20240229': {'input': 0.003, 'output': 0.015},
        'claude-3-opus-20240229': {'input': 0.015, 'output': 0.075},
        'claude-3.5-sonnet-20240620': {'input': 0.003, 'output': 0.015},
        'claude-3.5-sonnet-20241022': {'input': 0.003, 'output': 0.015},
        'claude-3.5-haiku-20241022': {'input': 0.001, 'output': 0.005},
        # Default fallback pricing
        'default': {'input': 0.003, 'output': 0.015}
    }
    
    def __init__(self, config: ModelConfig):
        """
        Initialize Claude adapter.
        
        Args:
            config: Model configuration
        """
        super().__init__(config)
        self.claude_cli = "/Users/pentester/.claude/local/claude"  # Full path to Claude CLI
        self.pipeline_dir = Path(__file__).parent.parent.parent
        
        # Map common model names to Claude CLI model identifiers
        self.model_mapping = {
            # Primary CLI model names (Claude 4)
            'claude': 'sonnet',  # Default to sonnet (Claude 4 Sonnet)
            'sonnet': 'sonnet',  # Claude 4 Sonnet
            'haiku': 'haiku',   # Claude 4 Haiku
            'opus': 'opus',     # Claude 4 Opus
            
            # Legacy API model names (for backward compatibility)
            'claude-3-haiku': 'haiku',
            'claude-3-sonnet': 'sonnet',
            'claude-3-opus': 'opus',
            'claude-3.5-sonnet': 'sonnet',  # Maps to current sonnet
            'claude-3.5-haiku': 'haiku',
        }
        
        self.cli_model = self._get_cli_model_name()
        
        # Episode context path storage (for summary.md file reference)
        self.episode_context_path = None  # Path to episode summary.md file
        
        logger.info(f"Claude adapter initialized: {self.model_name} -> {self.cli_model}")
    
    def _get_cli_model_name(self) -> str:
        """Get the Claude CLI model name from config."""
        return self.model_mapping.get(self.model_name, 'sonnet')
    
    def set_episode_context(self, episode_context_path: Optional[str]):
        """
        Set the episode context file path for use in Claude CLI calls.
        
        This allows the adapter to add episode summary.md as an @ file reference
        when invoking Claude CLI, providing episode-specific context alongside
        the specialized CLAUDE.md instructions.
        
        Args:
            episode_context_path: Path to episode summary.md file, or None to clear
        """
        if episode_context_path and Path(episode_context_path).exists():
            self.episode_context_path = Path(episode_context_path).resolve()
            logger.info(f"Episode context set: {self.episode_context_path}")
        else:
            self.episode_context_path = None
            logger.debug("Episode context cleared")
    
    async def generate(self, 
                      prompt: str,
                      context: Optional[str] = None,
                      mode: str = "default") -> ModelResponse:
        """
        Generate text using Claude via CLI.
        
        Args:
            prompt: The prompt to send to Claude
            context: Optional context (CLAUDE.md file path or content)
            mode: Operation mode
            
        Returns:
            ModelResponse with generated content
        """
        start_time = time.time()
        
        try:
            # For summarize and respond modes, don't add MODE: prefix - the specialized CLAUDE.md handles it
            if mode in ['summarize', 'respond']:
                prepared_prompt = prompt
            else:
                # Prepare the prompt for the specific mode
                prepared_prompt = self.prepare_prompt_for_mode(prompt, mode)
            
            # Call Claude CLI
            response_text = await self._call_claude_cli(prepared_prompt, context, mode)
            
            # Calculate metrics
            latency_ms = int((time.time() - start_time) * 1000)
            input_tokens = len(prepared_prompt) // 4  # Rough estimate
            output_tokens = len(response_text) // 4  # Rough estimate
            cost = self.estimate_cost(input_tokens, output_tokens)
            
            return ModelResponse(
                content=response_text,
                tokens_used=input_tokens + output_tokens,
                cost_estimate=cost,
                model_name=self.model_name,
                latency_ms=latency_ms,
                metadata={
                    'mode': mode,
                    'cli_model': self.cli_model,
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens
                }
            )
            
        except subprocess.TimeoutExpired as e:
            raise ModelTimeoutException(f"Claude CLI timeout: {e}")
        except Exception as e:
            raise ModelException(f"Claude generation failed: {e}")
    
    async def batch_generate(self,
                            prompts: List[str],
                            context: Optional[str] = None,
                            mode: str = "default") -> List[ModelResponse]:
        """
        Generate responses for multiple prompts.
        
        For Claude, we'll process sequentially to avoid rate limiting,
        but this could be optimized for parallel processing in the future.
        """
        results = []
        
        for prompt in prompts:
            try:
                response = await self.generate(prompt, context, mode)
                results.append(response)
            except Exception as e:
                # Create error response for failed prompts
                error_response = ModelResponse(
                    content="",
                    tokens_used=0,
                    cost_estimate=0.0,
                    model_name=self.model_name,
                    latency_ms=0,
                    metadata={'error': str(e)}
                )
                results.append(error_response)
        
        return results
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost for Claude API usage.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Estimated cost in USD
        """
        # Get pricing for this specific model or use default
        pricing = self.PRICING.get(self.model_name, self.PRICING['default'])
        
        input_cost = (input_tokens / 1000) * pricing['input']
        output_cost = (output_tokens / 1000) * pricing['output']
        
        return input_cost + output_cost
    
    def get_context_limit(self) -> int:
        """
        Get Claude's context limit.
        
        Most Claude models have a 200k token context limit.
        """
        return self.config.context_limit or 200000
    
    def validate_availability(self) -> bool:
        """
        Check if Claude CLI is available and working.
        
        Returns:
            True if Claude CLI is available
        """
        try:
            result = subprocess.run(
                [self.claude_cli, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def supports_mode(self, mode: str) -> bool:
        """
        Claude supports all operation modes.
        """
        return True
    
    def prepare_prompt_for_mode(self, prompt: str, mode: str) -> str:
        """
        Prepare prompt with Claude-specific mode instructions.
        """
        # Use the base implementation but could be customized for Claude
        return super().prepare_prompt_for_mode(prompt, mode)
    
    async def _call_claude_cli(self, 
                              prompt: str, 
                              context: Optional[str] = None,
                              mode: str = "default") -> str:
        """
        Call Claude CLI with the prepared prompt and context.
        
        Args:
            prompt: The prompt to send
            context: Optional context file path or content
            mode: Operation mode for specialized context
            
        Returns:
            Claude's response text
        """
        temp_prompt = None
        temp_transcript = None
        try:
            # Get working directory for stage - this allows Claude CLI to pick up CLAUDE.md automatically
            working_dir = self._get_stage_working_directory(mode)
            
            # Special handling for summarize mode
            if mode == "summarize":
                # For summarize mode, we expect the prompt to contain a path to the transcript file
                # Look for @/path/to/transcript.txt pattern in the prompt
                import re
                transcript_path_match = re.search(r'@([^\s]+transcript\.txt)', prompt)
                
                if transcript_path_match:
                    # Prompt already has @ reference to transcript file, use as-is
                    temp_prompt = self.pipeline_dir / f".temp_prompt_{mode}_{int(time.time())}.txt"
                    temp_prompt.write_text(prompt)
                    logger.info(f"Created prompt file with @ reference: {temp_prompt} ({len(prompt)} chars)")
                    
                    # Log prompt content for debugging @ symbol issues
                    if '@' in prompt:
                        at_count = prompt.count('@')
                        logger.info(f"Prompt contains {at_count} @ symbols")
                        if at_count > 1:
                            logger.warning(f"Multiple @ symbols detected - Claude CLI may interpret these as file references")
                            # Show the lines with @ symbols
                            for line_num, line in enumerate(prompt.split('\n'), 1):
                                if '@' in line:
                                    logger.debug(f"  Line {line_num}: {line[:100]}..." if len(line) > 100 else f"  Line {line_num}: {line}")
                else:
                    # Old style - try to extract embedded transcript (for backward compatibility)
                    logger.debug(f"Summarize mode prompt length: {len(prompt)} chars")
                    transcript_match = re.search(r'EPISODE TRANSCRIPT:\n(.*?)\n\nGenerate:', prompt, re.DOTALL)
                    if transcript_match:
                        transcript_content = transcript_match.group(1)
                        
                        # Write transcript to a separate file
                        temp_transcript = self.pipeline_dir / f".temp_transcript_{int(time.time())}.txt"
                        temp_transcript.write_text(transcript_content)
                        logger.info(f"Created temp transcript file: {temp_transcript} ({len(transcript_content)} chars)")
                        
                        # Create a simple prompt that references the transcript file
                        simple_prompt = f"""Stay in your role and output in the exact format shown in CLAUDE.md.

Summarize this transcript: @{temp_transcript}"""
                        
                        # Write the simple prompt to temp file
                        temp_prompt = self.pipeline_dir / f".temp_prompt_{mode}_{int(time.time())}.txt"
                        temp_prompt.write_text(simple_prompt)
                        logger.info(f"Created simplified prompt file: {temp_prompt} ({len(simple_prompt)} chars)")
                    else:
                        # Fallback - use original prompt
                        temp_prompt = self.pipeline_dir / f".temp_prompt_{mode}_{int(time.time())}.txt"
                        temp_prompt.write_text(prompt)
                        logger.info(f"Created temp prompt file: {temp_prompt} ({len(prompt)} chars)")
            else:
                # For non-summarize modes, use the prompt as-is
                temp_prompt = self.pipeline_dir / f".temp_prompt_{mode}_{int(time.time())}.txt"
                temp_prompt.write_text(prompt)
                logger.info(f"Created temp prompt file: {temp_prompt} ({len(prompt)} chars)")
            
            # Build Claude CLI command with MCP config to prevent MCP usage
            # Use minimal MCP config file to avoid any MCP server connections
            mcp_config_path = self.pipeline_dir / "minimal-mcp-config.json"
            
            # For respond mode, pass prompt via stdin to avoid file analysis
            if mode == 'respond':
                cmd = [
                    self.claude_cli,
                    "--strict-mcp-config",  # Prevent loading user's MCP config
                    "--mcp-config", str(mcp_config_path),  # Use our minimal config
                    "--dangerously-skip-permissions",  # Skip permission prompts for @ references
                    "--model", self.cli_model,
                    "--print"
                    # No file reference - will pass via stdin
                ]
                use_stdin = True
                stdin_content = prompt  # Use the prompt directly (episode context included in prompt text)
            else:
                # For other modes, use file reference
                cmd = [
                    self.claude_cli,
                    "--strict-mcp-config",  # Prevent loading user's MCP config
                    "--mcp-config", str(mcp_config_path),  # Use our minimal config
                    "--dangerously-skip-permissions",  # Skip permission prompts for @ references
                    "--model", self.cli_model,
                    "--print",
                    f"@{temp_prompt}"  # Use @ prefix to indicate file reference
                ]
                use_stdin = False
                stdin_content = None
            
            # Add temperature if specified
            if self.config.temperature != 0.3:  # Claude CLI default
                cmd.extend(["--temperature", str(self.config.temperature)])
            
            # Log the command and working directory for debugging
            logger.info(f"Claude CLI command: {' '.join(cmd)}")
            logger.info(f"Working directory: {working_dir}")
            logger.info(f"CLI model: {self.cli_model}")
            if self.episode_context_path:
                logger.debug(f"Episode context available: {self.episode_context_path} (referenced in prompt)")
            if use_stdin:
                logger.info(f"Using stdin for prompt ({len(stdin_content)} chars)")
            else:
                logger.info(f"Using file reference: @{temp_prompt}")
            
            # Use longer timeout for summarization (20 minutes) vs other modes (5 minutes)
            timeout_seconds = 1200 if mode == "summarize" else self.config.timeout_seconds
            logger.info(f"Using timeout: {timeout_seconds} seconds for mode: {mode}")
            
            # Execute command from stage directory (so Claude CLI picks up local CLAUDE.md)
            logger.info("Executing Claude CLI...")
            if use_stdin:
                # Pass prompt via stdin for respond mode
                result = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=working_dir
                )
                try:
                    stdout, stderr = await asyncio.wait_for(
                        result.communicate(stdin_content.encode()), 
                        timeout=timeout_seconds
                    )
                except asyncio.TimeoutError:
                    logger.error(f"Claude CLI timeout after {timeout_seconds} seconds for mode: {mode}")
                    # Try to kill the process
                    try:
                        result.kill()
                        await result.wait()
                    except:
                        pass
                    raise ModelTimeoutException(f"Claude CLI timeout after {timeout_seconds} seconds.")
            else:
                # Use file reference for other modes
                result = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=working_dir
                )
                try:
                    stdout, stderr = await asyncio.wait_for(
                        result.communicate(), 
                        timeout=timeout_seconds
                    )
                except asyncio.TimeoutError:
                    logger.error(f"Claude CLI timeout after {timeout_seconds} seconds for mode: {mode}")
                    # Try to kill the process
                    try:
                        result.kill()
                        await result.wait()
                    except:
                        pass
                    raise ModelTimeoutException(f"Claude CLI timeout after {timeout_seconds} seconds. Consider using a smaller transcript or increasing timeout.")
            
            if result.returncode != 0:
                error_msg = stderr.decode() if stderr else f"Process exited with code {result.returncode}"
                logger.error(f"Claude CLI error: {error_msg}")
                raise ModelException(f"Claude CLI failed: {error_msg}")
            
            response = stdout.decode().strip()
            logger.info(f"Claude CLI response length: {len(response)} characters")
            
            # Log the first part of response for debugging (especially for short responses)
            if len(response) < 100:
                logger.warning(f"Claude CLI returned very short response: '{response}'")
            else:
                logger.debug(f"Claude CLI response preview: {response[:200]}...")
            
            # Check for common error patterns that might indicate file reference issues
            if len(response) < 50 and ('not found' in response.lower() or 'error' in response.lower() or 'failed' in response.lower()):
                logger.error(f"Claude CLI may have encountered an error. Response: '{response}'")
                logger.error(f"This could be due to @ symbols being interpreted as file references")
            
            return response
            
        except asyncio.TimeoutError:
            logger.error("Claude CLI timeout")
            raise ModelTimeoutException("Claude CLI request timed out")
        except Exception as e:
            logger.error(f"Error calling Claude CLI: {e}")
            raise ModelException(f"Claude CLI execution failed: {e}")
        finally:
            # Always clean up temp files
            if temp_prompt and temp_prompt.exists():
                temp_prompt.unlink(missing_ok=True)
            if temp_transcript and temp_transcript.exists():
                temp_transcript.unlink(missing_ok=True)
    
    def _get_context_files(self, context: Optional[str], mode: str) -> List[str]:
        """
        Get appropriate context files for Claude CLI.
        
        Args:
            context: Context file path or content
            mode: Operation mode for specialized context
            
        Returns:
            List of context file paths
        """
        context_files = []
        
        # Add specialized CLAUDE.md based on mode
        specialized_context = self._get_specialized_context_file(mode)
        if specialized_context:
            context_files.append(str(specialized_context))
        else:
            # Fallback to master CLAUDE.md
            master_context = self.pipeline_dir / "CLAUDE.md"
            if master_context.exists():
                context_files.append(str(master_context))
        
        # Add episode-specific context if provided
        if context:
            # Check if context looks like a file path (short and no newlines)
            if len(context) < 500 and '\n' not in context and Path(context).exists():
                # Context is a file path
                context_files.append(context)
            else:
                # Context is content - write to temp file
                temp_context = self.pipeline_dir / f".temp_context_{mode}_{int(time.time())}.md"
                temp_context.write_text(context)
                context_files.append(str(temp_context))
        
        return context_files
    
    def _get_stage_working_directory(self, mode: str) -> Path:
        """
        Get the working directory for a given stage mode.
        
        Args:
            mode: Operation mode
            
        Returns:
            Path to the specialized stage directory or pipeline directory as fallback
        """
        mode_to_dir = {
            'summarize': 'summarizer',
            'classify': 'classifier',
            'respond': 'responder',
            'moderate': 'moderator'
        }
        
        if mode in mode_to_dir:
            specialized_dir = self.pipeline_dir / "specialized" / mode_to_dir[mode]
            if specialized_dir.exists():
                return specialized_dir
        
        # Fallback to pipeline directory
        return self.pipeline_dir
    
    def _get_specialized_context_file(self, mode: str) -> Optional[Path]:
        """
        Get the specialized CLAUDE.md file for a given mode.
        
        Args:
            mode: Operation mode
            
        Returns:
            Path to specialized CLAUDE.md or None
        """
        mode_to_dir = {
            'summarize': 'summarizer',
            'classify': 'classifier',
            'respond': 'responder',
            'moderate': 'moderator'
        }
        
        if mode not in mode_to_dir:
            return None
        
        specialized_dir = self.pipeline_dir / "specialized" / mode_to_dir[mode]
        specialized_file = specialized_dir / "CLAUDE.md"
        
        return specialized_file if specialized_file.exists() else None