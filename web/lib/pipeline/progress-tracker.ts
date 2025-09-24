/**
 * Pipeline Progress Tracker
 * 
 * Advanced progress tracking with:
 * - Real-time stage progress monitoring
 * - Estimated time remaining calculations
 * - Resource usage tracking
 * - Performance metrics collection
 * - Visual progress data for UI components
 */

import { prisma } from '@/lib/db';

export interface ProgressMetrics {
  episodeId: number;
  runId: string;
  overallProgress: number; // 0-100
  currentStage?: StageProgress;
  completedStages: StageProgress[];
  upcomingStages: StageProgress[];
  estimatedTimeRemaining: number; // minutes
  estimatedCompletion: Date;
  startedAt: Date;
  elapsedTime: number; // minutes
  throughputMetrics: ThroughputMetrics;
  resourceUsage: ResourceUsage;
}

export interface StageProgress {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  progress: number; // 0-100
  startedAt?: Date;
  completedAt?: Date;
  duration?: number; // minutes
  estimatedDuration: number; // minutes
  remainingTime?: number; // minutes
  retryCount: number;
  errorMessage?: string;
  metrics?: StageMetrics;
}

export interface StageMetrics {
  itemsProcessed: number;
  totalItems: number;
  processingRate: number; // items per minute
  apiCallsUsed: number;
  tokensUsed: number;
  costIncurred: number;
  memoryUsed?: number; // MB
  cpuUsage?: number; // percentage
}

export interface ThroughputMetrics {
  tweetsProcessed: number;
  responsesGenerated: number;
  averageProcessingTime: number; // seconds per item
  apiCallsPerMinute: number;
  tokensPerMinute: number;
  costPerHour: number;
}

export interface ResourceUsage {
  memoryUsage: number; // MB
  cpuUsage: number; // percentage
  diskIO: number; // MB/s
  networkIO: number; // MB/s
  activeConnections: number;
  queueLength: number;
}

export class ProgressTracker {
  private progressCache = new Map<number, ProgressMetrics>();
  private stageStartTimes = new Map<string, Date>();
  private performanceHistory = new Map<string, number[]>(); // stage -> duration history

  /**
   * Initialize progress tracking for a pipeline run
   */
  async initializeProgress(
    episodeId: number,
    runId: string,
    stages: { id: string; name: string; estimatedDuration: number }[]
  ): Promise<ProgressMetrics> {
    const now = new Date();
    
    const progress: ProgressMetrics = {
      episodeId,
      runId,
      overallProgress: 0,
      completedStages: [],
      upcomingStages: stages.map(stage => ({
        ...stage,
        status: 'pending',
        progress: 0,
        retryCount: 0,
      })),
      estimatedTimeRemaining: stages.reduce((total, stage) => total + stage.estimatedDuration, 0),
      estimatedCompletion: new Date(now.getTime() + stages.reduce((total, stage) => total + stage.estimatedDuration, 0) * 60000),
      startedAt: now,
      elapsedTime: 0,
      throughputMetrics: {
        tweetsProcessed: 0,
        responsesGenerated: 0,
        averageProcessingTime: 0,
        apiCallsPerMinute: 0,
        tokensPerMinute: 0,
        costPerHour: 0,
      },
      resourceUsage: {
        memoryUsage: 0,
        cpuUsage: 0,
        diskIO: 0,
        networkIO: 0,
        activeConnections: 0,
        queueLength: 0,
      },
    };

    this.progressCache.set(episodeId, progress);
    return progress;
  }

