/**
 * Error Recovery Manager
 * 
 * Handles error recovery strategies for pipeline failures including:
 * - Automatic retry with exponential backoff
 * - Intelligent error categorization
 * - Recovery strategy recommendation
 * - Rollback capabilities
 * - Error context preservation
 */

import { prisma } from '@/lib/db';
import { processTracker } from '@/lib/process-tracker';

export interface ErrorContext {
  episodeId: number;
  stage: string;
  runId: string;
  errorType: ErrorType;
  errorMessage: string;
  stackTrace?: string;
  timestamp: Date;
  attemptNumber: number;
  systemState: SystemState;
  suggestedAction: RecoveryAction;
}

export interface SystemState {
  availableMemory?: number;
  diskSpace?: number;
  networkConnectivity: boolean;
  externalServiceStatus: Record<string, 'available' | 'degraded' | 'unavailable'>;
  activeProcesses: number;
}

export interface RecoveryAction {
  type: 'retry' | 'skip' | 'rollback' | 'manual_intervention' | 'abort';
  description: string;
  automated: boolean;
  estimatedTime: number; // minutes
  prerequisites?: string[];
  riskLevel: 'low' | 'medium' | 'high';
}

export type ErrorType = 
  | 'network_timeout'
  | 'api_rate_limit'
  | 'authentication_failure'
  | 'model_unavailable'
  | 'insufficient_resources'
  | 'data_validation_error'
  | 'file_access_error'
  | 'database_error'
  | 'process_killed'
  | 'unknown_error';

export interface RetryStrategy {
  maxAttempts: number;
  baseDelay: number; // milliseconds
  maxDelay: number; // milliseconds
  multiplier: number;
  jitter: boolean;
}

export class ErrorRecoveryManager {
  private defaultRetryStrategy: RetryStrategy = {
    maxAttempts: 3,
    baseDelay: 1000,
    maxDelay: 30000,
    multiplier: 2,
    jitter: true,
  };

  private stageSpecificStrategies: Record<string, RetryStrategy> = {
    'validation': {
      maxAttempts: 2,
      baseDelay: 500,
      maxDelay: 5000,
      multiplier: 2,
      jitter: false,
    },
    'summarization': {
      maxAttempts: 3,
      baseDelay: 2000,
      maxDelay: 60000,
      multiplier: 2,
      jitter: true,
    },
    'classification': {
      maxAttempts: 4,
      baseDelay: 1000,
      maxDelay: 30000,
      multiplier: 1.5,
      jitter: true,
    },
    'response': {
      maxAttempts: 3,
      baseDelay: 3000,
      maxDelay: 60000,
      multiplier: 2,
      jitter: true,
    },
  };

  /**
   * Analyze error and determine recovery strategy
   */
  async analyzeError(
    episodeId: number,
    stage: string,
    runId: string,
    error: Error,
    attemptNumber: number
  ): Promise<ErrorContext> {
    const errorType = this.categorizeError(error);
    const systemState = await this.getSystemState();
    const suggestedAction = this.determineSuggestedAction(errorType, stage, attemptNumber, systemState);

    const errorContext: ErrorContext = {
      episodeId,
      stage,
      runId,
      errorType,
      errorMessage: error.message,
      stackTrace: error.stack,
      timestamp: new Date(),
      attemptNumber,
      systemState,
      suggestedAction,
    };

    // Store error context in database
    await this.storeErrorContext(errorContext);

    return errorContext;
  }

  /**
   * Categorize error based on error message and type
   */
  private categorizeError(error: Error): ErrorType {
    const message = error.message.toLowerCase();
    const stack = error.stack?.toLowerCase() || '';

    // Network-related errors
    if (message.includes('timeout') || message.includes('econnrefused') || message.includes('network')) {
      return 'network_timeout';
    }

    // API rate limiting
    if (message.includes('rate limit') || message.includes('too many requests') || message.includes('429')) {
      return 'api_rate_limit';
    }

    // Authentication errors
    if (message.includes('unauthorized') || message.includes('forbidden') || message.includes('401') || message.includes('403')) {
      return 'authentication_failure';
    }

    // Model availability
    if (message.includes('model not found') || message.includes('ollama') || message.includes('model unavailable')) {
      return 'model_unavailable';
    }

    // Resource constraints
    if (message.includes('out of memory') || message.includes('disk space') || message.includes('enospc')) {
      return 'insufficient_resources';
    }

    // Data validation
    if (message.includes('validation') || message.includes('invalid') || message.includes('schema')) {
      return 'data_validation_error';
    }

    // File access
    if (message.includes('enoent') || message.includes('eacces') || message.includes('file not found')) {
      return 'file_access_error';
    }

    // Database errors
    if (message.includes('database') || message.includes('connection') || stack.includes('prisma')) {
      return 'database_error';
    }

    // Process killed
    if (message.includes('sigterm') || message.includes('sigkill') || message.includes('killed')) {
      return 'process_killed';
    }

    return 'unknown_error';
  }

