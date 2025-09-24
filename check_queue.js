const { PrismaClient } = require('./web/node_modules/@prisma/client');
const prisma = new PrismaClient();

async function checkQueue() {
  try {
    // Check tweet queue
    const queueStats = await prisma.tweetQueue.groupBy({
      by: ['status', 'source'],
      _count: {
        id: true
      },
      where: {
        source: 'approved_draft'
      }
    });

    console.log('\n📊 Tweet Queue Status (approved_draft source):');
    console.log('----------------------------------------');
    queueStats.forEach(stat => {
      console.log(`${stat.status}: ${stat._count.id} tweets`);
    });

    // Check recent approved drafts
    const recentDrafts = await prisma.draftReply.findMany({
      where: {
        status: { in: ['approved', 'posted'] },
      },
      orderBy: { updatedAt: 'desc' },
      take: 5,
      include: {
        tweet: {
          select: {
            twitterId: true,
            authorHandle: true,
            textPreview: true
          }
        }
      }
    });

    console.log('\n📝 Recent Approved/Posted Drafts:');
    console.log('----------------------------------------');
    recentDrafts.forEach(draft => {
      console.log(`\nDraft ID: ${draft.id}`);
      console.log(`Status: ${draft.status}`);
      console.log(`Tweet: @${draft.tweet.authorHandle} - ${draft.tweet.textPreview?.substring(0, 50)}...`);
      console.log(`Response: ${draft.text.substring(0, 100)}...`);
      console.log(`Posted At: ${draft.postedAt || 'NOT POSTED'}`);
      console.log(`Approved At: ${draft.approvedAt || 'N/A'}`);
    });

    // Check for pending items in queue
    const pendingQueue = await prisma.tweetQueue.findMany({
      where: {
        status: 'pending',
        source: 'approved_draft'
      },
      take: 5,
      orderBy: { addedAt: 'desc' }
    });

    if (pendingQueue.length > 0) {
      console.log('\n⏳ Pending Queue Items (need processing):');
      console.log('----------------------------------------');
      pendingQueue.forEach(item => {
        console.log(`\nQueue ID: ${item.id}`);
        console.log(`Twitter ID: ${item.twitterId}`);
        console.log(`Added: ${item.addedAt}`);
        console.log(`Metadata:`, JSON.stringify(item.metadata, null, 2));
      });
    }

  } catch (error) {
    console.error('Error checking queue:', error);
  } finally {
    await prisma.$disconnect();
  }
}

checkQueue();