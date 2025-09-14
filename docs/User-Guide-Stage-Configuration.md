# User Guide: Pipeline Stage Configuration

## Overview

The WDFWatch pipeline now supports flexible configuration where you can:
- **Enable or disable individual pipeline stages**
- **Choose different LLM models for different tasks**
- **Create custom workflows** for different use cases

This guide will walk you through how to use these features effectively.

## Accessing Stage Configuration

1. Navigate to the **Settings** page in the Web UI
2. Click on **LLM Models** in the settings menu
3. You'll see two main sections:
   - **LLM Model Configuration**: Choose models for each task
   - **Pipeline Stage Configuration**: Enable/disable stages

## Understanding Pipeline Stages

### Stage Types and Purposes

| Stage | Purpose | Required | Typical Use |
|-------|---------|----------|-------------|
| **Summarization** | Analyzes podcast transcripts and extracts key information | ✅ Yes | Always needed |
| **Few-shot Generation** | Creates example tweets for training classification | ❌ No | Traditional ML workflows |
| **Tweet Scraping** | Discovers relevant tweets using keywords | ✅ Yes | Always needed |
| **Classification** | Scores tweets for relevance (0.00 to 1.00) | ✅ Yes | Always needed |
| **Response Generation** | Creates engaging replies to relevant tweets | ❌ No | Optional |
| **Quality Moderation** | Reviews and approves generated responses | ❌ No | Optional quality check |

### Stage Dependencies

Some stages depend on others:
- **Moderation** requires **Response Generation** to be enabled
- **Response Generation** works best with **Classification** enabled
- **Classification** and **Response** need **Scraping** to have tweets to process

The UI will show warnings or errors if dependencies aren't satisfied.

## Common Configuration Scenarios

### 1. Claude Pipeline (Recommended)

**Best for:** Most users who want high-quality results with minimal setup

**Configuration:**
- **Stages:** Enable Summarization, Scraping, Classification, Response. Disable Few-shot and Moderation.
- **Models:** Use Claude for all tasks

**Why this works:**
- Claude doesn't need few-shot examples for classification
- Direct classification is more accurate and faster
- Claude provides excellent quality across all tasks

**Steps:**
1. In **Pipeline Stage Configuration**, ensure:
   - ✅ Summarization: Enabled
   - ❌ Few-shot Generation: Disabled
   - ✅ Tweet Scraping: Enabled
   - ✅ Classification: Enabled
   - ✅ Response Generation: Enabled
   - ❌ Quality Moderation: Disabled

2. In **LLM Model Configuration**, set all tasks to "Claude 4 Sonnet (via CLI)"

### 2. Hybrid Pipeline (Cost-Optimized)

**Best for:** Users who want to optimize costs by using each model's strengths

**Configuration:**
- **Models:** Mix free and specialized models
- **Stages:** Enable Few-shot for better classification

**Steps:**
1. Set models to:
   - **Summarization:** Gemini 2.5 Pro (Free)
   - **Few-shot:** Gemini 2.5 Pro (Free)
   - **Classification:** Gemma3n (Ollama, specialized)
   - **Response:** Deepseek R1 (Ollama, good reasoning)
   - **Moderation:** Claude (excellent quality assessment)

2. Enable all relevant stages including Few-shot

### 3. Classification-Only Pipeline

**Best for:** Research or analysis without generating responses

**Configuration:**
- **Purpose:** Analyze tweet relevance without creating responses
- **Stages:** Enable up to Classification, disable Response and Moderation

**Steps:**
1. Disable **Response Generation** and **Moderation**
2. Choose your preferred classification model (Claude or Gemma3n)

### 4. Full Quality Pipeline

**Best for:** Maximum quality with human oversight

**Configuration:**
- **Stages:** Enable all stages including Moderation
- **Models:** Use high-quality models throughout

**Steps:**
1. Enable all stages including **Quality Moderation**
2. Use Claude or GPT-4 models for critical stages
3. Responses will require human approval before publishing

## Model Selection Guide

### When to Use Each Model

**Claude Models** (claude, sonnet, haiku, opus):
- ✅ **Best for:** All tasks, especially moderation and complex reasoning
- ✅ **Strengths:** Excellent quality, understands context well
- ❌ **Limitations:** May be slower and more expensive

**Gemini Models** (gemini-2.5-pro, gemini-2.5-flash):
- ✅ **Best for:** Summarization, few-shot generation
- ✅ **Strengths:** Free to use, good text analysis
- ❌ **Limitations:** Limited moderation capability