  /**
   * Get current system state for context
   */
  private async getSystemState(): Promise<SystemState> {
    const state: SystemState = {
      networkConnectivity: true,
      externalServiceStatus: {},
      activeProcesses: processTracker.getAllProcesses().size,
    };

    // Check external service availability
    state.externalServiceStatus = await this.checkExternalServices();

    return state;
  }

  /**
   * Check external service availability
   */
  private async checkExternalServices(): Promise<Record<string, 'available' | 'degraded' | 'unavailable'>> {
    const services: Record<string, 'available' | 'degraded' | 'unavailable'> = {};

    // Check Ollama
    try {
      const ollamaHost = process.env.WDF_OLLAMA_HOST || 'http://localhost:11434';
      const response = await fetch(`${ollamaHost}/api/tags`, {
        signal: AbortSignal.timeout(5000),
      });
      services.ollama = response.ok ? 'available' : 'degraded';
    } catch (error) {
      services.ollama = 'unavailable';
    }

    // Check Gemini API (indirect check via configured keys)
    try {
      const apiKeysResponse = await fetch(`${process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000'}/api/internal/api-keys`, {
        headers: { 'X-API-Key': process.env.WEB_API_KEY || 'development' },
        signal: AbortSignal.timeout(5000),
      });
      
      if (apiKeysResponse.ok) {
        const apiKeys = await apiKeysResponse.json();
        services.gemini = apiKeys.gemini?.api_key ? 'available' : 'unavailable';
      } else {
        services.gemini = 'unavailable';
      }
    } catch (error) {
      services.gemini = 'unavailable';
    }

    // Check database
    try {
      await prisma.$queryRaw`SELECT 1`;
      services.database = 'available';
    } catch (error) {
      services.database = 'unavailable';
    }

    return services;
  }