  /**
   * Update stage progress
   */
  async updateStageProgress(
    episodeId: number,
    stageId: string,
    updates: Partial<StageProgress>
  ): Promise<ProgressMetrics | null> {
    const progress = this.progressCache.get(episodeId);
    if (!progress) return null;

    // Find stage in appropriate array
    let stageToUpdate: StageProgress | undefined;
    let stageArray: StageProgress[] | undefined;

    if (progress.currentStage?.id === stageId) {
      stageToUpdate = progress.currentStage;
    } else {
      stageToUpdate = progress.upcomingStages.find(s => s.id === stageId) ||
                    progress.completedStages.find(s => s.id === stageId);
      
      if (stageToUpdate) {
        stageArray = progress.upcomingStages.includes(stageToUpdate) 
          ? progress.upcomingStages 
          : progress.completedStages;
      }
    }

    if (!stageToUpdate) return progress;

    // Update stage properties
    Object.assign(stageToUpdate, updates);

    // Handle stage status changes
    if (updates.status) {
      switch (updates.status) {
        case 'running':
          if (progress.currentStage?.id !== stageId) {
            // Move from upcoming to current
            progress.upcomingStages = progress.upcomingStages.filter(s => s.id !== stageId);
            progress.currentStage = stageToUpdate;
            stageToUpdate.startedAt = new Date();
            this.stageStartTimes.set(`${episodeId}-${stageId}`, stageToUpdate.startedAt);
          }
          break;

        case 'completed':
          if (progress.currentStage?.id === stageId) {
            // Move from current to completed
            stageToUpdate.completedAt = new Date();
            stageToUpdate.progress = 100;
            
            if (stageToUpdate.startedAt) {
              stageToUpdate.duration = (stageToUpdate.completedAt.getTime() - stageToUpdate.startedAt.getTime()) / 60000;
              this.recordStagePerformance(stageId, stageToUpdate.duration);
            }
            
            progress.completedStages.push(stageToUpdate);
            progress.currentStage = undefined;
          }
          break;

        case 'failed':
          if (progress.currentStage?.id === stageId) {
            progress.currentStage = undefined;
          }
          break;

        case 'skipped':
          // Remove from upcoming and add to completed
          progress.upcomingStages = progress.upcomingStages.filter(s => s.id !== stageId);
          stageToUpdate.progress = 100;
          stageToUpdate.completedAt = new Date();
          progress.completedStages.push(stageToUpdate);
          break;
      }
    }

    // Recalculate overall progress and time estimates
    this.recalculateProgress(progress);

    // Store updated progress
    this.progressCache.set(episodeId, progress);

    // Persist to database
    await this.persistProgress(progress);

    return progress;
  }

  /**
   * Update stage metrics (items processed, API calls, etc.)
   */
  async updateStageMetrics(
    episodeId: number,
    stageId: string,
    metrics: Partial<StageMetrics>
  ): Promise<void> {
    const progress = this.progressCache.get(episodeId);
    if (!progress) return;

    const stage = progress.currentStage?.id === stageId 
      ? progress.currentStage
      : progress.completedStages.find(s => s.id === stageId) ||
        progress.upcomingStages.find(s => s.id === stageId);

    if (!stage) return;

    if (!stage.metrics) {
      stage.metrics = {
        itemsProcessed: 0,
        totalItems: 0,
        processingRate: 0,
        apiCallsUsed: 0,
        tokensUsed: 0,
        costIncurred: 0,
      };
    }

    Object.assign(stage.metrics, metrics);

    // Update stage progress based on items processed
    if (stage.metrics.totalItems > 0) {
      stage.progress = Math.round((stage.metrics.itemsProcessed / stage.metrics.totalItems) * 100);
    }

    // Calculate processing rate
    if (stage.startedAt && stage.metrics.itemsProcessed > 0) {
      const elapsedMinutes = (Date.now() - stage.startedAt.getTime()) / 60000;
      stage.metrics.processingRate = stage.metrics.itemsProcessed / elapsedMinutes;
      
      // Estimate remaining time
      const remainingItems = stage.metrics.totalItems - stage.metrics.itemsProcessed;
      if (stage.metrics.processingRate > 0) {
        stage.remainingTime = remainingItems / stage.metrics.processingRate;
      }
    }

    // Update throughput metrics
    this.updateThroughputMetrics(progress);

    this.progressCache.set(episodeId, progress);
  }

  /**
   * Get current progress for an episode
   */
  getProgress(episodeId: number): ProgressMetrics | null {
    return this.progressCache.get(episodeId) || null;
  }

  /**
   * Record stage performance for future estimates
   */
  private recordStagePerformance(stageId: string, duration: number): void {
    if (!this.performanceHistory.has(stageId)) {
      this.performanceHistory.set(stageId, []);
    }
    
    const history = this.performanceHistory.get(stageId)!;
    history.push(duration);
    
    // Keep only last 10 records for rolling average
    if (history.length > 10) {
      history.shift();
    }
  }