**Specialized Ollama Models:**
- **gemma3n:e4b**: Excellent for classification only
- **deepseek-r1:latest**: Good reasoning for response generation
- **llama3.3:70b**: General-purpose alternative to Claude

**OpenAI Models** (gpt-4o, gpt-4o-mini):
- ✅ **Best for:** General-purpose tasks, good moderation
- ✅ **Strengths:** Reliable, well-tested
- ❌ **Limitations:** Requires API key and credits

### Model Capability Warnings

The UI will warn you if a model isn't suitable for a task:
- 🟡 **Yellow warning:** Model has limited capability for this task
- 🔴 **Red warning:** Model is incompatible with this task

## Configuration Best Practices

### 1. Start Simple
Begin with the **Claude Pipeline** configuration - it's the most reliable and requires minimal tuning.

### 2. Test Your Configuration
Use the **"Test Models"** button to verify all selected models are available before saving.

### 3. Monitor Performance
After changing configuration:
- Check response quality in the Review interface
- Monitor approval rates if using moderation
- Adjust models if you see quality issues

### 4. Environment-Specific Settings

**Development:**
- Use free models (Gemini) to avoid costs
- Enable moderation for quality checking
- Disable response generation if just testing classification

**Production:**
- Use reliable models (Claude, GPT-4)
- Consider hybrid approach for cost optimization
- Enable moderation for important accounts

## Troubleshooting Common Issues

### "Required stage cannot be disabled"
Some stages (Summarization, Scraping, Classification) are required for the pipeline to function. You cannot disable these.

### "Moderation requires response generation"
You can only enable moderation if response generation is also enabled. Enable response generation first.

### "Model not suitable for task"
The selected model has limited capability for this task. Either:
- Choose a different model recommended for this task
- Accept the warning if you want to experiment

### "Model validation failed"
The selected model is not available. Check:
- Ollama is running (for Ollama models)
- API keys are configured (for Claude/OpenAI/Gemini)
- Model is installed locally (for Ollama)

### Pipeline runs but stages are skipped
Check the pipeline logs for stage enablement. Stages will be skipped if:
- The stage is disabled in configuration
- Dependencies aren't met (e.g., no responses to moderate)
- Required models aren't available

## Advanced Configuration

### Environment Variables
You can override configuration using environment variables:

```bash
# Enable/disable stages
export WDF_STAGE_FEWSHOT_ENABLED=false
export WDF_STAGE_MODERATION_ENABLED=true

# Override models
export WDF_LLM_MODEL_CLASSIFICATION=claude
export WDF_LLM_MODEL_RESPONSE=gpt-4o
```

### Programmatic Configuration
The Python pipeline automatically loads configuration from the database in web mode:

```bash
# Load configuration and run pipeline
python main.py  # (with WDF_WEB_MODE=true)
```

## Migration from CLI-Only Setup

If you were previously using the CLI-only pipeline:

1. **Backup your current settings** in environment variables or config files
2. **Configure equivalent settings** in the Web UI
3. **Test the new configuration** with a small batch
4. **Monitor results** and adjust as needed

The new system maintains backward compatibility - existing environment variables will still work if database configuration isn't available.

## Getting Help

### Validation Feedback
The UI provides real-time validation:
- ✅ **Green checkmarks:** Valid configuration
- ⚠️ **Yellow warnings:** Configuration works but may have issues
- ❌ **Red errors:** Configuration must be fixed before saving

### Configuration Examples
Use the preset configurations as starting points:
- Click **"Reset to Defaults"** to restore recommended settings
- Modify from there based on your needs

### Support Resources
- Check the **API Documentation** for technical details
- Review pipeline logs for execution details
- Test configuration changes in development first

---

## Quick Start Checklist

✅ **Step 1:** Navigate to Settings → LLM Models  
✅ **Step 2:** Choose a configuration scenario (Claude Pipeline recommended)  
✅ **Step 3:** Configure models for each enabled stage  
✅ **Step 4:** Enable/disable stages as needed  
✅ **Step 5:** Click "Test Models" to validate availability  
✅ **Step 6:** Save configuration  
✅ **Step 7:** Run pipeline and monitor results  

With stage configuration, you now have full control over your WDFWatch pipeline. Start with the recommended Claude Pipeline and customize from there based on your specific needs!