  /**
   * Determine suggested recovery action based on error context
   */
  private determineSuggestedAction(
    errorType: ErrorType,
    stage: string,
    attemptNumber: number,
    systemState: SystemState
  ): RecoveryAction {
    const strategy = this.stageSpecificStrategies[stage] || this.defaultRetryStrategy;

    switch (errorType) {
      case 'network_timeout':
        if (attemptNumber < strategy.maxAttempts) {
          return {
            type: 'retry',
            description: 'Network timeout detected. Will retry with exponential backoff.',
            automated: true,
            estimatedTime: Math.ceil(this.calculateDelay(attemptNumber, strategy) / 60000),
            riskLevel: 'low',
          };
        }
        return {
          type: 'manual_intervention',
          description: 'Persistent network issues. Check network connectivity and external service status.',
          automated: false,
          estimatedTime: 10,
          prerequisites: ['Check network connectivity', 'Verify external service status'],
          riskLevel: 'medium',
        };

      case 'api_rate_limit':
        return {
          type: 'retry',
          description: 'API rate limit hit. Will wait and retry with extended delay.',
          automated: true,
          estimatedTime: 5,
          riskLevel: 'low',
        };

      case 'authentication_failure':
        return {
          type: 'manual_intervention',
          description: 'Authentication failed. Check API keys configuration.',
          automated: false,
          estimatedTime: 5,
          prerequisites: ['Verify API keys in Settings', 'Check key permissions'],
          riskLevel: 'high',
        };

      case 'model_unavailable':
        if (stage === 'classification' || stage === 'response') {
          return {
            type: 'manual_intervention',
            description: 'Required model not available. Check Ollama service and pull missing models.',
            automated: false,
            estimatedTime: 30,
            prerequisites: ['Start Ollama service', 'Pull required models'],
            riskLevel: 'high',
          };
        }
        return {
          type: 'retry',
          description: 'Model temporarily unavailable. Will retry.',
          automated: true,
          estimatedTime: 2,
          riskLevel: 'medium',
        };

      case 'insufficient_resources':
        return {
          type: 'manual_intervention',
          description: 'Insufficient system resources. Free up memory/disk space or reduce concurrency.',
          automated: false,
          estimatedTime: 15,
          prerequisites: ['Free up disk space', 'Close other applications', 'Reduce worker count'],
          riskLevel: 'high',
        };

      case 'data_validation_error':
        if (stage === 'validation') {
          return {
            type: 'abort',
            description: 'Data validation failed. Fix input data before retrying.',
            automated: false,
            estimatedTime: 30,
            prerequisites: ['Fix episode data', 'Check transcript content', 'Verify configuration'],
            riskLevel: 'high',
          };
        }
        return {
          type: 'skip',
          description: 'Non-critical data validation error. Skip this stage and continue.',
          automated: true,
          estimatedTime: 1,
          riskLevel: 'medium',
        };

      case 'file_access_error':
        return {
          type: 'manual_intervention',
          description: 'File access error. Check file permissions and disk space.',
          automated: false,
          estimatedTime: 10,
          prerequisites: ['Check file permissions', 'Verify disk space', 'Check directory structure'],
          riskLevel: 'medium',
        };

      case 'database_error':
        if (systemState.externalServiceStatus.database === 'unavailable') {
          return {
            type: 'manual_intervention',
            description: 'Database unavailable. Check database service status.',
            automated: false,
            estimatedTime: 15,
            prerequisites: ['Start PostgreSQL service', 'Check database configuration'],
            riskLevel: 'high',
          };
        }
        if (attemptNumber < 2) {
          return {
            type: 'retry',
            description: 'Transient database error. Will retry.',
            automated: true,
            estimatedTime: 1,
            riskLevel: 'low',
          };
        }
        return {
          type: 'manual_intervention',
          description: 'Persistent database issues. Check database logs and connectivity.',
          automated: false,
          estimatedTime: 20,
          riskLevel: 'high',
        };

      case 'process_killed':
        return {
          type: 'retry',
          description: 'Process was terminated. Will restart.',
          automated: true,
          estimatedTime: 1,
          riskLevel: 'low',
        };

      default:
        if (attemptNumber < strategy.maxAttempts) {
          return {
            type: 'retry',
            description: 'Unknown error encountered. Will retry with standard strategy.',
            automated: true,
            estimatedTime: Math.ceil(this.calculateDelay(attemptNumber, strategy) / 60000),
            riskLevel: 'medium',
          };
        }
        return {
          type: 'manual_intervention',
          description: 'Persistent unknown error. Manual investigation required.',
          automated: false,
          estimatedTime: 30,
          prerequisites: ['Check logs for detailed error information', 'Verify system state'],
          riskLevel: 'high',
        };
    }
  }

  /**
   * Calculate delay for retry with exponential backoff
   */
  calculateDelay(attemptNumber: number, strategy: RetryStrategy): number {
    let delay = strategy.baseDelay * Math.pow(strategy.multiplier, attemptNumber - 1);
    delay = Math.min(delay, strategy.maxDelay);

    if (strategy.jitter) {
      // Add random jitter (±25%)
      const jitterRange = delay * 0.25;
      delay += (Math.random() * 2 - 1) * jitterRange;
    }

    return Math.max(delay, strategy.baseDelay);
  }

  /**
   * Execute recovery action
   */
  async executeRecoveryAction(errorContext: ErrorContext): Promise<boolean> {
    const { suggestedAction, episodeId, stage, runId } = errorContext;

    try {
      switch (suggestedAction.type) {
        case 'retry':
          await this.executeRetry(errorContext);
          return true;

        case 'skip':
          await this.executeSkip(errorContext);
          return true;

        case 'rollback':
          await this.executeRollback(errorContext);
          return false; // Rollback doesn't continue execution

        case 'manual_intervention':
        case 'abort':
          await this.logManualInterventionRequired(errorContext);
          return false;

        default:
          console.warn(`Unknown recovery action type: ${suggestedAction.type}`);
          return false;
      }
    } catch (recoveryError) {
      console.error('Error during recovery action execution:', recoveryError);
      return false;
    }
  }

  /**
   * Execute retry recovery action
   */
  private async executeRetry(errorContext: ErrorContext): Promise<void> {
    const { episodeId, stage, attemptNumber } = errorContext;
    const strategy = this.stageSpecificStrategies[stage] || this.defaultRetryStrategy;
    const delay = this.calculateDelay(attemptNumber, strategy);

    // Log retry attempt
    await this.logRecoveryAction(errorContext, 'retry', `Retrying after ${delay}ms delay`);

    // Wait for delay
    await new Promise(resolve => setTimeout(resolve, delay));

    // The actual retry will be handled by the pipeline controller
  }

