/**
 * Validation Results Component
 * 
 * Displays comprehensive pre-flight validation results with:
 * - Overall readiness status
 * - Detailed check results
 * - Actionable next steps
 * - Fix recommendations
 * - Progress tracking for fixes
 */

"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { ScrollArea } from "@/components/ui/scroll-area"
import { 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  Clock, 
  RefreshCw,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  Play,
  Settings,
  Database,
  Key,
  Cpu,
  HardDrive,
  Wifi,
  FileText,
  Zap
} from "lucide-react"
import { cn } from "@/lib/utils"

export interface ValidationCheck {
  id: string
  name: string
  category: 'critical' | 'warning' | 'info'
  status: 'pass' | 'fail' | 'skip' | 'pending'
  message: string
  suggestion?: string
  resolutionTime?: number
  details?: any
}

export interface ValidationResult {
  isValid: boolean
  score: number
  errors: string[]
  warnings: string[]
  checks: ValidationCheck[]
  estimatedIssueResolutionTime: number
}

export interface NextStep {
  priority: 'high' | 'medium' | 'low'
  action: string
  description: string
  estimatedTime: number
  category: string
}

interface ValidationResultsProps {
  episodeId: number
  validation: ValidationResult
  nextSteps: NextStep[]
  readinessStatus: {
    status: 'ready' | 'needs_attention' | 'blocked'
    color: 'green' | 'yellow' | 'red'
    message: string
  }
  onRevalidate?: () => void
  onStartPipeline?: () => void
  isRevalidating?: boolean
  canStartPipeline?: boolean
}

// Category icons and colors
const CATEGORY_CONFIG = {
  critical: {
    icon: XCircle,
    color: 'text-red-600',
    bg: 'bg-red-50',
    border: 'border-red-200',
    label: 'Critical Issues',
  },
  warning: {
    icon: AlertTriangle,
    color: 'text-yellow-600',
    bg: 'bg-yellow-50',
    border: 'border-yellow-200',
    label: 'Warnings',
  },
  info: {
    icon: CheckCircle2,
    color: 'text-blue-600',
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    label: 'Information',
  },
}

// Check type icons
const CHECK_ICONS = {
  episode_exists: FileText,
  episode_title: FileText,
  episode_transcript: FileText,
  episode_video_url: ExternalLink,
  twitter_api_keys: Key,
  gemini_api_keys: Key,
  claude_api_keys: Key,
  ollama_health: Cpu,
  classification_model: Zap,
  response_model: Zap,
  gemini_cli: Settings,
  disk_space: HardDrive,
  database_connectivity: Database,
  scoring_thresholds: Settings,
  keywords_configured: Settings,
}

