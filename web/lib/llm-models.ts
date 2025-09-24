/**
 * LLM Model Configuration
 * 
 * Available models and default configurations for each pipeline task
 * Used by: /api/settings/llm-models, LLM settings UI
 */

// Available models for each task type
export const AVAILABLE_MODELS = {
  summarization: [
    { value: 'claude', label: 'Claude 4 Sonnet (via CLI)', provider: 'claude', description: 'Claude 4 Sonnet via claude CLI - comprehensive analysis (default)' },
    { value: 'sonnet', label: 'Claude 4 Sonnet (explicit)', provider: 'claude', description: 'Claude 4 Sonnet via claude CLI - explicit model selection' },
    { value: 'haiku', label: 'Claude 4 Haiku (via CLI)', provider: 'claude', description: 'Claude 4 Haiku via claude CLI - faster, more economical' },
    { value: 'opus', label: 'Claude 4 Opus (via CLI)', provider: 'claude', description: 'Claude 4 Opus via claude CLI - maximum capability' },
    { value: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro (Free)', provider: 'gemini', description: 'Via gemini-cli npm package - comprehensive analysis' },
    { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash (Free)', provider: 'gemini', description: 'Via gemini-cli npm package - faster performance' },
    { value: 'gemini-pro', label: 'Gemini Pro (Free)', provider: 'gemini', description: 'Via gemini-cli npm package - previous generation' },
    { value: 'gpt-4o', label: 'GPT-4o', provider: 'openai', description: 'Latest OpenAI model with strong analysis' },
    { value: 'gpt-4o-mini', label: 'GPT-4o Mini', provider: 'openai', description: 'Cost-effective model for summarization' },
    { value: 'gpt-4-turbo', label: 'GPT-4 Turbo', provider: 'openai', description: 'High-performance summarization model' },
    { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo', provider: 'openai', description: 'Fast and affordable summarization' },
  ],
  fewshot: [
    { value: 'claude', label: 'Claude 4 Sonnet (via CLI)', provider: 'claude', description: 'Claude 4 Sonnet via claude CLI - context-aware example generation (default)' },
    { value: 'sonnet', label: 'Claude 4 Sonnet (explicit)', provider: 'claude', description: 'Claude 4 Sonnet via claude CLI - explicit model selection' },
    { value: 'haiku', label: 'Claude 4 Haiku (via CLI)', provider: 'claude', description: 'Claude 4 Haiku via claude CLI - faster example generation' },
    { value: 'opus', label: 'Claude 4 Opus (via CLI)', provider: 'claude', description: 'Claude 4 Opus via claude CLI - maximum quality examples' },
    { value: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro (Free)', provider: 'gemini', description: 'Via gemini-cli - best for nuanced examples' },
    { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash (Free)', provider: 'gemini', description: 'Via gemini-cli - balance of speed and quality' },
    { value: 'gemini-pro', label: 'Gemini Pro (Free)', provider: 'gemini', description: 'Via gemini-cli - reliable example generation' },
    { value: 'gpt-4o', label: 'GPT-4o', provider: 'openai', description: 'Excellent for creative examples' },
    { value: 'gpt-4o-mini', label: 'GPT-4o Mini', provider: 'openai', description: 'Efficient example generation' },
    { value: 'gpt-4-turbo', label: 'GPT-4 Turbo', provider: 'openai', description: 'High-quality few-shot examples' },
    { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo', provider: 'openai', description: 'Quick example generation' },
  ],
  classification: [
    { value: 'claude', label: 'Claude 4 Sonnet (via CLI)', provider: 'claude', description: 'Claude 4 Sonnet via claude CLI - highly accurate classification (default)' },
    { value: 'sonnet', label: 'Claude 4 Sonnet (explicit)', provider: 'claude', description: 'Claude 4 Sonnet via claude CLI - explicit model selection' },
    { value: 'haiku', label: 'Claude 4 Haiku (via CLI)', provider: 'claude', description: 'Claude 4 Haiku via claude CLI - faster classification' },
    { value: 'opus', label: 'Claude 4 Opus (via CLI)', provider: 'claude', description: 'Claude 4 Opus via claude CLI - maximum accuracy' },
    { value: 'gemma3n:e4b', label: 'Gemma3n (e4b)', provider: 'ollama', description: 'Optimized for classification tasks' },
    { value: 'llama3.3:70b', label: 'Llama 3.3 70B', provider: 'ollama', description: 'Large model with high accuracy' },
    { value: 'qwen2.5-coder:32b', label: 'Qwen 2.5 Coder 32B', provider: 'ollama', description: 'Alternative classification model' },
    { value: 'mixtral:8x7b', label: 'Mixtral 8x7B', provider: 'ollama', description: 'MoE model with good performance' },
    { value: 'gpt-4o', label: 'GPT-4o', provider: 'openai', description: 'Highly accurate classification' },
    { value: 'gpt-4o-mini', label: 'GPT-4o Mini', provider: 'openai', description: 'Fast and accurate classification' },
    { value: 'gpt-4-turbo', label: 'GPT-4 Turbo', provider: 'openai', description: 'Premium classification accuracy' },
    { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo', provider: 'openai', description: 'Cost-effective classification' },
  ],
  response: [
    { value: 'claude', label: 'Claude 4 Sonnet (via CLI)', provider: 'claude', description: 'Claude 4 Sonnet via claude CLI - context-aware responses (default)' },
    { value: 'sonnet', label: 'Claude 4 Sonnet (explicit)', provider: 'claude', description: 'Claude 4 Sonnet via claude CLI - explicit model selection' },
    { value: 'haiku', label: 'Claude 4 Haiku (via CLI)', provider: 'claude', description: 'Claude 4 Haiku via claude CLI - faster response generation' },
    { value: 'opus', label: 'Claude 4 Opus (via CLI)', provider: 'claude', description: 'Claude 4 Opus via claude CLI - highest quality responses' },
    { value: 'deepseek-r1:latest', label: 'Deepseek R1', provider: 'ollama', description: 'Advanced reasoning for responses' },
    { value: 'llama3.3:70b', label: 'Llama 3.3 70B', provider: 'ollama', description: 'High-quality response generation' },
    { value: 'qwen2.5-coder:32b', label: 'Qwen 2.5 Coder 32B', provider: 'ollama', description: 'Good for technical responses' },
    { value: 'mixtral:8x7b', label: 'Mixtral 8x7B', provider: 'ollama', description: 'Balanced response generation' },
    { value: 'gpt-4o', label: 'GPT-4o', provider: 'openai', description: 'Creative and engaging responses' },
    { value: 'gpt-4o-mini', label: 'GPT-4o Mini', provider: 'openai', description: 'Quick response generation' },
    { value: 'gpt-4-turbo', label: 'GPT-4 Turbo', provider: 'openai', description: 'Premium response quality' },
    { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo', provider: 'openai', description: 'Fast and affordable responses' },
  ],
  moderation: [
    { value: 'claude', label: 'Claude 4 Sonnet (via CLI)', provider: 'claude', description: 'Claude 4 Sonnet via claude CLI - excellent for quality evaluation (default)' },
    { value: 'sonnet', label: 'Claude 4 Sonnet (explicit)', provider: 'claude', description: 'Claude 4 Sonnet via claude CLI - explicit model selection' },
    { value: 'haiku', label: 'Claude 4 Haiku (via CLI)', provider: 'claude', description: 'Claude 4 Haiku via claude CLI - faster quality evaluation' },
    { value: 'opus', label: 'Claude 4 Opus (via CLI)', provider: 'claude', description: 'Claude 4 Opus via claude CLI - most thorough quality assessment' },
    { value: 'gpt-4o', label: 'GPT-4o', provider: 'openai', description: 'Superior moderation and quality assessment' },
    { value: 'gpt-4-turbo', label: 'GPT-4 Turbo', provider: 'openai', description: 'Premium quality evaluation capabilities' },
    { value: 'gpt-4o-mini', label: 'GPT-4o Mini', provider: 'openai', description: 'Cost-effective quality checking' },
    { value: 'llama3.3:70b', label: 'Llama 3.3 70B', provider: 'ollama', description: 'Large model capable of quality assessment' },
  ],
} as const

// Default model configuration  
export const DEFAULT_MODEL_CONFIG = {
  summarization: 'gemini-2.5-pro',
  fewshot: 'gemini-2.5-pro',
  classification: 'gemma3n:e4b',
  response: 'deepseek-r1:latest',
  moderation: 'claude',  // Uses Claude CLI (defaults to Claude 4 Sonnet)
} as const

// Model provider URLs for validation
export const MODEL_PROVIDERS = {
  claude: 'cli', // Claude uses CLI interface, not HTTP API
  gemini: 'https://generativelanguage.googleapis.com/v1beta',
  ollama: process.env.WDF_OLLAMA_HOST || 'http://localhost:11434',
  openai: 'https://api.openai.com/v1',
} as const

// Model capability flags - indicates which tasks each model is good at
export const MODEL_CAPABILITIES = {
  // Claude models - excellent at all tasks
  'claude': {
    canSummarize: true,
    canGenerateFewshots: true,
    canClassify: true,
    canRespond: true,
    canModerate: true,
    qualityRating: 'excellent'
  },
  
  // Gemini models - good for text generation tasks
  'gemini-2.5-pro': {
    canSummarize: true,
    canGenerateFewshots: true,
    canClassify: true,
    canRespond: true,
    canModerate: false, // Not specialized for quality evaluation
    qualityRating: 'good'
  },
  'gemini-2.5-flash': {
    canSummarize: true,
    canGenerateFewshots: true,
    canClassify: true,
    canRespond: true,
    canModerate: false,
    qualityRating: 'good'
  },
  'gemini-pro': {
    canSummarize: true,
    canGenerateFewshots: true,
    canClassify: true,
    canRespond: true,
    canModerate: false,
    qualityRating: 'good'
  },
  
  // OpenAI models - good for most tasks
  'gpt-4o': {
    canSummarize: true,
    canGenerateFewshots: true,
    canClassify: true,
    canRespond: true,
    canModerate: true,
    qualityRating: 'excellent'
  },
  'gpt-4-turbo': {
    canSummarize: true,
    canGenerateFewshots: true,
    canClassify: true,
    canRespond: true,
    canModerate: true,
    qualityRating: 'excellent'
  },
  'gpt-4o-mini': {
    canSummarize: true,
    canGenerateFewshots: true,
    canClassify: true,
    canRespond: true,
    canModerate: true,
    qualityRating: 'good'
  },
  'gpt-3.5-turbo': {
    canSummarize: true,
    canGenerateFewshots: true,
    canClassify: true,
    canRespond: true,
    canModerate: false, // Limited capability for complex evaluation
    qualityRating: 'fair'
  },
  
  // Ollama models - specialized capabilities
  'gemma3n:e4b': {
    canSummarize: false, // Optimized for classification
    canGenerateFewshots: false,
    canClassify: true,
    canRespond: false,
    canModerate: false,
    qualityRating: 'excellent' // For classification only
  },
  'llama3.3:70b': {
    canSummarize: true,
    canGenerateFewshots: true,
    canClassify: true,
    canRespond: true,
    canModerate: true, // Large model can handle evaluation
    qualityRating: 'good'
  },
  'deepseek-r1:latest': {
    canSummarize: true,
    canGenerateFewshots: true,
    canClassify: true,
    canRespond: true,
    canModerate: false, // Focused on reasoning, not evaluation
    qualityRating: 'good'
  },
  'qwen2.5-coder:32b': {
    canSummarize: true,
    canGenerateFewshots: true,
    canClassify: true,
    canRespond: true,
    canModerate: false,
    qualityRating: 'good'
  },
  'mixtral:8x7b': {
    canSummarize: true,
    canGenerateFewshots: true,
    canClassify: true,
    canRespond: true,
    canModerate: false,
    qualityRating: 'good'
  },
  'phi3:14b': {
    canSummarize: false,
    canGenerateFewshots: false,
    canClassify: true,
    canRespond: false,
    canModerate: false,
    qualityRating: 'fair'
  }
} as const

// Default stage configuration - which stages are enabled by default
export const DEFAULT_STAGE_CONFIG = {
  summarization: { enabled: true, required: true }, // Always needed
  fewshot: { enabled: false, required: false }, // Not needed for Claude pipeline
  scraping: { enabled: true, required: true }, // Always needed
  classification: { enabled: true, required: true }, // Always needed  
  response: { enabled: true, required: false }, // Can be disabled
  moderation: { enabled: false, required: false }, // Optional quality check
} as const

// Helper functions
export function getModelCapabilities(modelName: string) {
  return MODEL_CAPABILITIES[modelName as keyof typeof MODEL_CAPABILITIES] || {
    canSummarize: false,
    canGenerateFewshots: false,
    canClassify: false,
    canRespond: false,
    canModerate: false,
    qualityRating: 'unknown'
  }
}

export function isModelSuitableForTask(modelName: string, task: keyof typeof DEFAULT_MODEL_CONFIG): boolean {
  const capabilities = getModelCapabilities(modelName)
  
  switch (task) {
    case 'summarization':
      return capabilities.canSummarize
    case 'fewshot':
      return capabilities.canGenerateFewshots
    case 'classification':
      return capabilities.canClassify
    case 'response':
      return capabilities.canRespond
    case 'moderation':
      return capabilities.canModerate
    default:
      return false
  }
}

export function getRecommendationLevel(modelName: string, task: keyof typeof DEFAULT_MODEL_CONFIG): 'excellent' | 'good' | 'fair' | 'poor' | 'incompatible' {
  const capabilities = getModelCapabilities(modelName)
  
  if (!isModelSuitableForTask(modelName, task)) {
    return 'incompatible'
  }
  
  // For specialized models, check if this is their primary use case
  if (modelName === 'gemma3n:e4b' && task === 'classification') {
    return 'excellent'
  }
  
  return capabilities.qualityRating as 'excellent' | 'good' | 'fair' | 'poor'
}