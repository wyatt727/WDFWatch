import { NextRequest, NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

/**
 * GET /api/claude/cost-tracking
 * Get Claude API cost tracking data
 */
export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const days = parseInt(searchParams.get('days') || '30');
    const episodeId = searchParams.get('episodeId');
    const mode = searchParams.get('mode');
    
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - days);
    
    // Get cost summary
    const costSummary = await prisma.$queryRaw<any[]>`
      SELECT 
        mode,
        SUM(total_cost_usd) as total_cost,
        SUM(run_count) as total_runs,
        AVG(total_cost_usd / NULLIF(run_count, 0)) as avg_cost_per_run
      FROM claude_costs
      WHERE date >= ${startDate}
      ${mode ? prisma.$queryRaw`AND mode = ${mode}` : prisma.$queryRaw``}
      GROUP BY mode
      ORDER BY total_cost DESC
    `;
    
    // Get daily costs for chart
    const dailyCosts = await prisma.$queryRaw<any[]>`
      SELECT 
        date,
        SUM(total_cost_usd) as daily_cost,
        SUM(run_count) as daily_runs
      FROM claude_costs
      WHERE date >= ${startDate}
      ${mode ? prisma.$queryRaw`AND mode = ${mode}` : prisma.$queryRaw``}
      GROUP BY date
      ORDER BY date ASC
    `;
    
    // Get episode-specific costs if requested
    let episodeCosts = null;
    if (episodeId) {
      episodeCosts = await prisma.$queryRaw<any[]>`
        SELECT 
          stage,
          COUNT(*) as run_count,
          SUM(cost_usd) as total_cost,
          AVG(cost_usd) as avg_cost,
          AVG(duration_seconds) as avg_duration
        FROM claude_pipeline_runs
        WHERE episode_id = ${parseInt(episodeId)}
        AND status = 'completed'
        GROUP BY stage
        ORDER BY total_cost DESC
      `;
    }
    
    // Get total costs
    const totals = await prisma.$queryRaw<any[]>`
      SELECT 
        SUM(total_cost_usd) as total_cost,
        SUM(run_count) as total_runs
      FROM claude_costs
      WHERE date >= ${startDate}
    `;
    
    // Get recent runs
    const recentRuns = await prisma.claudePipelineRun.findMany({
      where: {
        status: 'completed',
        startedAt: { gte: startDate }
      },
      orderBy: { startedAt: 'desc' },
      take: 10,
      include: {
        episode: {
          select: {
            id: true,
            title: true
          }
        }
      }
    });
    
    return NextResponse.json({
      summary: {
        byMode: costSummary,
        totalCost: totals[0]?.total_cost || 0,
        totalRuns: totals[0]?.total_runs || 0,
        periodDays: days
      },
      dailyCosts,
      episodeCosts,
      recentRuns: recentRuns.map(run => ({
        runId: run.runId,
        episodeId: run.episodeId,
        episodeTitle: run.episode?.title,
        stage: run.stage,
        cost: run.costUsd,
        inputTokens: run.inputTokens,
        outputTokens: run.outputTokens,
        duration: run.durationSeconds,
        startedAt: run.startedAt
      }))
    });
    
  } catch (error) {
    console.error('Failed to get Claude cost tracking:', error);
    return NextResponse.json(
      { error: 'Failed to get cost tracking data' },
      { status: 500 }
    );
  }
}

/**
 * POST /api/claude/cost-tracking
 * Record Claude API usage and costs
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const {
      mode,
      inputTokens,
      outputTokens,
      costUsd,
      episodeId,
      runId
    } = body;
    
    if (!mode || costUsd === undefined) {
      return NextResponse.json(
        { error: 'Mode and cost are required' },
        { status: 400 }
      );
    }
    
    // Update or create daily cost record
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    const existingCost = await prisma.claudeCost.findFirst({
      where: {
        date: today,
        mode
      }
    });
    
    if (existingCost) {
      // Update existing record
      await prisma.claudeCost.update({
        where: { id: existingCost.id },
        data: {
          totalInputTokens: existingCost.totalInputTokens + BigInt(inputTokens || 0),
          totalOutputTokens: existingCost.totalOutputTokens + BigInt(outputTokens || 0),
          totalCostUsd: existingCost.totalCostUsd.add(costUsd),
          runCount: existingCost.runCount + 1
        }
      });
    } else {
      // Create new record
      await prisma.claudeCost.create({
        data: {
          date: today,
          mode,
          totalInputTokens: BigInt(inputTokens || 0),
          totalOutputTokens: BigInt(outputTokens || 0),
          totalCostUsd: costUsd,
          runCount: 1
        }
      });
    }
    
    // If associated with a pipeline run, update that too
    if (runId) {
      await prisma.claudePipelineRun.updateMany({
        where: { runId },
        data: {
          inputTokens: inputTokens || 0,
          outputTokens: outputTokens || 0,
          costUsd
        }
      });
    }
    
    return NextResponse.json({
      success: true,
      message: 'Cost tracking recorded'
    });
    
  } catch (error) {
    console.error('Failed to record Claude costs:', error);
    return NextResponse.json(
      { error: 'Failed to record costs' },
      { status: 500 }
    );
  }
}

/**
 * DELETE /api/claude/cost-tracking
 * Reset cost tracking data (admin only)
 */
export async function DELETE(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const confirmReset = searchParams.get('confirm') === 'true';
    
    if (!confirmReset) {
      return NextResponse.json(
        { error: 'Confirmation required to reset cost data' },
        { status: 400 }
      );
    }
    
    // Delete all cost records
    const deleted = await prisma.claudeCost.deleteMany({});
    
    return NextResponse.json({
      success: true,
      message: `Deleted ${deleted.count} cost records`
    });
    
  } catch (error) {
    console.error('Failed to reset cost tracking:', error);
    return NextResponse.json(
      { error: 'Failed to reset cost tracking' },
      { status: 500 }
    );
  }
}