  /**
   * Get improved time estimate based on historical performance
   */
  getImprovedEstimate(stageId: string, baseEstimate: number): number {
    const history = this.performanceHistory.get(stageId);
    if (!history || history.length === 0) {
      return baseEstimate;
    }

    // Calculate weighted average (more recent entries have higher weight)
    let weightedSum = 0;
    let weightSum = 0;
    
    history.forEach((duration, index) => {
      const weight = index + 1; // More recent = higher weight
      weightedSum += duration * weight;
      weightSum += weight;
    });

    const average = weightedSum / weightSum;
    
    // Blend historical average with base estimate (70% historical, 30% base)
    return Math.round(average * 0.7 + baseEstimate * 0.3);
  }

  /**
   * Recalculate overall progress and time estimates
   */
  private recalculateProgress(progress: ProgressMetrics): void {
    const totalStages = progress.completedStages.length + 
                       progress.upcomingStages.length + 
                       (progress.currentStage ? 1 : 0);
    
    if (totalStages === 0) return;

    // Calculate overall progress
    let totalProgress = progress.completedStages.length * 100;
    if (progress.currentStage) {
      totalProgress += progress.currentStage.progress;
    }
    progress.overallProgress = Math.round(totalProgress / totalStages);

    // Calculate elapsed time
    progress.elapsedTime = (Date.now() - progress.startedAt.getTime()) / 60000;

    // Estimate remaining time
    let estimatedRemaining = 0;
    
    // Add current stage remaining time
    if (progress.currentStage?.remainingTime) {
      estimatedRemaining += progress.currentStage.remainingTime;
    } else if (progress.currentStage) {
      const stageProgress = progress.currentStage.progress / 100;
      const remainingProgress = 1 - stageProgress;
      estimatedRemaining += progress.currentStage.estimatedDuration * remainingProgress;
    }
    
    // Add upcoming stages time (with improved estimates)
    progress.upcomingStages.forEach(stage => {
      estimatedRemaining += this.getImprovedEstimate(stage.id, stage.estimatedDuration);
    });

    progress.estimatedTimeRemaining = Math.round(estimatedRemaining);
    progress.estimatedCompletion = new Date(Date.now() + estimatedRemaining * 60000);
  }

  /**
   * Update throughput metrics
   */
  private updateThroughputMetrics(progress: ProgressMetrics): void {
    const elapsedHours = progress.elapsedTime / 60;
    if (elapsedHours === 0) return;

    let totalTweets = 0;
    let totalResponses = 0;
    let totalApiCalls = 0;
    let totalTokens = 0;
    let totalCost = 0;
    let totalProcessingTime = 0;
    let processedItems = 0;

    // Aggregate metrics from all stages
    [...progress.completedStages, ...(progress.currentStage ? [progress.currentStage] : [])].forEach(stage => {
      if (stage.metrics) {
        if (stage.id === 'classification' || stage.id === 'scraping') {
          totalTweets += stage.metrics.itemsProcessed;
        }
        if (stage.id === 'response') {
          totalResponses += stage.metrics.itemsProcessed;
        }
        totalApiCalls += stage.metrics.apiCallsUsed;
        totalTokens += stage.metrics.tokensUsed;
        totalCost += stage.metrics.costIncurred;
        
        if (stage.duration && stage.metrics.itemsProcessed > 0) {
          totalProcessingTime += stage.duration;
          processedItems += stage.metrics.itemsProcessed;
        }
      }
    });

    progress.throughputMetrics = {
      tweetsProcessed: totalTweets,
      responsesGenerated: totalResponses,
      averageProcessingTime: processedItems > 0 ? (totalProcessingTime * 60) / processedItems : 0, // seconds per item
      apiCallsPerMinute: totalApiCalls / progress.elapsedTime,
      tokensPerMinute: totalTokens / progress.elapsedTime,
      costPerHour: totalCost / elapsedHours,
    };
  }

