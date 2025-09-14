/**
 * Pipeline Validation API Endpoint
 * 
 * Provides detailed pre-flight validation for pipeline execution including:
 * - Episode content validation
 * - API key validation  
 * - Model availability checks
 * - System resource validation
 * - Configuration validation
 */

import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';
import { PipelineValidator } from '@/lib/pipeline/validator';

export const dynamic = 'force-dynamic';

/**
 * POST - Run comprehensive pipeline validation
 */
export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const episodeId = parseInt(params.id);
    
    // Check if episode exists
    const episode = await prisma.podcastEpisode.findUnique({
      where: { id: episodeId },
      select: {
        id: true,
        title: true,
        pipelineType: true,
        transcriptText: true,
        videoUrl: true,
        status: true,
      },
    });

    if (!episode) {
      return NextResponse.json(
        { error: 'Episode not found' },
        { status: 404 }
      );
    }

    const pipelineType = episode.pipelineType as 'claude' | 'legacy';
    const validator = new PipelineValidator();
    
    // Run comprehensive validation
    const validationResults = await validator.validatePipeline(episodeId, pipelineType);

    // Store validation results in database
    await prisma.auditLog.create({
      data: {
        action: 'pipeline_validation_run',
        resourceType: 'episode',
        resourceId: episodeId,
        metadata: {
          pipelineType,
          validationScore: validationResults.score,
          isValid: validationResults.isValid,
          errorCount: validationResults.errors.length,
          warningCount: validationResults.warnings.length,
          checkCount: validationResults.checks.length,
          estimatedResolutionTime: validationResults.estimatedIssueResolutionTime,
        },
      },
    });

    // Create response with actionable information
    const response = {
      episodeId,
      pipelineType,
      validation: validationResults,
      readinessStatus: getReadinessStatus(validationResults),
      nextSteps: getNextSteps(validationResults),
      estimatedFixTime: validationResults.estimatedIssueResolutionTime,
    };

    return NextResponse.json(response);

  } catch (error) {
    console.error('Pipeline validation error:', error);
    
    // Log validation failure
    const episodeId = parseInt(params.id);
    if (!isNaN(episodeId)) {
      await prisma.auditLog.create({
        data: {
          action: 'pipeline_validation_failed',
          resourceType: 'episode',
          resourceId: episodeId,
          metadata: {
            error: error instanceof Error ? error.message : 'Unknown error',
          },
        },
      });
    }

    return NextResponse.json(
      { error: 'Validation failed', details: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}

/**
 * GET - Get last validation results
 */
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const episodeId = parseInt(params.id);
    
    // Get most recent validation audit log
    const lastValidation = await prisma.auditLog.findFirst({
      where: {
        resourceType: 'episode',
        resourceId: episodeId,
        action: { in: ['pipeline_validation_run', 'pipeline_validated'] },
      },
      orderBy: { createdAt: 'desc' },
    });

    if (!lastValidation) {
      return NextResponse.json({
        episodeId,
        hasValidation: false,
        message: 'No validation results found. Run validation first.',
      });
    }

    const metadata = lastValidation.metadata as any;
    
    return NextResponse.json({
      episodeId,
      hasValidation: true,
      lastValidated: lastValidation.createdAt,
      validationScore: metadata.validationScore,
      isValid: metadata.isValid,
      errorCount: metadata.errorCount,
      warningCount: metadata.warningCount,
      estimatedResolutionTime: metadata.estimatedResolutionTime,
      details: metadata.validationResults || metadata,
    });

  } catch (error) {
    console.error('Failed to get validation results:', error);
    return NextResponse.json(
      { error: 'Failed to get validation results' },
      { status: 500 }
    );
  }
}

/**
 * Determine overall readiness status
 */
function getReadinessStatus(validation: any): {
  status: 'ready' | 'needs_attention' | 'blocked';
  color: 'green' | 'yellow' | 'red';
  message: string;
} {
  if (validation.isValid && validation.score >= 90) {
    return {
      status: 'ready',
      color: 'green',
      message: 'Pipeline is ready to run with no issues detected.',
    };
  }
  
  if (validation.isValid && validation.score >= 70) {
    return {
      status: 'needs_attention',
      color: 'yellow',
      message: 'Pipeline can run but has some warnings that should be addressed.',
    };
  }
  
  if (validation.isValid && validation.score >= 50) {
    return {
      status: 'needs_attention',
      color: 'yellow',
      message: 'Pipeline can run but has several issues that may impact performance.',
    };
  }
  
  return {
    status: 'blocked',
    color: 'red',
    message: 'Critical issues prevent pipeline execution. Fix required errors before proceeding.',
  };
}

/**
 * Generate actionable next steps
 */
function getNextSteps(validation: any): Array<{
  priority: 'high' | 'medium' | 'low';
  action: string;
  description: string;
  estimatedTime: number;
  category: string;
}> {
  const steps: Array<{
    priority: 'high' | 'medium' | 'low';
    action: string;
    description: string;
    estimatedTime: number;
    category: string;
  }> = [];

  // Process critical errors first
  validation.checks
    .filter((check: any) => check.status === 'fail' && check.category === 'critical')
    .forEach((check: any) => {
      steps.push({
        priority: 'high',
        action: check.name,
        description: check.suggestion || check.message,
        estimatedTime: check.resolutionTime || 5,
        category: 'Critical Issue',
      });
    });

  // Process warnings
  validation.checks
    .filter((check: any) => check.status === 'fail' && check.category === 'warning')
    .forEach((check: any) => {
      steps.push({
        priority: 'medium',
        action: check.name,
        description: check.suggestion || check.message,
        estimatedTime: check.resolutionTime || 3,
        category: 'Warning',
      });
    });

  // Add general recommendations
  if (validation.score < 80) {
    steps.push({
      priority: 'low',
      action: 'Review Configuration',
      description: 'Review all settings to ensure optimal pipeline performance.',
      estimatedTime: 10,
      category: 'Optimization',
    });
  }

  // Sort by priority and estimated impact
  steps.sort((a, b) => {
    const priorityOrder = { high: 3, medium: 2, low: 1 };
    return priorityOrder[b.priority] - priorityOrder[a.priority];
  });

  return steps.slice(0, 8); // Limit to top 8 most important steps
}