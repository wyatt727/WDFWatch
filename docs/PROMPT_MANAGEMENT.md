# Prompt Management System

This document describes the comprehensive prompt management system implemented in WDFWatch, allowing users to customize all LLM prompts and context files from the Web UI.

## Overview

The prompt management system enables users to:
- Edit all LLM prompts used throughout the pipeline
- Manage context files (podcast overview, video URLs)
- Track version history with rollback capability
- Test prompts with sample data before deployment
- Perform variable substitution in templates

## Architecture

### Database Schema

```sql
-- Prompt Templates
CREATE TABLE prompt_templates (
  id SERIAL PRIMARY KEY,
  key VARCHAR(50) UNIQUE NOT NULL,        -- e.g., 'summarization', 'classification'
  name VARCHAR(100) NOT NULL,             -- Human-readable name
  description TEXT,                       -- Optional description
  template TEXT NOT NULL,                 -- The actual prompt template
  variables JSON,                         -- List of variables used
  is_active BOOLEAN DEFAULT true,
  version INTEGER DEFAULT 1,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  created_by VARCHAR(100)
);

-- Prompt History
CREATE TABLE prompt_history (
  id SERIAL PRIMARY KEY,
  prompt_id INTEGER REFERENCES prompt_templates(id),
  version INTEGER NOT NULL,
  template TEXT NOT NULL,
  changed_by VARCHAR(100),
  change_note TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Context Files
CREATE TABLE context_files (
  id SERIAL PRIMARY KEY,
  key VARCHAR(50) UNIQUE NOT NULL,        -- e.g., 'podcast_overview'
  name VARCHAR(100) NOT NULL,
  description TEXT,
  content TEXT NOT NULL,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  updated_by VARCHAR(100)
);
```

### Prompt Keys

| Key | Task | Description |
|-----|------|-------------|
| `summarization` | Transcript Summarization | Generates episode summary and keywords |
| `fewshot_generation` | Few-shot Examples | Creates classification training examples |
| `tweet_classification` | Tweet Classification | Determines if tweets are relevant |
| `response_generation` | Response Generation | Creates engaging tweet responses |

### Context File Keys

| Key | Description | Usage |
|-----|-------------|-------|
| `podcast_overview` | General WDF podcast description | Included in all prompts |
| `video_url` | Latest episode YouTube URL | Used in tweet responses |

## Web UI Features

### Prompt Editor (`/settings/prompts`)

1. **Template Editing**
   - Syntax-highlighted editor
   - Variable extraction and validation
   - Real-time variable detection

2. **Variable System**
   - Simple substitution: `{variable}`
   - Conditional substitution: `{condition ? 'true text' : 'false text'}`
   - Automatic variable detection

3. **Testing & Preview**
   - Test prompts with sample data
   - Preview final output
   - Character count for tweet responses

4. **Version History**
   - Track all changes
   - Compare versions
   - One-click rollback
   - Change notes

### Context File Editor

- Edit podcast overview
- Update video URLs
- Character limits
- Usage information

## Python Integration

### Loading Prompts (`scripts/load_prompts.py`)

```bash
# Export prompts to environment variables
eval $(python scripts/load_prompts.py)

# Show current configuration
python scripts/load_prompts.py --show

# Test database connection
python scripts/load_prompts.py --test
```

### Environment Variables

Prompts are exported as:
- `WDF_PROMPT_SUMMARIZATION`
- `WDF_PROMPT_FEWSHOT_GENERATION`
- `WDF_PROMPT_TWEET_CLASSIFICATION`
- `WDF_PROMPT_RESPONSE_GENERATION`

Context files are exported as:
- `WDF_CONTEXT_PODCAST_OVERVIEW`
- `WDF_CONTEXT_VIDEO_URL`

### Pipeline Integration

All pipeline tasks have been updated to:
1. Check for database prompts via environment variables
2. Fall back to hardcoded defaults if not available
3. Support variable substitution

Example from `tweet_classifier.py`:
```python
if build_classification_prompt:
    system_prompt = build_classification_prompt(topic_summary)
else:
    # Fallback to hardcoded prompt
    system_prompt = DEFAULT_SYSTEM_MSG
```

## API Endpoints

### Prompt Management

- `GET /api/settings/prompts` - List all prompts
- `POST /api/settings/prompts` - Create new prompt
- `PUT /api/settings/prompts` - Update prompt
- `DELETE /api/settings/prompts?id={id}` - Deactivate prompt

### Prompt History

- `GET /api/settings/prompts/{id}/history` - Get version history
- `POST /api/settings/prompts/{id}/history` - Restore previous version

### Context Files

- `GET /api/settings/context-files` - List all context files
- `POST /api/settings/context-files` - Create context file
- `PUT /api/settings/context-files` - Update context file
- `DELETE /api/settings/context-files?id={id}` - Deactivate context file

### Testing

- `POST /api/settings/prompts/test` - Test prompt with sample data

## Usage Examples

### Editing a Prompt

1. Navigate to Settings → Prompts & Context
2. Select a prompt template from the list
3. Edit the template in the editor
4. Test with sample data
5. Save changes

### Using Variables

```text
You are a tweet classifier for the '{podcast_name}' podcast.
{is_first_chunk ? 'Start with a comprehensive summary.' : 'Continue the analysis.'}

Context:
{overview}

Task: {task_description}
```

### Restoring a Previous Version

1. Click "History" on any prompt
2. Select a previous version
3. Click "Compare with Current" to see differences
4. Click "Restore This Version" to rollback

## Security Considerations

- All prompts are stored in PostgreSQL
- Access controlled via Web UI authentication
- Change history tracked for audit purposes
- Environment variables used for Python integration

## Migration from Hardcoded Prompts

The system maintains full backward compatibility:
1. If database prompts are not available, hardcoded defaults are used
2. Web mode (`WDF_WEB_MODE=true`) automatically loads prompts from database
3. File-based mode continues to work with hardcoded prompts

## Best Practices

1. **Test Before Save**: Always test prompts with sample data
2. **Use Descriptive Change Notes**: Document why changes were made
3. **Monitor Character Limits**: Especially for tweet responses
4. **Version Control**: Use history feature to track changes
5. **Variable Naming**: Use clear, descriptive variable names

## Troubleshooting

### Prompts Not Loading

```bash
# Check if prompts are loaded
python scripts/load_prompts.py --show

# Test database connection
python scripts/load_prompts.py --test

# Verify environment variables
env | grep WDF_PROMPT
```

### Variable Substitution Issues

- Ensure variables are properly formatted: `{variable_name}`
- Check that all required variables are provided
- Use the test feature to preview output

### Performance

- Prompts are loaded once at pipeline startup
- Cached in environment variables
- No runtime database queries

## Future Enhancements

1. **A/B Testing**: Test different prompt versions
2. **Metrics Integration**: Track prompt performance
3. **Import/Export**: Share prompt configurations
4. **Template Library**: Pre-built prompt templates
5. **Multi-language Support**: Prompts in different languages