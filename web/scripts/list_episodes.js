const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function listEpisodes() {
  try {
    const episodes = await prisma.episode.findMany({
      select: {
        id: true,
        title: true,
        episodeNumber: true
      },
      orderBy: { id: 'asc' }
    });

    console.log('Available episodes:');
    episodes.forEach(ep => {
      console.log(`  Episode ${ep.id}: ${ep.title || `Episode #${ep.episodeNumber}`}`);
    });
  } catch (error) {
    console.error('Error:', error);
  } finally {
    await prisma.$disconnect();
  }
}

listEpisodes();