#!/usr/bin/env node

const { PrismaClient } = require('@prisma/client');

async function killRunningJobs() {
  const prisma = new PrismaClient();

  try {
    // Find running pipeline jobs
    const runningJobs = await prisma.pipelineRun.findMany({
      where: {
        status: 'running'
      },
      include: {
        episode: {
          select: { title: true }
        }
      }
    });

    console.log('=== CHECKING FOR RUNNING PIPELINE JOBS ===');

    if (runningJobs.length === 0) {
      console.log('✅ No running pipeline jobs found');
    } else {
      console.log(`🔍 Found ${runningJobs.length} running jobs:`);

      for (const job of runningJobs) {
        console.log(`   📋 ID: ${job.id}`);
        console.log(`   📺 Episode: ${job.episode?.title || 'Unknown'} (${job.episodeId})`);
        console.log(`   🎯 Stage: ${job.stage}`);
        console.log(`   ⏰ Started: ${job.startedAt}`);
        console.log(`   📍 Current Stage: ${job.currentStage || 'N/A'}`);
        console.log('   ---');
      }

      console.log('🔪 Killing all running jobs...');

      const result = await prisma.pipelineRun.updateMany({
        where: { status: 'running' },
        data: {
          status: 'failed',
          errorMessage: 'Manually killed by user',
          completedAt: new Date()
        }
      });

      console.log(`✅ Successfully killed ${result.count} pipeline jobs`);
    }

  } catch (error) {
    console.error('❌ Error:', error.message);
  } finally {
    await prisma.$disconnect();
  }
}

killRunningJobs();