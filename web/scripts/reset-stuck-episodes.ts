#!/usr/bin/env tsx
/**
 * Reset Stuck Episodes Migration Script
 * 
 * Handles episodes that are stuck in 'processing' state from before the process tracking
 * system was implemented. These episodes have no corresponding running processes and
 * cannot be deleted through the normal flow.
 * 
 * Usage:
 *   npx tsx scripts/reset-stuck-episodes.ts [--dry-run] [--older-than-hours=24]
 */

import { config } from 'dotenv';
import { resolve } from 'path';

// Load environment variables from .env.local
config({ path: resolve(__dirname, '../.env.local') });

import { PrismaClient } from '@prisma/client';
import { processTracker } from '../lib/process-tracker';

const prisma = new PrismaClient();

interface StuckEpisode {
  id: number;
  title: string;
  status: string;
  updatedAt: Date;
  hasRunningProcess: boolean;
  ageInHours: number;
}

async function findStuckEpisodes(olderThanHours: number = 24): Promise<StuckEpisode[]> {
  // Find episodes in processing state
  const processingEpisodes = await prisma.podcastEpisode.findMany({
    where: {
      status: 'processing',
    },
    select: {
      id: true,
      title: true,
      status: true,
      updatedAt: true,
    },
  });

  console.log(`Found ${processingEpisodes.length} episodes in 'processing' state`);

  const stuckEpisodes: StuckEpisode[] = [];
  const cutoffTime = new Date(Date.now() - (olderThanHours * 60 * 60 * 1000));

  for (const episode of processingEpisodes) {
    // Check if there's actually a running process for this episode
    const runningProcesses = processTracker.getProcessesForEpisode(episode.id);
    const hasRunningProcess = runningProcesses.length > 0;

    // Calculate age
    const ageInHours = (Date.now() - episode.updatedAt.getTime()) / (1000 * 60 * 60);

    // Consider it stuck if:
    // 1. No running process AND older than cutoff time
    // 2. OR no running process AND older than 1 hour (for safety)
    const isStuck = !hasRunningProcess && (
      episode.updatedAt < cutoffTime || ageInHours > 1
    );

    if (isStuck) {
      stuckEpisodes.push({
        id: episode.id,
        title: episode.title,
        status: episode.status,
        updatedAt: episode.updatedAt,
        hasRunningProcess,
        ageInHours,
      });
    }
  }

  return stuckEpisodes;
}

async function resetStuckEpisodes(episodes: StuckEpisode[], dryRun: boolean = false): Promise<void> {
  if (episodes.length === 0) {
    console.log('✅ No stuck episodes found!');
    return;
  }

  console.log(`\n📋 Found ${episodes.length} stuck episodes:`);
  episodes.forEach((ep, index) => {
    console.log(`  ${index + 1}. "${ep.title}" (ID: ${ep.id})`);
    console.log(`     Status: ${ep.status}, Age: ${ep.ageInHours.toFixed(1)} hours`);
    console.log(`     Last updated: ${ep.updatedAt.toISOString()}`);
    console.log(`     Has running process: ${ep.hasRunningProcess ? '✓' : '✗'}`);
    console.log('');
  });

  if (dryRun) {
    console.log('🔍 DRY RUN: Would reset these episodes to "ready" status');
    console.log('   Run without --dry-run to actually perform the reset');
    return;
  }

  console.log('🔧 Resetting stuck episodes...');

  const resetPromises = episodes.map(async (episode) => {
    try {
      // Reset episode status to 'ready'
      await prisma.podcastEpisode.update({
        where: { id: episode.id },
        data: { 
          status: 'ready',
          updatedAt: new Date(),
        },
      });

      // Create audit log entry
      await prisma.auditLog.create({
        data: {
          action: 'episode_reset_from_stuck',
          resourceType: 'episode',
          resourceId: episode.id,
          oldValue: {
            status: episode.status,
            updatedAt: episode.updatedAt,
          },
          newValue: {
            status: 'ready',
            updatedAt: new Date(),
          },
          metadata: {
            ageInHours: episode.ageInHours,
            hadRunningProcess: episode.hasRunningProcess,
            resetReason: 'stuck_processing_without_running_process',
          },
        },
      });

      console.log(`  ✅ Reset episode "${episode.title}" (ID: ${episode.id})`);
      return { success: true, episode };
    } catch (error) {
      console.error(`  ❌ Failed to reset episode "${episode.title}" (ID: ${episode.id}):`, error);
      return { success: false, episode, error };
    }
  });

  const results = await Promise.all(resetPromises);
  const successful = results.filter(r => r.success).length;
  const failed = results.filter(r => !r.success).length;

  console.log(`\n📊 Reset Summary:`);
  console.log(`  ✅ Successfully reset: ${successful} episodes`);
  console.log(`  ❌ Failed to reset: ${failed} episodes`);

  if (failed > 0) {
    console.log('\n❌ Failed episodes:');
    results.filter(r => !r.success).forEach(result => {
      console.log(`  - "${result.episode.title}" (ID: ${result.episode.id})`);
    });
  }
}

async function main() {
  const args = process.argv.slice(2);
  const dryRun = args.includes('--dry-run');
  const olderThanArg = args.find(arg => arg.startsWith('--older-than-hours='));
  const olderThanHours = olderThanArg ? parseInt(olderThanArg.split('=')[1]) : 24;

  console.log('🔍 Checking for stuck episodes...');
  console.log(`   Criteria: Processing status + no running process + older than ${olderThanHours} hours`);
  console.log(`   Mode: ${dryRun ? 'DRY RUN' : 'LIVE'}`);
  console.log('');

  try {
    const stuckEpisodes = await findStuckEpisodes(olderThanHours);
    await resetStuckEpisodes(stuckEpisodes, dryRun);
  } catch (error) {
    console.error('❌ Script failed:', error);
    process.exit(1);
  } finally {
    await prisma.$disconnect();
  }
}

// Run if called directly
if (require.main === module) {
  main().catch((error) => {
    console.error('❌ Unhandled error:', error);
    process.exit(1);
  });
}