export function ValidationResults({
  episodeId,
  validation,
  nextSteps,
  readinessStatus,
  onRevalidate,
  onStartPipeline,
  isRevalidating = false,
  canStartPipeline = false,
}: ValidationResultsProps) {
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set(['critical']))
  const [expandedChecks, setExpandedChecks] = useState<Set<string>>(new Set())

  // Group checks by category
  const checksByCategory = validation.checks.reduce((acc, check) => {
    if (!acc[check.category]) acc[check.category] = []
    acc[check.category].push(check)
    return acc
  }, {} as Record<string, ValidationCheck[]>)

  // Toggle category expansion
  const toggleCategory = (category: string) => {
    const newExpanded = new Set(expandedCategories)
    if (newExpanded.has(category)) {
      newExpanded.delete(category)
    } else {
      newExpanded.add(category)
    }
    setExpandedCategories(newExpanded)
  }

  // Toggle check expansion
  const toggleCheck = (checkId: string) => {
    const newExpanded = new Set(expandedChecks)
    if (newExpanded.has(checkId)) {
      newExpanded.delete(checkId)
    } else {
      newExpanded.add(checkId)
    }
    setExpandedChecks(newExpanded)
  }

  // Get status badge configuration
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'pass':
        return { variant: 'default' as const, className: 'bg-green-100 text-green-800 border-green-200' }
      case 'fail':
        return { variant: 'destructive' as const, className: '' }
      case 'skip':
        return { variant: 'secondary' as const, className: '' }
      default:
        return { variant: 'outline' as const, className: '' }
    }
  }

  // Get readiness status styling
  const getReadinessStatusStyling = () => {
    switch (readinessStatus.color) {
      case 'green':
        return {
          alertClass: 'border-green-200 bg-green-50',
          iconColor: 'text-green-600',
          icon: CheckCircle2,
        }
      case 'yellow':
        return {
          alertClass: 'border-yellow-200 bg-yellow-50',
          iconColor: 'text-yellow-600',
          icon: AlertTriangle,
        }
      case 'red':
        return {
          alertClass: 'border-red-200 bg-red-50',
          iconColor: 'text-red-600',
          icon: XCircle,
        }
    }
  }

  const statusStyling = getReadinessStatusStyling()

  return (
    <div className="space-y-6">
      {/* Overall Status */}
      <Card>
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">Pre-flight Validation</CardTitle>
              <p className="text-sm text-muted-foreground">
                Episode {episodeId} • {validation.checks.length} checks completed
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-right">
                <div className="text-2xl font-bold">{validation.score}/100</div>
                <div className="text-sm text-muted-foreground">Readiness Score</div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={onRevalidate}
                disabled={isRevalidating}
              >
                <RefreshCw className={cn("w-4 h-4 mr-2", isRevalidating && "animate-spin")} />
                {isRevalidating ? 'Validating...' : 'Re-validate'}
              </Button>
            </div>
          </div>
          
          <Progress value={validation.score} className="h-2 mt-2" />
        </CardHeader>

        <CardContent>
          <Alert className={statusStyling.alertClass}>
            <statusStyling.icon className={cn("h-4 w-4", statusStyling.iconColor)} />
            <AlertTitle className="capitalize">{readinessStatus.status.replace('_', ' ')}</AlertTitle>
            <AlertDescription>
              {readinessStatus.message}
              {validation.estimatedIssueResolutionTime > 0 && (
                <span className="block mt-1 text-sm">
                  Estimated fix time: {Math.ceil(validation.estimatedIssueResolutionTime)} minutes
                </span>
              )}
            </AlertDescription>
          </Alert>

          {/* Quick Actions */}
          <div className="flex items-center gap-3 mt-4">
            {canStartPipeline && validation.isValid && (
              <Button onClick={onStartPipeline}>
                <Play className="w-4 h-4 mr-2" />
                Start Pipeline
              </Button>
            )}
            
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <div className="flex items-center gap-1">
                <CheckCircle2 className="w-4 h-4 text-green-600" />
                {validation.checks.filter(c => c.status === 'pass').length} passed
              </div>
              <div className="flex items-center gap-1">
                <XCircle className="w-4 h-4 text-red-600" />
                {validation.errors.length} errors
              </div>
              <div className="flex items-center gap-1">
                <AlertTriangle className="w-4 h-4 text-yellow-600" />
                {validation.warnings.length} warnings
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Detailed Results */}
      <Tabs defaultValue="checks" className="space-y-4">
        <TabsList>
          <TabsTrigger value="checks">Validation Checks</TabsTrigger>
          <TabsTrigger value="next-steps">
            Next Steps 
            {nextSteps.filter(s => s.priority === 'high').length > 0 && (
              <Badge variant="destructive" className="ml-2 text-xs">
                {nextSteps.filter(s => s.priority === 'high').length}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="checks" className="space-y-4">
          {Object.entries(checksByCategory).map(([category, checks]) => {
            const categoryConfig = CATEGORY_CONFIG[category as keyof typeof CATEGORY_CONFIG]
            const isExpanded = expandedCategories.has(category)
            const failedChecks = checks.filter(c => c.status === 'fail')

            return (
              <Card key={category}>
                <CardHeader className="pb-3">
                  <div 
                    className="flex items-center justify-between cursor-pointer"
                    onClick={() => toggleCategory(category)}
                  >
                    <div className="flex items-center gap-3">
                      <categoryConfig.icon className={cn("w-5 h-5", categoryConfig.color)} />
                      <h3 className="font-medium">{categoryConfig.label}</h3>
                      <Badge variant="outline">
                        {failedChecks.length} / {checks.length}
                      </Badge>
                    </div>
                    {isExpanded ? (
                      <ChevronDown className="w-4 h-4" />
                    ) : (
                      <ChevronRight className="w-4 h-4" />
                    )}
                  </div>
                </CardHeader>

                {isExpanded && (
                  <CardContent className="pt-0">
                    <ScrollArea className="h-64">
                      <div className="space-y-3">
                        {checks.map((check) => {
                          const statusBadge = getStatusBadge(check.status)
                          const isCheckExpanded = expandedChecks.has(check.id)
                          const CheckIcon = CHECK_ICONS[check.id as keyof typeof CHECK_ICONS] || Settings

                          return (
                            <div 
                              key={check.id}
                              className={cn(
                                "p-3 rounded-lg border cursor-pointer transition-colors",
                                check.status === 'fail' && "border-red-200 bg-red-50",
                                check.status === 'pass' && "border-green-200 bg-green-50",
                                check.status === 'skip' && "border-gray-200 bg-gray-50"
                              )}
                              onClick={() => toggleCheck(check.id)}
                            >
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3 flex-1">
                                  <CheckIcon className="w-4 h-4 text-muted-foreground" />
                                  <div className="flex-1">
                                    <div className="flex items-center gap-2">
                                      <span className="font-medium text-sm">{check.name}</span>
                                      <Badge {...statusBadge}>{check.status}</Badge>
                                    </div>
                                    <p className="text-sm text-muted-foreground mt-1">
                                      {check.message}
                                    </p>
                                  </div>
                                </div>
                                
                                <div className="flex items-center gap-2">
                                  {check.resolutionTime && (
                                    <div className="text-xs text-muted-foreground flex items-center gap-1">
                                      <Clock className="w-3 h-3" />
                                      {check.resolutionTime}m
                                    </div>
                                  )}
                                  {isCheckExpanded ? (
                                    <ChevronDown className="w-4 h-4" />
                                  ) : (
                                    <ChevronRight className="w-4 h-4" />
                                  )}
                                </div>
                              </div>

                              {/* Expanded check details */}
                              {isCheckExpanded && (check.suggestion || check.details) && (
                                <div className="mt-3 pt-3 border-t border-gray-200">
                                  {check.suggestion && (
                                    <div className="mb-2">
                                      <h4 className="text-sm font-medium text-blue-800 mb-1">
                                        Recommended Action:
                                      </h4>
                                      <p className="text-sm text-blue-700 bg-blue-50 p-2 rounded">
                                        {check.suggestion}
                                      </p>
                                    </div>
                                  )}
                                  
                                  {check.details && (
                                    <div>
                                      <h4 className="text-sm font-medium text-gray-800 mb-1">
                                        Details:
                                      </h4>
                                      <pre className="text-xs text-gray-600 bg-gray-50 p-2 rounded overflow-x-auto">
                                        {JSON.stringify(check.details, null, 2)}
                                      </pre>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    </ScrollArea>
                  </CardContent>
                )}
              </Card>
            )
          })}
        </TabsContent>

        <TabsContent value="next-steps" className="space-y-4">
          {nextSteps.length === 0 ? (
            <Card>
              <CardContent className="p-6 text-center">
                <CheckCircle2 className="w-12 h-12 text-green-600 mx-auto mb-3" />
                <h3 className="font-medium text-lg mb-2">All Set!</h3>
                <p className="text-muted-foreground">
                  No action items found. Your pipeline is ready to run.
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {nextSteps.map((step, index) => (
                <Card key={index}>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3 flex-1">
                        <div className={cn(
                          "w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium",
                          step.priority === 'high' && "bg-red-100 text-red-800",
                          step.priority === 'medium' && "bg-yellow-100 text-yellow-800",
                          step.priority === 'low' && "bg-blue-100 text-blue-800"
                        )}>
                          {index + 1}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <h3 className="font-medium">{step.action}</h3>
                            <Badge 
                              variant={step.priority === 'high' ? 'destructive' : 
                                      step.priority === 'medium' ? 'default' : 'secondary'}
                              className="text-xs"
                            >
                              {step.priority} priority
                            </Badge>
                            <Badge variant="outline" className="text-xs">
                              {step.category}
                            </Badge>
                          </div>
                          <p className="text-sm text-muted-foreground">
                            {step.description}
                          </p>
                        </div>
                      </div>
                      
                      <div className="text-right text-sm text-muted-foreground">
                        <div className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {step.estimatedTime}m
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
              
              <Card className="bg-blue-50 border-blue-200">
                <CardContent className="p-4">
                  <div className="flex items-center gap-3">
                    <Clock className="w-5 h-5 text-blue-600" />
                    <div>
                      <h3 className="font-medium text-blue-900">
                        Total Estimated Time
                      </h3>
                      <p className="text-sm text-blue-700">
                        {Math.ceil(nextSteps.reduce((sum, step) => sum + step.estimatedTime, 0))} minutes 
                        to resolve all issues
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}