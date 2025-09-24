const { PrismaClient } = require('./web/node_modules/@prisma/client');
const prisma = new PrismaClient();

async function analyzeFailures() {
  try {
    // Get failed tweets with their error messages
    const failedTweets = await prisma.tweetQueue.findMany({
      where: {
        status: 'failed',
        source: 'approved_draft'
      },
      orderBy: { processedAt: 'desc' },
      take: 10
    });

    console.log('\n❌ Failed Tweet Analysis:');
    console.log('=' + '='.repeat(59));

    const errorPatterns = {};

    failedTweets.forEach(tweet => {
      const metadata = typeof tweet.metadata === 'string'
        ? JSON.parse(tweet.metadata)
        : tweet.metadata;

      const error = metadata.lastError || metadata.error || 'Unknown error';

      // Extract key error patterns
      let errorType = 'Unknown';
      if (error.includes('401') || error.includes('Unauthorized')) {
        errorType = '401 Unauthorized';
      } else if (error.includes('403') || error.includes('Forbidden')) {
        errorType = '403 Forbidden';
      } else if (error.includes('429') || error.includes('Too Many Requests')) {
        errorType = '429 Rate Limited';
      } else if (error.includes('duplicate') || error.includes('already replied')) {
        errorType = 'Duplicate Reply';
      } else if (error.includes('token') || error.includes('Token')) {
        errorType = 'Token Issue';
      }

      errorPatterns[errorType] = (errorPatterns[errorType] || 0) + 1;

      console.log(`\nTweet: ${tweet.twitterId}`);
      console.log(`Failed at: ${tweet.processedAt || 'N/A'}`);
      console.log(`Retry count: ${tweet.retryCount}`);
      console.log(`Error: ${error.substring(0, 200)}...`);
    });

    console.log('\n📊 Error Pattern Summary:');
    console.log('=' + '='.repeat(59));
    Object.entries(errorPatterns).forEach(([type, count]) => {
      console.log(`${type}: ${count} occurrences`);
    });

    // Check token expiration
    console.log('\n🔑 Token Status Check:');
    console.log('=' + '='.repeat(59));

    // Get the most recent successful post
    const lastSuccess = await prisma.tweetQueue.findFirst({
      where: {
        status: 'completed',
        source: 'approved_draft'
      },
      orderBy: { processedAt: 'desc' }
    });

    if (lastSuccess) {
      console.log(`Last successful post: ${lastSuccess.processedAt}`);
      const hoursSinceSuccess = (Date.now() - lastSuccess.processedAt.getTime()) / (1000 * 60 * 60);
      console.log(`Hours since last success: ${hoursSinceSuccess.toFixed(1)}`);

      if (hoursSinceSuccess > 48) {
        console.log('⚠️  No successful posts in 2+ days - likely token expired!');
      }
    }

    // Check pending tweets
    const pendingCount = await prisma.tweetQueue.count({
      where: {
        status: 'pending',
        source: 'approved_draft'
      }
    });

    console.log(`\n📋 Queue Status:`);
    console.log(`Pending: ${pendingCount}`);
    console.log(`Failed: ${failedTweets.length} (showing 10)`);

  } catch (error) {
    console.error('Error analyzing failures:', error);
  } finally {
    await prisma.$disconnect();
  }
}

analyzeFailures();