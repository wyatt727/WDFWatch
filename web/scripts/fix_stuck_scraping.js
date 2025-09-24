const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function fixStuckScraping() {
  try {
    // Find all running scraping stages
    const stuckRuns = await prisma.pipelineRun.findMany({
      where: {
        status: 'running',
        stage: 'scraping'
      }
    });

    console.log(`Found ${stuckRuns.length} stuck scraping runs`);

    for (const run of stuckRuns) {
      console.log(`Marking run ${run.runId} as failed (episode ${run.episodeId})`);

      // Update to failed status
      await prisma.pipelineRun.update({
        where: { id: run.id },
        data: {
          status: 'failed',
          completedAt: new Date(),
          errorMessage: 'Process terminated - marked as failed'
        }
      });
    }

    console.log('All stuck scraping runs have been marked as failed');
  } catch (error) {
    console.error('Error:', error);
  } finally {
    await prisma.$disconnect();
  }
}

fixStuckScraping();