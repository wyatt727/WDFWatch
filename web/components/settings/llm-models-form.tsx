'use client'

import { useState, useEffect, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Card } from '@/components/ui/card'
import { useToast } from '@/components/ui/use-toast'
import { Loader2, RotateCcw, Save, Sparkles, Zap, Brain, MessageSquare, Shield, CheckCircle, AlertCircle, Settings as SettingsIcon } from 'lucide-react'
import { ModelSelect } from '@/components/ui/model-select'
import { isModelSuitableForTask, getRecommendationLevel, getModelCapabilities } from '@/lib/llm-models'
import { Switch } from '@/components/ui/switch'
import { Separator } from '@/components/ui/separator'

type ModelOption = {
  value: string
  label: string
  provider: string
  description: string
}

type LLMConfig = {
  summarization: string
  fewshot: string
  classification: string
  response: string
  moderation: string
}

type AvailableModels = {
  summarization: ModelOption[]
  fewshot: ModelOption[]
  classification: ModelOption[]
  response: ModelOption[]
  moderation: ModelOption[]
}

type StageConfig = {
  enabled: boolean
  required: boolean
}

type PipelineStages = {
  summarization: StageConfig
  fewshot: StageConfig
  scraping: StageConfig
  classification: StageConfig
  response: StageConfig
  moderation: StageConfig
}

const TASK_INFO = {
  summarization: {
    title: 'Summarization',
    description: 'Generates podcast summaries and extracts keywords',
    icon: Sparkles,
    hasModel: true,
  },
  fewshot: {
    title: 'Few-shot Generation',
    description: 'Creates example tweets for classification training',
    icon: Zap,
    hasModel: true,
  },
  scraping: {
    title: 'Tweet Scraping',
    description: 'Discovers relevant tweets using keywords',
    icon: SettingsIcon,
    hasModel: false,
  },
  classification: {
    title: 'Tweet Classification',
    description: 'Scores tweet relevancy from 0.00 to 1.00',
    icon: Brain,
    hasModel: true,
  },
  response: {
    title: 'Response Generation',
    description: 'Generates engaging responses to relevant tweets',
    icon: MessageSquare,
    hasModel: true,
  },
  moderation: {
    title: 'Quality Moderation',
    description: 'Evaluates response quality and appropriateness',
    icon: Shield,
    hasModel: true,
  },
}