  /**
   * Update resource usage metrics
   */
  async updateResourceUsage(episodeId: number, usage: Partial<ResourceUsage>): Promise<void> {
    const progress = this.progressCache.get(episodeId);
    if (!progress) return;

    Object.assign(progress.resourceUsage, usage);
    this.progressCache.set(episodeId, progress);
  }

  /**
   * Persist progress to database
   */
  private async persistProgress(progress: ProgressMetrics): Promise<void> {
    try {
      await prisma.pipelineRun.upsert({
        where: { runId: progress.runId },
        update: {
          progress: progress.overallProgress,
          currentStage: progress.currentStage?.id,
          estimatedCompletion: progress.estimatedCompletion,
          metadata: {
            stageProgress: {
              completed: progress.completedStages,
              current: progress.currentStage,
              upcoming: progress.upcomingStages,
            },
            throughputMetrics: progress.throughputMetrics,
            resourceUsage: progress.resourceUsage,
          },
        },
        create: {
          runId: progress.runId,
          episodeId: progress.episodeId,
          stage: 'full_pipeline',
          status: 'running',
          progress: progress.overallProgress,
          currentStage: progress.currentStage?.id,
          startedAt: progress.startedAt,
          estimatedCompletion: progress.estimatedCompletion,
          metadata: {
            stageProgress: {
              completed: progress.completedStages,
              current: progress.currentStage,
              upcoming: progress.upcomingStages,
            },
            throughputMetrics: progress.throughputMetrics,
            resourceUsage: progress.resourceUsage,
          },
        },
      });
    } catch (error) {
      console.error('Failed to persist progress:', error);
    }
  }

  /**
   * Load progress from database
   */
  async loadProgress(episodeId: number): Promise<ProgressMetrics | null> {
    try {
      const pipelineRun = await prisma.pipelineRun.findFirst({
        where: { 
          episodeId,
          stage: 'full_pipeline',
          status: { in: ['running', 'validating', 'paused'] },
        },
        orderBy: { startedAt: 'desc' },
      });

      if (!pipelineRun || !pipelineRun.metadata) return null;

      const metadata = pipelineRun.metadata as any;
      const stageProgress = metadata.stageProgress || {};

      const progress: ProgressMetrics = {
        episodeId,
        runId: pipelineRun.runId,
        overallProgress: pipelineRun.progress || 0,
        currentStage: stageProgress.current,
        completedStages: stageProgress.completed || [],
        upcomingStages: stageProgress.upcoming || [],
        estimatedTimeRemaining: 0,
        estimatedCompletion: pipelineRun.estimatedCompletion || new Date(),
        startedAt: pipelineRun.startedAt,
        elapsedTime: (Date.now() - pipelineRun.startedAt.getTime()) / 60000,
        throughputMetrics: metadata.throughputMetrics || {
          tweetsProcessed: 0,
          responsesGenerated: 0,
          averageProcessingTime: 0,
          apiCallsPerMinute: 0,
          tokensPerMinute: 0,
          costPerHour: 0,
        },
        resourceUsage: metadata.resourceUsage || {
          memoryUsage: 0,
          cpuUsage: 0,
          diskIO: 0,
          networkIO: 0,
          activeConnections: 0,
          queueLength: 0,
        },
      };

      this.recalculateProgress(progress);
      this.progressCache.set(episodeId, progress);

      return progress;
    } catch (error) {
      console.error('Failed to load progress:', error);
      return null;
    }
  }

  /**
   * Clean up progress tracking for completed/failed pipelines
   */
  cleanup(episodeId: number): void {
    this.progressCache.delete(episodeId);
  }

  /**
   * Get performance statistics for analytics
   */
  getPerformanceStatistics(): Record<string, { average: number; median: number; count: number }> {
    const stats: Record<string, { average: number; median: number; count: number }> = {};

    this.performanceHistory.forEach((durations, stageId) => {
      if (durations.length === 0) return;

      const sorted = [...durations].sort((a, b) => a - b);
      const average = durations.reduce((sum, d) => sum + d, 0) / durations.length;
      const median = sorted.length % 2 === 0
        ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
        : sorted[Math.floor(sorted.length / 2)];

      stats[stageId] = {
        average: Math.round(average * 100) / 100,
        median: Math.round(median * 100) / 100,
        count: durations.length,
      };
    });

    return stats;
  }
}