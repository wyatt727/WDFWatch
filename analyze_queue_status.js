const { PrismaClient } = require('./web/node_modules/@prisma/client');
const prisma = new PrismaClient();

async function analyzeQueueStatus() {
  try {
    // Get counts for each status
    const statuses = await prisma.tweetQueue.groupBy({
      by: ['status'],
      where: {
        source: 'approved_draft'
      },
      _count: {
        id: true
      }
    });

    console.log('\n📊 Queue Status Overview:');
    console.log('=' + '='.repeat(59));
    statuses.forEach(s => {
      console.log(`${s.status}: ${s._count.id} tweets`);
    });

    // Check for duplicate response texts
    const allQueue = await prisma.tweetQueue.findMany({
      where: {
        source: 'approved_draft',
        status: { in: ['pending', 'failed'] }
      }
    });

    const responseTexts = {};
    const duplicates = [];

    allQueue.forEach(item => {
      const metadata = typeof item.metadata === 'string'
        ? JSON.parse(item.metadata)
        : item.metadata;
      const text = metadata.responseText;

      if (responseTexts[text]) {
        duplicates.push({
          text: text.substring(0, 50),
          tweets: [responseTexts[text], item.twitterId]
        });
      } else {
        responseTexts[text] = item.twitterId;
      }
    });

    if (duplicates.length > 0) {
      console.log('\n⚠️  Duplicate Response Texts Found:');
      console.log('=' + '='.repeat(59));
      duplicates.forEach(dup => {
        console.log(`"${dup.text}...":`);
        console.log(`  Tweets: ${dup.tweets.join(', ')}`);
      });
    }

    // Check a pending tweet
    const pendingTweet = await prisma.tweetQueue.findFirst({
      where: {
        status: 'pending',
        source: 'approved_draft'
      }
    });

    if (pendingTweet) {
      const metadata = typeof pendingTweet.metadata === 'string'
        ? JSON.parse(pendingTweet.metadata)
        : pendingTweet.metadata;

      console.log('\n📝 Sample Pending Tweet:');
      console.log('=' + '='.repeat(59));
      console.log('Twitter ID:', pendingTweet.twitterId);
      console.log('Response:', metadata.responseText?.substring(0, 100) + '...');
      console.log('Added:', pendingTweet.addedAt);
      console.log('Retry Count:', pendingTweet.retryCount);
    }

    // Check if we have tweets that were already posted
    const postedCheck = await prisma.$queryRaw`
      SELECT q.twitterId, q.status as queue_status, d.status as draft_status
      FROM tweet_queue q
      LEFT JOIN tweets t ON t.twitter_id = q.twitter_id
      LEFT JOIN draft_replies d ON d.tweet_id = t.id
      WHERE q.source = 'approved_draft'
      AND q.status IN ('pending', 'failed')
      AND d.status = 'posted'
      LIMIT 10
    `;

    if (postedCheck && postedCheck.length > 0) {
      console.log('\n❌ Tweets Already Posted But Still In Queue:');
      console.log('=' + '='.repeat(59));
      postedCheck.forEach(t => {
        console.log(`Tweet ${t.twitterid}: Queue=${t.queue_status}, Draft=${t.draft_status}`);
      });
    }

  } catch (error) {
    console.error('Error:', error);
  } finally {
    await prisma.$disconnect();
  }
}

analyzeQueueStatus();