export function LLMModelsForm() {
  const [config, setConfig] = useState<LLMConfig | null>(null)
  const [available, setAvailable] = useState<AvailableModels | null>(null)
  const [stages, setStages] = useState<PipelineStages | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [validationResults, setValidationResults] = useState<Record<string, boolean>>({})
  const [dependencyErrors, setDependencyErrors] = useState<string[]>([])
  const [dependencyWarnings, setDependencyWarnings] = useState<string[]>([])
  const [capabilityWarnings, setCapabilityWarnings] = useState<Record<string, string>>({})
  const { toast } = useToast()

  // Stage dependency validation
  const validateStageDependencies = useCallback((stageConfig: PipelineStages) => {
    const errors: string[] = []
    const warnings: string[] = []

    // Response generation typically needs classification
    if (stageConfig.response?.enabled && !stageConfig.classification?.enabled) {
      warnings.push('Response generation is enabled but classification is disabled. This may result in responses to irrelevant tweets.')
    }

    // Moderation needs response generation
    if (stageConfig.moderation?.enabled && !stageConfig.response?.enabled) {
      errors.push('Moderation requires response generation to be enabled.')
    }

    // Classification typically needs scraping (tweets to classify)
    if (stageConfig.classification?.enabled && !stageConfig.scraping?.enabled) {
      warnings.push('Classification is enabled but scraping is disabled. No tweets will be available to classify.')
    }

    // Response generation needs scraping (tweets to respond to)
    if (stageConfig.response?.enabled && !stageConfig.scraping?.enabled) {
      warnings.push('Response generation is enabled but scraping is disabled. No tweets will be available for responses.')
    }

    return { errors, warnings }
  }, [])

  // Model capability validation
  const validateModelCapabilities = useCallback((modelsConfig: LLMConfig) => {
    const warnings: Record<string, string> = {}

    Object.entries(modelsConfig).forEach(([task, modelName]) => {
      const taskKey = task as keyof typeof modelsConfig
      
      if (!isModelSuitableForTask(modelName, taskKey)) {
        const capabilities = getModelCapabilities(modelName)
        warnings[task] = `This model is not suitable for ${task}. Consider using a model with better ${task} capabilities.`
      } else {
        const recommendationLevel = getRecommendationLevel(modelName, taskKey)
        if (recommendationLevel === 'fair') {
          warnings[task] = `This model has limited capabilities for ${task}. Consider a higher-quality model for better results.`
        } else if (recommendationLevel === 'poor') {
          warnings[task] = `This model is not recommended for ${task}. Performance may be significantly degraded.`
        }
      }
    })

    return warnings
  }, [])

  const fetchConfig = useCallback(async () => {
    try {
      // Fetch both LLM models and stage configuration
      const [modelsResponse, stagesResponse] = await Promise.all([
        fetch('/api/settings/llm-models'),
        fetch('/api/settings/pipeline-stages')
      ])
      
      if (!modelsResponse.ok) throw new Error('Failed to fetch LLM model configuration')
      if (!stagesResponse.ok) throw new Error('Failed to fetch stage configuration')
      
      const modelsData = await modelsResponse.json()
      const stagesData = await stagesResponse.json()
      
      setConfig(modelsData.config)
      setAvailable(modelsData.available)
      setStages(stagesData.config)
      
      // Validate dependencies on initial load
      const validation = validateStageDependencies(stagesData.config)
      setDependencyErrors(validation.errors)
      setDependencyWarnings(validation.warnings)
      
      // Validate model capabilities on initial load
      const capabilityWarnings = validateModelCapabilities(modelsData.config)
      setCapabilityWarnings(capabilityWarnings)
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to load configuration',
        variant: 'destructive',
      })
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    fetchConfig()
  }, [fetchConfig])

  const handleSave = async () => {
    if (!config || !stages) return

    setSaving(true)
    try {
      // Save both LLM models and stage configuration in parallel
      const [modelsResponse, stagesResponse] = await Promise.all([
        fetch('/api/settings/llm-models', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(config),
        }),
        fetch('/api/settings/pipeline-stages', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(stages),
        })
      ])

      if (!modelsResponse.ok) throw new Error('Failed to save LLM model configuration')
      if (!stagesResponse.ok) throw new Error('Failed to save stage configuration')

      toast({
        title: 'Success',
        description: 'LLM models and stage configuration saved successfully',
      })
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to save configuration',
        variant: 'destructive',
      })
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    setSaving(true)
    try {
      // Reset both LLM models and stage configuration in parallel
      const [modelsResponse, stagesResponse] = await Promise.all([
        fetch('/api/settings/llm-models/reset', {
          method: 'POST',
        }),
        fetch('/api/settings/pipeline-stages/reset', {
          method: 'POST',
        })
      ])

      if (!modelsResponse.ok) throw new Error('Failed to reset LLM model configuration')
      if (!stagesResponse.ok) throw new Error('Failed to reset stage configuration')

      const [modelsData, stagesData] = await Promise.all([
        modelsResponse.json(),
        stagesResponse.json()
      ])

      setConfig(modelsData.config)
      setStages(stagesData.config)
      setValidationResults({}) // Clear validation results
      setCapabilityWarnings({}) // Clear capability warnings
      setDependencyErrors([]) // Clear dependency errors
      setDependencyWarnings([]) // Clear dependency warnings

      toast({
        title: 'Success',
        description: 'LLM models and stage configuration reset to defaults',
      })
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to reset configuration',
        variant: 'destructive',
      })
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    if (!config || !available) return

    setTesting(true)
    setValidationResults({})
    const results: Record<string, boolean> = {}

    try {
      // Test each configured model
      for (const [task, model] of Object.entries(config)) {
        const models = available[task as keyof AvailableModels]
        const modelInfo = models.find(m => m.value === model)
        
        if (modelInfo) {
          const response = await fetch('/api/settings/llm-models/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model, provider: modelInfo.provider }),
          })

          if (response.ok) {
            const result = await response.json()
            results[`${task}-${model}`] = result.valid
            
            if (!result.valid) {
              toast({
                title: `${TASK_INFO[task as keyof typeof TASK_INFO].title}`,
                description: result.message,
                variant: 'destructive',
              })
            }
          }
        }
      }

      setValidationResults(results)
      
      const allValid = Object.values(results).every(v => v)
      if (allValid) {
        toast({
          title: 'Success',
          description: 'All models are available and ready to use',
        })
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to validate models',
        variant: 'destructive',
      })
    } finally {
      setTesting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    )
  }

  if (!config || !available) {
    return (
      <div className="text-center p-12">
        <p className="text-muted-foreground">Failed to load configuration</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Model Configuration Section */}
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold">LLM Model Configuration</h3>
          <div className="h-px bg-border flex-1" />
        </div>
        
        {(Object.keys(TASK_INFO) as Array<keyof typeof TASK_INFO>)
          .filter(task => TASK_INFO[task].hasModel)
          .map((task) => {
            const TaskIcon = TASK_INFO[task].icon
            const models = available[task] || []
            const isStageEnabled = stages?.[task]?.enabled ?? true
            
            return (
              <Card key={task} className={`p-6 ${!isStageEnabled ? 'opacity-50' : ''}`}>
                <div className="space-y-4">
                  <div className="flex items-start gap-3">
                    <TaskIcon className="h-5 w-5 text-muted-foreground mt-0.5" />
                    <div className="flex-1">
                      <Label className="text-base">{TASK_INFO[task].title}</Label>
                      <p className="text-sm text-muted-foreground mt-1">
                        {TASK_INFO[task].description}
                      </p>
                      {!isStageEnabled && (
                        <p className="text-xs text-orange-600 mt-1">
                          Stage is disabled - model selection has no effect
                        </p>
                      )}
                      {capabilityWarnings[task] && (
                        <p className="text-xs text-amber-600 mt-1 flex items-center gap-1">
                          <AlertCircle className="h-3 w-3" />
                          {capabilityWarnings[task]}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <div className="flex-1">
                      <ModelSelect
                        models={models}
                        value={config[task]}
                        onValueChange={(value) => {
                          const newConfig = { ...config, [task]: value }
                          setConfig(newConfig)
                          
                          // Clear validation for this task when changed
                          const newResults = { ...validationResults }
                          Object.keys(newResults).forEach(key => {
                            if (key.startsWith(task + '-')) {
                              delete newResults[key]
                            }
                          })
                          setValidationResults(newResults)
                          
                          // Validate model capabilities for new configuration
                          const newCapabilityWarnings = validateModelCapabilities(newConfig)
                          setCapabilityWarnings(newCapabilityWarnings)
                        }}
                        placeholder="Select a model..."
                        disabled={!isStageEnabled}
                      />
                    </div>
                    
                    {validationResults[`${task}-${config[task]}`] !== undefined && (
                      <div className="flex items-center">
                        {validationResults[`${task}-${config[task]}`] ? (
                          <CheckCircle className="h-5 w-5 text-green-500" />
                        ) : (
                          <AlertCircle className="h-5 w-5 text-red-500" />
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            )
          })}
      </div>

      <Separator className="my-6" />

      {/* Stage Configuration Section */}
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold">Pipeline Stage Configuration</h3>
          <div className="h-px bg-border flex-1" />
        </div>
        
        <div className="text-sm text-muted-foreground mb-4">
          Enable or disable individual pipeline stages. Required stages cannot be disabled.
        </div>

        {stages && (Object.keys(TASK_INFO) as Array<keyof typeof TASK_INFO>).map((task) => {
          const TaskIcon = TASK_INFO[task].icon
          const stageConfig = stages[task]
          const isRequired = stageConfig?.required ?? false
          
          return (
            <Card key={task} className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <TaskIcon className="h-5 w-5 text-muted-foreground" />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <Label className="text-base">{TASK_INFO[task].title}</Label>
                      {isRequired && (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                          Required
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground mt-1">
                      {TASK_INFO[task].description}
                    </p>
                  </div>
                </div>
                
                <div className="flex items-center gap-2">
                  <Switch
                    checked={stageConfig?.enabled ?? true}
                    onCheckedChange={(enabled) => {
                      const newStages = {
                        ...stages,
                        [task]: {
                          ...stageConfig,
                          enabled
                        }
                      }
                      setStages(newStages)
                      
                      // Validate dependencies after change
                      const validation = validateStageDependencies(newStages)
                      setDependencyErrors(validation.errors)
                      setDependencyWarnings(validation.warnings)
                    }}
                    disabled={isRequired}
                  />
                  <span className="text-sm text-muted-foreground">
                    {stageConfig?.enabled ? 'Enabled' : 'Disabled'}
                  </span>
                </div>
              </div>
            </Card>
          )
        })}
      </div>

      {/* Dependency Validation Section */}
      {(dependencyErrors.length > 0 || dependencyWarnings.length > 0) && (
        <div className="space-y-4">
          {dependencyErrors.length > 0 && (
            <div className="border border-red-200 bg-red-50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <AlertCircle className="h-5 w-5 text-red-600" />
                <h4 className="font-medium text-red-800">Configuration Errors</h4>
              </div>
              <ul className="space-y-1">
                {dependencyErrors.map((error, index) => (
                  <li key={index} className="text-sm text-red-700">
                    • {error}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {dependencyWarnings.length > 0 && (
            <div className="border border-yellow-200 bg-yellow-50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <AlertCircle className="h-5 w-5 text-yellow-600" />
                <h4 className="font-medium text-yellow-800">Configuration Warnings</h4>
              </div>
              <ul className="space-y-1">
                {dependencyWarnings.map((warning, index) => (
                  <li key={index} className="text-sm text-yellow-700">
                    • {warning}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="flex justify-between">
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={handleReset}
            disabled={saving || testing}
          >
            <RotateCcw className="h-4 w-4 mr-2" />
            Reset to Defaults
          </Button>
          
          <Button
            variant="outline"
            onClick={handleTest}
            disabled={saving || testing}
          >
            {testing ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <CheckCircle className="h-4 w-4 mr-2" />
            )}
            Test Models
          </Button>
        </div>
        
        <Button 
          onClick={handleSave} 
          disabled={saving || testing || dependencyErrors.length > 0}
        >
          {saving ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <Save className="h-4 w-4 mr-2" />
          )}
          Save Configuration
        </Button>
      </div>
    </div>
  )
}