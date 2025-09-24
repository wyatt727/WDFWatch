/**
 * Analytics API route for WDFWatch
 * Provides aggregated data for the analytics dashboard
 * 
 * Connected files:
 * - /web/lib/db.ts - Database connection
 * - /web/app/(dashboard)/analytics/page.tsx - Analytics dashboard UI
 */

import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';
import { startOfDay, subDays, format } from 'date-fns';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const days = parseInt(searchParams.get('days') || '30');
    
    const startDate = startOfDay(subDays(new Date(), days));
    
    // Return simplified analytics
    const analytics = await getSimplifiedAnalytics(startDate);
    return NextResponse.json(analytics);
  } catch (error) {
    console.error('Analytics API error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch analytics data' },
      { status: 500 }
    );
  }
}

async function getSimplifiedAnalytics(startDate: Date) {
  // Get basic counts that actually exist in the database
  const [totalTweets, totalDrafts, totalEpisodes, recentTweets] = await Promise.all([
    prisma.tweet.count(),
    prisma.draftReply.count(),
    prisma.podcastEpisode.count(),
    prisma.tweet.count({
      where: { createdAt: { gte: startDate } }
    })
  ]);

  // Get drafts by status
  const draftsByStatus = await prisma.draftReply.groupBy({
    by: ['status'],
    _count: { id: true }
  });

  const draftCounts = draftsByStatus.reduce((acc, item) => {
    acc[item.status] = item._count.id;
    return acc;
  }, {} as Record<string, number>);

  // Get episodes with tweet counts
  const episodesWithTweets = await prisma.podcastEpisode.findMany({
    select: {
      id: true,
      title: true,
      createdAt: true,
      _count: {
        select: { tweets: true }
      }
    },
    orderBy: { createdAt: 'desc' },
    take: 10
  });

  return {
    overview: {
      totalTweets,
      totalDrafts,
      totalEpisodes,
      recentTweets,
      pendingDrafts: draftCounts.pending || 0,
      approvedDrafts: draftCounts.approved || 0,
      rejectedDrafts: draftCounts.rejected || 0,
      draftApprovalRate: totalDrafts > 0 
        ? ((draftCounts.approved || 0) / totalDrafts * 100).toFixed(1) + '%'
        : '0%'
    },
    recentEpisodes: episodesWithTweets.map(ep => ({
      id: ep.id,
      title: ep.title,
      tweetCount: ep._count.tweets,
      createdAt: ep.createdAt
    })),
    draftsByStatus: draftCounts
  };
}