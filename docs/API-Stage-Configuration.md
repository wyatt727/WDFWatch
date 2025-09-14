# API Documentation: Stage Configuration

## Overview

The Stage Configuration API allows users to configure pipeline stages and LLM models through the Web UI. This enables flexible pipeline execution where individual stages can be enabled/disabled and different models can be assigned to different tasks.

## Endpoints

### Pipeline Stages Configuration

#### GET /api/settings/pipeline-stages

Retrieve current pipeline stage configuration.

**Response:**
```json
{
  "config": {
    "summarization": {
      "enabled": true,
      "required": true
    },
    "fewshot": {
      "enabled": false,
      "required": false
    },
    "scraping": {
      "enabled": true,
      "required": true
    },
    "classification": {
      "enabled": true,
      "required": true
    },
    "response": {
      "enabled": true,
      "required": false
    },
    "moderation": {
      "enabled": false,
      "required": false
    }
  }
}
```

**Response Fields:**
- `enabled` (boolean): Whether the stage is currently enabled
- `required` (boolean): Whether the stage is required and cannot be disabled

#### PUT /api/settings/pipeline-stages

Update pipeline stage configuration.

**Request Body:**
```json
{
  "summarization": {
    "enabled": true,
    "required": true
  },
  "fewshot": {
    "enabled": false,
    "required": false
  },
  "scraping": {
    "enabled": true,
    "required": true
  },
  "classification": {
    "enabled": true,
    "required": true
  },
  "response": {
    "enabled": true,
    "required": false
  },
  "moderation": {
    "enabled": false,
    "required": false
  }
}
```

**Success Response:**
```json
{
  "success": true,
  "message": "Pipeline stage configuration updated successfully"
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Required stage 'summarization' cannot be disabled",
  "validation_errors": [
    "Required stage 'summarization' cannot be disabled",
    "Moderation requires response generation to be enabled"
  ]
}
```

#### POST /api/settings/pipeline-stages/reset

Reset pipeline stage configuration to defaults.

**Success Response:**
```json
{
  "success": true,
  "message": "Pipeline stage configuration reset to defaults",
  "config": {
    "summarization": {"enabled": true, "required": true},
    "fewshot": {"enabled": false, "required": false},
    "scraping": {"enabled": true, "required": true},
    "classification": {"enabled": true, "required": true},
    "response": {"enabled": true, "required": false},
    "moderation": {"enabled": false, "required": false}
  }
}
```

### LLM Models Configuration

#### GET /api/settings/llm-models

Retrieve current LLM model configuration and available models.

**Response:**
```json
{
  "config": {
    "summarization": "gemini-2.5-pro",
    "fewshot": "gemini-2.5-pro",
    "classification": "gemma3n:e4b",
    "response": "deepseek-r1:latest",
    "moderation": "claude"
  },
  "available": {
    "summarization": [
      {
        "value": "claude",
        "label": "Claude 4 Sonnet (via CLI)",
        "provider": "claude",
        "description": "Claude 4 Sonnet via claude CLI - comprehensive analysis (default)"
      },
      {
        "value": "gemini-2.5-pro",
        "label": "Gemini 2.5 Pro (Free)",
        "provider": "gemini",
        "description": "Via gemini-cli npm package - comprehensive analysis"
      }
    ],
    "classification": [
      {
        "value": "claude",
        "label": "Claude 4 Sonnet (via CLI)",
        "provider": "claude",
        "description": "Claude 4 Sonnet via claude CLI - highly accurate classification"
      },
      {
        "value": "gemma3n:e4b",
        "label": "Gemma3n (e4b)",
        "provider": "ollama",
        "description": "Optimized for classification tasks"
      }
    ],
    "moderation": [
      {
        "value": "claude",
        "label": "Claude 4 Sonnet (via CLI)",
        "provider": "claude",
        "description": "Claude 4 Sonnet via claude CLI - excellent for quality evaluation"
      },
      {
        "value": "gpt-4o",
        "label": "GPT-4o",
        "provider": "openai",
        "description": "Superior moderation and quality assessment"
      }
    ]
  }
}
```

#### PUT /api/settings/llm-models

Update LLM model configuration.

**Request Body:**
```json
{
  "summarization": "claude",
  "fewshot": "claude",
  "classification": "gemma3n:e4b",
  "response": "deepseek-r1:latest",
  "moderation": "claude"
}
```

**Success Response:**
```json
{
  "success": true,
  "message": "LLM model configuration updated successfully"
}
```

#### POST /api/settings/llm-models/validate

Validate model availability.

**Request Body:**
```json
{
  "model": "claude",
  "provider": "claude"
}
```

**Success Response:**
```json
{
  "valid": true,
  "message": "Model is available and ready to use"
}
```

**Error Response:**
```json
{
  "valid": false,
  "message": "Model 'claude' is not available. Please check configuration."
}
```

## Stage Configuration Schema

### Stage Types

1. **summarization**: Generates podcast summaries and extracts keywords
   - Required: Yes
   - Default Model: `gemini-2.5-pro`
   - Capabilities: Text analysis, keyword extraction

2. **fewshot**: Creates example tweets for classification training
   - Required: No (typically disabled for Claude pipeline)
   - Default Model: `gemini-2.5-pro`
   - Capabilities: Example generation

3. **scraping**: Discovers relevant tweets using keywords
   - Required: Yes
   - No model required (uses Twitter API)
   - Capabilities: Tweet discovery, API integration

4. **classification**: Scores tweet relevancy from 0.00 to 1.00
   - Required: Yes
   - Default Model: `gemma3n:e4b`
   - Capabilities: Binary classification, scoring

