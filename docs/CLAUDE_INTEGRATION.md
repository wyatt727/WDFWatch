# Claude Integration for WDFWatch Pipeline

## Overview
Claude has been fully integrated into the WDFWatch pipeline, allowing it to be used as an alternative to Gemini, Ollama, and OpenAI models for all pipeline tasks. Users can now select Claude for any or all of the following tasks through the Web UI at http://localhost:3000/settings/llm-models.

## Implementation Status ✅

### Completed Features
1. **Claude Summarization** - Wrapper script for transcript summarization
2. **Claude Few-shot Generation** - Native task module for generating classification examples
3. **Claude Classification** - Both wrapper and native implementations for tweet classification
4. **Claude Response Generation** - Existing implementation enhanced with proper routing
5. **Pipeline Routing** - main.py automatically routes to Claude implementations when selected
6. **Web UI Integration** - Claude appears as an option in the LLM models settings page

### Files Created/Modified

#### New Files
- `src/wdf/tasks/claude_fewshot.py` - Few-shot generation using Claude
- `scripts/claude_summarizer.py` - Wrapper for transcript summarization with Claude
- `scripts/claude_classifier.py` - Wrapper for tweet classification with Claude
- `test_claude_integration.py` - Comprehensive test suite for Claude integration

#### Modified Files
- `main.py` - Added routing logic to use Claude tasks when selected
- `tweet_classifier.py` - Added redirect to Claude wrapper when Claude is selected
- `web/lib/llm-models.ts` - Claude already listed as an option for all tasks

## How to Use Claude

### Method 1: Web UI Configuration (Recommended)
1. Navigate to http://localhost:3000/settings/llm-models
2. Select "Claude 4 Sonnet (via CLI)" for desired tasks:
   - **Summarization** - Generate podcast summaries and keywords
   - **Few-shot Generation** - Create classification examples
   - **Tweet Classification** - Score tweet relevancy
   - **Response Generation** - Generate tweet responses
3. Click "Save Configuration"
4. Run the pipeline: `python main.py`

### Method 2: Environment Variables
Set environment variables before running the pipeline:
```bash
export WDF_LLM_MODELS__SUMMARIZATION=claude
export WDF_LLM_MODELS__FEWSHOT=claude
export WDF_LLM_MODELS__CLASSIFICATION=claude
export WDF_LLM_MODELS__RESPONSE=claude
python main.py
```

### Method 3: Database Configuration
The Web UI saves selections to the PostgreSQL database, which are automatically loaded by the pipeline when `WDF_WEB_MODE=true`.

## Prerequisites

### Claude CLI Setup
For Claude to work, you need the Claude CLI installed and configured. The pipeline expects a `claude` command to be available in your PATH.

#### Setting up Claude CLI Alias
Create an alias that wraps the Claude Code CLI:
```bash
# Add to ~/.bashrc or ~/.zshrc
alias claude='claude-code --pipe --no-markdown --temperature 0.7'
```

Or create a wrapper script:
```bash
#!/bin/bash
# Save as /usr/local/bin/claude
claude-code --pipe --no-markdown --temperature 0.7 "$@"
```

## How It Works

### Routing Logic
When the pipeline runs, it checks the selected model for each task:

1. **Summarization**: If `claude` is selected, uses `scripts/claude_summarizer.py` instead of `transcript_summarizer.js`
2. **Few-shot**: If `claude` is selected, uses `src/wdf/tasks/claude_fewshot.py` instead of `fewshot.py`
3. **Classification**: If `claude` is selected, uses `src/wdf/tasks/claude_classify.py` or wrapper
4. **Response**: If `claude` is selected, uses `src/wdf/tasks/claude.py` (already existed)

### Fallback Behavior
If Claude CLI is not available or fails:
- Wrapper scripts will log an error and fail gracefully
- Pipeline can be configured to fall back to default models
- Mock mode available for testing without Claude CLI

## Testing

Run the integration test suite:
```bash
python test_claude_integration.py
```

Expected output:
- ✅ All wrapper scripts and modules exist
- ✅ main.py has proper routing logic
- ✅ Claude can be selected via environment variables
- ⚠️ Claude CLI availability depends on local setup

## Advanced Features

### Claude-Specific Capabilities
When using Claude for classification, you can leverage:
- **Direct reasoning** without few-shot examples (claude_classify.py)
- **Episode memory** for context-aware classification
- **Batch processing** for efficient API usage

### Mixed Model Usage
You can mix and match models for different tasks:
```bash
export WDF_LLM_MODELS__SUMMARIZATION=gemini-2.5-pro  # Use Gemini for summaries
export WDF_LLM_MODELS__FEWSHOT=claude                 # Use Claude for examples
export WDF_LLM_MODELS__CLASSIFICATION=gemma3n:e4b     # Use Ollama for classification
export WDF_LLM_MODELS__RESPONSE=claude                # Use Claude for responses
```

## Troubleshooting

### Claude CLI Not Found
If you get "Claude CLI not found" errors:
1. Ensure Claude Code is installed
2. Create the `claude` alias or wrapper script
3. Verify with: `which claude`

### Permission Denied
If wrapper scripts fail with permission errors:
```bash
chmod +x scripts/claude_summarizer.py
chmod +x scripts/claude_classifier.py
```

### Model Not Available
If Claude doesn't appear in the Web UI:
1. Check that `web/lib/llm-models.ts` includes Claude options
2. Restart the Next.js dev server: `npm run dev`
3. Clear browser cache and reload

## Performance Considerations

### API Rate Limits
Claude has different rate limits than other providers:
- Consider using batch processing for classification
- Implement retry logic for rate limit errors
- Monitor usage through Claude's dashboard

### Cost Optimization
- Claude may be more expensive than free alternatives (Gemini, Ollama)
- Use Claude selectively for tasks that benefit most from its capabilities
- Consider using Claude for response generation and cheaper models for classification

## Future Enhancements

Potential improvements for Claude integration:
1. **Native Claude API** - Direct API integration instead of CLI
2. **Streaming Support** - Real-time response streaming
3. **Context Windows** - Optimize for Claude's larger context window
4. **Custom Prompts** - Claude-specific prompt templates
5. **Error Recovery** - Automatic fallback to alternative models
6. **Usage Tracking** - Monitor Claude API usage and costs

## Support

For issues with Claude integration:
1. Run the test suite: `python test_claude_integration.py`
2. Check logs in `logs/pipeline.log`
3. Verify Claude CLI is working: `echo "test" | claude -p "Say hello"`
4. Review this documentation for configuration steps

## Conclusion

Claude is now fully integrated into the WDFWatch pipeline and can be used for all LLM tasks. The implementation maintains backward compatibility while providing the flexibility to use Claude's advanced capabilities when needed.