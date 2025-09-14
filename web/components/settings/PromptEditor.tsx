'use client'

import { useState, useEffect } from 'react'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { TestTube, Variable, FileText, AlertCircle } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { toast } from '@/components/ui/use-toast'

interface PromptTemplate {
  id: number
  key: string
  name: string
  description: string | null
  template: string
  variables: string[] | any
  isActive: boolean
  version: number
  historyCount?: number
}

interface PromptEditorProps {
  prompt: PromptTemplate
  onChange: (prompt: PromptTemplate) => void
  sampleData?: Record<string, any>
}

export function PromptEditor({ prompt, onChange, sampleData = {} }: PromptEditorProps) {
  const [preview, setPreview] = useState<string>('')
  const [isTestLoading, setIsTestLoading] = useState(false)
  const [testResult, setTestResult] = useState<{
    result: string
    variables: string[]
    usedData: Record<string, any>
  } | null>(null)

  // Extract variables from template
  const extractVariables = (template: string): string[] => {
    const variables = new Set<string>()
    
    // Extract from conditional blocks
    template.replace(/{(\w+)\s*\?/g, (match, varName) => {
      variables.add(varName)
      return match
    })
    
    // Extract from simple substitutions
    template.replace(/{(\w+)}/g, (match, varName) => {
      variables.add(varName)
      return match
    })
    
    return Array.from(variables)
  }

  // Temporarily disabled to fix focus issue
  // useEffect(() => {
  //   const timeoutId = setTimeout(() => {
  //     const vars = extractVariables(prompt.template)
  //     const currentVars = Array.isArray(prompt.variables) ? prompt.variables : []
  //     if (JSON.stringify(vars) !== JSON.stringify(currentVars)) {
  //       onChange({ ...prompt, variables: vars })
  //     }
  //   }, 500) // Debounce for 500ms

  //   return () => clearTimeout(timeoutId)
  // }, [prompt.template, prompt.variables, prompt, onChange])

  const handleTest = async () => {
    try {
      setIsTestLoading(true)
      
      const res = await fetch('/api/settings/prompts/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          template: prompt.template,
          variables: extractVariables(prompt.template),
          sampleData
        })
      })
      
      if (!res.ok) throw new Error('Failed to test prompt')
      
      const data = await res.json()
      setTestResult(data)
      setPreview(data.result)
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to test prompt template',
        variant: 'destructive'
      })
    } finally {
      setIsTestLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Template Editor */}
      <div className="space-y-2">
        <Label htmlFor="template">Template</Label>
        <Textarea
          id="template"
          value={prompt.template}
          onChange={(e) => onChange({ ...prompt, template: e.target.value })}
          className="min-h-[400px] font-mono text-sm"
          placeholder="Enter your prompt template here..."
        />
        <p className="text-sm text-muted-foreground">
          Use {'{variable}'} for simple substitution or {'{condition ? \'true\' : \'false\'}'} for conditionals
        </p>
      </div>

      {/* Variables */}
      {(() => {
        const currentVars = extractVariables(prompt.template)
        return currentVars.length > 0 && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Variable className="h-4 w-4" />
                Template Variables
              </CardTitle>
              <CardDescription>
                These variables will be replaced with actual values during execution
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {currentVars.map((variable) => (
                  <Badge key={variable} variant="secondary">
                    {variable}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )
      })()}

      {/* Test Section */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base flex items-center gap-2">
                <TestTube className="h-4 w-4" />
                Test Template
              </CardTitle>
              <CardDescription>
                Preview how your template will look with sample data
              </CardDescription>
            </div>
            <Button
              size="sm"
              onClick={handleTest}
              disabled={isTestLoading}
            >
              {isTestLoading ? 'Testing...' : 'Run Test'}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {testResult && (
            <>
              {/* Sample Data Used */}
              <div className="space-y-2">
                <Label className="text-sm">Sample Data</Label>
                <div className="bg-muted p-3 rounded-md">
                  <pre className="text-xs font-mono overflow-x-auto">
                    {JSON.stringify(testResult.usedData, null, 2)}
                  </pre>
                </div>
              </div>

              <Separator />

              {/* Preview Result */}
              <div className="space-y-2">
                <Label className="text-sm flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  Preview Result
                </Label>
                <ScrollArea className="h-[300px] w-full rounded-md border p-4">
                  <pre className="text-sm whitespace-pre-wrap font-mono">
                    {testResult.result}
                  </pre>
                </ScrollArea>
              </div>

              {/* Character Count for Response Generation */}
              {prompt.key === 'response_generation' && (
                <Alert>
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>
                    Preview length: {testResult.result.length} characters
                    {testResult.result.length > 280 && (
                      <span className="text-destructive ml-1">
                        (exceeds Twitter limit by {testResult.result.length - 280} characters)
                      </span>
                    )}
                  </AlertDescription>
                </Alert>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Description */}
      <div className="space-y-2">
        <Label htmlFor="description">Description (Optional)</Label>
        <Textarea
          id="description"
          value={prompt.description || ''}
          onChange={(e) => onChange({ ...prompt, description: e.target.value })}
          className="min-h-[80px]"
          placeholder="Add notes about this prompt template..."
        />
      </div>
    </div>
  )
}