5. **response**: Generates engaging responses to relevant tweets
   - Required: No
   - Default Model: `deepseek-r1:latest`
   - Capabilities: Response generation, context awareness

6. **moderation**: Evaluates response quality and appropriateness
   - Required: No (optional quality check)
   - Default Model: `claude`
   - Capabilities: Quality assessment, approval workflow

### Stage Dependencies

- **Response Generation** benefits from **Classification** (warning if disabled)
- **Moderation** requires **Response Generation** (error if response disabled)
- **Classification** and **Response** benefit from **Scraping** (warning if scraping disabled)

### Model Capabilities

Models have different capabilities for different tasks:

```typescript
type ModelCapabilities = {
  canSummarize: boolean
  canGenerateFewshots: boolean
  canClassify: boolean
  canRespond: boolean
  canModerate: boolean
  qualityRating: 'excellent' | 'good' | 'fair' | 'poor'
}
```

**Claude Models** (excellent for all tasks):
- `claude`, `sonnet`, `haiku`, `opus`
- Full capability across all pipeline stages

**Gemini Models** (good for text generation):
- `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-pro`
- Strong in summarization, fewshot, classification, response
- Limited moderation capability

**OpenAI Models** (good for most tasks):
- `gpt-4o`, `gpt-4-turbo`, `gpt-4o-mini`, `gpt-3.5-turbo`
- Strong general-purpose capabilities
- Good moderation support

**Ollama Models** (specialized):
- `gemma3n:e4b`: Excellent for classification only
- `deepseek-r1:latest`: Strong reasoning for responses
- `llama3.3:70b`: Good general capability
- Limited moderation capability

## Usage Examples

### Claude Pipeline Configuration

Typical configuration for Claude pipeline (no few-shot needed):

```bash
curl -X PUT http://localhost:3000/api/settings/pipeline-stages \
  -H "Content-Type: application/json" \
  -d '{
    "summarization": {"enabled": true, "required": true},
    "fewshot": {"enabled": false, "required": false},
    "scraping": {"enabled": true, "required": true},
    "classification": {"enabled": true, "required": true},
    "response": {"enabled": true, "required": false},
    "moderation": {"enabled": false, "required": false}
  }'

curl -X PUT http://localhost:3000/api/settings/llm-models \
  -H "Content-Type: application/json" \
  -d '{
    "summarization": "claude",
    "fewshot": "claude",
    "classification": "claude",
    "response": "claude",
    "moderation": "claude"
  }'
```

### Hybrid Pipeline Configuration

Configuration using each model's strengths:

```bash
curl -X PUT http://localhost:3000/api/settings/llm-models \
  -H "Content-Type: application/json" \
  -d '{
    "summarization": "gemini-2.5-pro",
    "fewshot": "gemini-2.5-pro",
    "classification": "gemma3n:e4b",
    "response": "deepseek-r1:latest",
    "moderation": "claude"
  }'
```

### Minimal Pipeline Configuration

Classification-only pipeline:

```bash
curl -X PUT http://localhost:3000/api/settings/pipeline-stages \
  -H "Content-Type: application/json" \
  -d '{
    "summarization": {"enabled": true, "required": true},
    "fewshot": {"enabled": false, "required": false},
    "scraping": {"enabled": true, "required": true},
    "classification": {"enabled": true, "required": true},
    "response": {"enabled": false, "required": false},
    "moderation": {"enabled": false, "required": false}
  }'
```

## Environment Variable Support

Pipeline stages can also be configured via environment variables:

```bash
# Stage enablement
export WDF_STAGE_SUMMARIZATION_ENABLED=true
export WDF_STAGE_FEWSHOT_ENABLED=false
export WDF_STAGE_SCRAPING_ENABLED=true
export WDF_STAGE_CLASSIFICATION_ENABLED=true
export WDF_STAGE_RESPONSE_ENABLED=true
export WDF_STAGE_MODERATION_ENABLED=false

# Model configuration
export WDF_LLM_MODEL_SUMMARIZATION=claude
export WDF_LLM_MODEL_CLASSIFICATION=gemma3n:e4b
export WDF_LLM_MODEL_RESPONSE=deepseek-r1:latest
export WDF_LLM_MODEL_MODERATION=claude
```

## Error Codes

| Code | Description |
|------|-------------|
| 400  | Bad Request - Invalid configuration data |
| 422  | Validation Error - Stage dependency violations |
| 500  | Internal Server Error - Database or system error |

## Validation Rules

1. **Required stages cannot be disabled**
   - `summarization`, `scraping`, `classification` are always required

2. **Stage dependencies must be satisfied**
   - Moderation requires response generation
   - Response generation benefits from classification (warning)

3. **Model assignments must be valid**
   - Unknown models generate warnings
   - Incompatible models generate capability warnings

4. **Configuration consistency**
   - All stage configurations must be provided
   - Model assignments must match available options

## Python Integration

The Python pipeline automatically loads configuration from the database in web mode:

```python
# Automatic loading in web mode
python main.py  # (with WDF_WEB_MODE=true)

# Manual loading
eval $(python web/scripts/load_llm_config.py)
eval $(python web/scripts/load_stage_config.py)
```

Stage checking in Python:

```python
from claude_pipeline.core.model_factory import ModelFactory

factory = ModelFactory()

# Check if stage is enabled
if factory.is_stage_enabled('fewshot'):
    # Stage is enabled, create model
    model = factory.create_model_for_task('fewshot')
else:
    # Stage disabled, skip
    model = None
```