  /**
   * Execute skip recovery action
   */
  private async executeSkip(errorContext: ErrorContext): Promise<void> {
    const { episodeId, stage } = errorContext;

    // Log skip action
    await this.logRecoveryAction(errorContext, 'skip', `Skipping stage ${stage} due to non-critical error`);

    // Mark stage as skipped in pipeline state
    // This will be handled by the pipeline controller
  }

  /**
   * Execute rollback recovery action
   */
  private async executeRollback(errorContext: ErrorContext): Promise<void> {
    const { episodeId, stage } = errorContext;

    // Log rollback action
    await this.logRecoveryAction(errorContext, 'rollback', `Rolling back due to critical error in stage ${stage}`);

    // Kill any running processes for this episode
    await processTracker.killProcessesForEpisode(episodeId);

    // Reset episode status
    await prisma.podcastEpisode.update({
      where: { id: episodeId },
      data: { status: 'ready' },
    });
  }

  /**
   * Log manual intervention requirement
   */
  private async logManualInterventionRequired(errorContext: ErrorContext): Promise<void> {
    const { suggestedAction } = errorContext;

    await this.logRecoveryAction(
      errorContext,
      'manual_intervention',
      `Manual intervention required: ${suggestedAction.description}`
    );

    // Emit SSE event for immediate user notification
    await this.emitSSEEvent({
      type: 'manual_intervention_required',
      episodeId: errorContext.episodeId.toString(),
      stage: errorContext.stage,
      errorType: errorContext.errorType,
      description: suggestedAction.description,
      prerequisites: suggestedAction.prerequisites,
      estimatedTime: suggestedAction.estimatedTime,
    });
  }

  /**
   * Store error context in database
   */
  private async storeErrorContext(errorContext: ErrorContext): Promise<void> {
    try {
      await prisma.pipelineError.create({
        data: {
          episodeId: errorContext.episodeId,
          runId: errorContext.runId,
          stage: errorContext.stage,
          errorType: errorContext.errorType,
          errorMessage: errorContext.errorMessage,
          stackTrace: errorContext.stackTrace,
          attemptNumber: errorContext.attemptNumber,
          systemState: errorContext.systemState as any,
          suggestedAction: errorContext.suggestedAction as any,
          timestamp: errorContext.timestamp,
        },
      });
    } catch (error) {
      console.error('Failed to store error context:', error);
    }
  }

  /**
   * Log recovery action
   */
  private async logRecoveryAction(
    errorContext: ErrorContext,
    actionType: string,
    description: string
  ): Promise<void> {
    try {
      await prisma.auditLog.create({
        data: {
          action: `recovery_${actionType}`,
          resourceType: 'pipeline',
          resourceId: errorContext.episodeId,
          metadata: {
            runId: errorContext.runId,
            stage: errorContext.stage,
            errorType: errorContext.errorType,
            attemptNumber: errorContext.attemptNumber,
            description,
          },
        },
      });
    } catch (error) {
      console.error('Failed to log recovery action:', error);
    }
  }

  /**
   * Emit SSE event
   */
  private async emitSSEEvent(eventData: any): Promise<void> {
    try {
      await fetch(`${process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000'}/api/internal/events`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': process.env.WEB_API_KEY || 'development',
        },
        body: JSON.stringify(eventData),
      });
    } catch (error) {
      console.error('Failed to emit SSE event:', error);
    }
  }

  /**
   * Get error recovery history for an episode
   */
  async getRecoveryHistory(episodeId: number, limit: number = 10): Promise<any[]> {
    try {
      return await prisma.pipelineError.findMany({
        where: { episodeId },
        orderBy: { timestamp: 'desc' },
        take: limit,
        select: {
          id: true,
          stage: true,
          errorType: true,
          errorMessage: true,
          attemptNumber: true,
          suggestedAction: true,
          timestamp: true,
        },
      });
    } catch (error) {
      console.error('Failed to get recovery history:', error);
      return [];
    }
  }

  /**
   * Get error statistics for analytics
   */
  async getErrorStatistics(days: number = 30): Promise<any> {
    try {
      const since = new Date();
      since.setDate(since.getDate() - days);

      const errorsByType = await prisma.pipelineError.groupBy({
        by: ['errorType'],
        where: {
          timestamp: { gte: since },
        },
        _count: {
          errorType: true,
        },
      });

      const errorsByStage = await prisma.pipelineError.groupBy({
        by: ['stage'],
        where: {
          timestamp: { gte: since },
        },
        _count: {
          stage: true,
        },
      });

      return {
        byType: errorsByType,
        byStage: errorsByStage,
        period: days,
      };
    } catch (error) {
      console.error('Failed to get error statistics:', error);
      return { byType: [], byStage: [], period: days };
    }
  }
}