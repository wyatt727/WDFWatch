/**
 * Seed script for WDFWatch development database
 * Creates sample episodes, tweets, drafts, and audit data
 * Interacts with: Prisma client, PostgreSQL database
 */

import { PrismaClient } from '@prisma/client'
import { hash } from 'crypto'

const prisma = new PrismaClient()

async function main() {
  console.log('🌱 Starting database seed...')

  // Clean existing data
  console.log('🧹 Cleaning existing data...')
  await prisma.auditLog.deleteMany()
  await prisma.draftReply.deleteMany()
  await prisma.tweet.deleteMany()
  await prisma.keyword.deleteMany()
  await prisma.podcastEpisode.deleteMany()
  await prisma.pipelineRun.deleteMany()
  await prisma.quotaUsage.deleteMany()

  // Create a sample episode
  console.log('📻 Creating podcast episode...')
  const episode = await prisma.podcastEpisode.create({
    data: {
      title: 'The Growing Federal Debt Crisis',
      summaryText: `
## Key Topics

1. **Federal Debt Explosion**
   - National debt now exceeds $34 trillion
   - Interest payments consuming larger portion of budget
   - States increasingly dependent on federal funding

2. **State Sovereignty Under Pressure**
   - Federal mandates tied to funding
   - Loss of state autonomy in policy decisions
   - Constitutional concerns about 10th Amendment

3. **Solutions Through Federalism**
   - States asserting their rights through nullification
   - Interstate compacts as alternative to federal programs
   - Return to constitutional limits on federal power
      `.trim(),
      status: 'keywords_ready',
      keywords: {
        terms: [
          { text: 'federal debt', weight: 0.9 },
          { text: 'state sovereignty', weight: 0.85 },
          { text: 'constitutional federalism', weight: 0.8 },
          { text: 'tenth amendment', weight: 0.75 },
        ]
      }
    }
  })

  // Create keywords
  console.log('🔑 Creating keywords...')
  const keywordData = [
    { text: 'federal debt', weight: 0.9 },
    { text: 'state sovereignty', weight: 0.85 },
    { text: 'constitutional federalism', weight: 0.8 },
    { text: 'tenth amendment', weight: 0.75 },
    { text: 'states rights', weight: 0.7 },
    { text: 'federal overreach', weight: 0.9 },
  ]

  for (const kw of keywordData) {
    await prisma.keyword.create({
      data: {
        episodeId: episode.id,
        keyword: kw.text,
        weight: kw.weight,
      }
    })
  }

  // Create sample tweets
  console.log('🐦 Creating sample tweets...')
  const tweetData = [
    {
      twitterId: '1747283945621234567',
      authorHandle: 'liberty_defender',
      authorName: 'Liberty Defender',
      fullText: 'The federal debt is completely out of control. We need states to stand up and refuse to participate in unconstitutional programs.',
      status: 'relevant' as const,
      relevanceScore: 0.92,
      metrics: { likes: 45, retweets: 12 },
    },
    {
      twitterId: '1747283945621234568',
      authorHandle: 'coffee_lover',
      authorName: 'Coffee Enthusiast',
      fullText: 'Just made the best coffee ever! Starting my Sunday right ☕️',
      status: 'skipped' as const,
      relevanceScore: 0.1,
      metrics: { likes: 5, retweets: 0 },
    },
    {
      twitterId: '1747283945621234569',
      authorHandle: 'constitutional_scholar',
      authorName: 'Constitutional Scholar',
      fullText: 'Interesting article about how states are pushing back against federal mandates. The 10th Amendment still matters!',
      status: 'relevant' as const,
      relevanceScore: 0.88,
      metrics: { likes: 78, retweets: 23 },
    },
    {
      twitterId: '1747283945621234571',
      authorHandle: 'political_analyst',
      authorName: 'Political Analyst',
      fullText: "State sovereignty isn't just a conservative issue. It's about protecting democracy from centralized power.",
      status: 'drafted' as const,
      relevanceScore: 0.85,
      metrics: { likes: 156, retweets: 42 },
    },
  ]

  const tweets = []
  for (const tweetInfo of tweetData) {
    const tweet = await prisma.tweet.create({
      data: {
        ...tweetInfo,
        episodeId: episode.id,
        textPreview: tweetInfo.fullText.substring(0, 280),
      }
    })
    tweets.push(tweet)
  }

  // Create draft responses for relevant tweets
  console.log('✍️  Creating draft responses...')
  const drafts = [
    {
      tweetId: tweets[0].id,
      text: "Absolutely! Rick Becker dives deep into this exact issue on WDF. States have constitutional power to resist - check out our latest episode on federal debt & state sovereignty: https://youtu.be/example",
      modelName: 'deepseek-r1:latest',
      status: 'pending' as const,
      characterCount: 189,
    },
    {
      tweetId: tweets[2].id,
      text: "The 10th Amendment is making a comeback! WDF podcast explores how states are reclaiming their constitutional authority. Great discussion with Rick Becker here: https://youtu.be/example",
      modelName: 'deepseek-r1:latest',
      status: 'pending' as const,
      characterCount: 178,
    },
    {
      tweetId: tweets[3].id,
      text: "Well said! It's about balance of power, not partisan politics. Rick Becker examines this on War, Divorce, or Federalism - fascinating take on protecting democracy through federalism: https://youtu.be/example",
      modelName: 'deepseek-r1:latest',
      status: 'approved' as const,
      characterCount: 201,
      approvedAt: new Date(Date.now() - 3600000), // 1 hour ago
    },
  ]

  for (const draft of drafts) {
    await prisma.draftReply.create({ data: draft })
  }

  // Create pipeline run
  console.log('🔧 Creating pipeline run...')
  await prisma.pipelineRun.create({
    data: {
      runId: `dev-seed-${Date.now()}`,
      episodeId: episode.id,
      stage: 'moderation',
      status: 'in_progress',
      startedAt: new Date(Date.now() - 7200000), // 2 hours ago
      metrics: {
        tweets_scraped: 4,
        tweets_classified: 4,
        tweets_relevant: 3,
        drafts_generated: 3,
        drafts_approved: 1,
      }
    }
  })

  // Skip creating quota usage - will be created when Twitter API is actually used
  console.log('📊 Skipping quota usage creation (no Twitter API usage yet)...')

  // Create audit logs
  console.log('📝 Creating audit logs...')
  const auditLogs = [
    {
      action: 'episode_created',
      resourceType: 'episode',
      resourceId: episode.id,
      metadata: { title: episode.title },
    },
    {
      action: 'tweets_scraped',
      resourceType: 'pipeline',
      resourceId: episode.id,
      metadata: { count: 4, keywords: ['federal debt', 'state sovereignty'] },
    },
    {
      action: 'draft_approved',
      resourceType: 'draft',
      resourceId: 3,
      metadata: { tweetId: tweets[3].twitterId, modelName: 'deepseek-r1:latest' },
    },
  ]

  for (const log of auditLogs) {
    await prisma.auditLog.create({ data: log })
  }

  // Create settings
  console.log('⚙️  Creating settings...')
  await prisma.setting.createMany({
    data: [
      { key: 'auto_approve_threshold', value: '0.95', description: 'Minimum confidence score for auto-approval' },
      { key: 'max_response_length', value: '280', description: 'Maximum character count for responses' },
      { key: 'daily_tweet_limit', value: '50', description: 'Maximum tweets to process per day' },
    ]
  })

  // Create prompt templates
  console.log('📝 Creating prompt templates...')
  
  // Summarization prompt
  await prisma.promptTemplate.create({
    data: {
      key: 'summarization',
      name: 'Transcript Summarization',
      description: 'Generates comprehensive episode summary and keywords from transcript',
      template: `You are an expert social media manager for the "War, Divorce, or Federalism" podcast hosted by Rick Becker.
{is_first_chunk ? 'Your task is to create an EXTREMELY lengthy and comprehensive summary of this podcast episode, touching on all the topics discussed.
The summary should be detailed enough for someone who hasn't listened to understand all key points.
Include how it relates to the podcast as a whole.
DO NOT start with phrases like "Here is the summary" or "In this episode". Start directly with the summary content.' : 'Continue analyzing this podcast transcript chunk. Add to the summary you've been building.'}
{is_last_chunk ? 'This is the final chunk. Please finalize your summary and then add a section titled "### Keywords signaling tweet relevance" 
with a list of 20 specific keywords or phrases that would indicate a tweet is relevant to this episode, including WDF and Rick Becker.

FORMAT REQUIREMENTS FOR KEYWORDS:
- List each keyword or phrase on its own line with a bullet point (- ) prefix
- Use proper names exactly as they appear
- Include both specific terms and broader concepts
- Make sure each keyword/phrase is truly distinctive to this episode's content

These keywords will be used to find relevant social media posts to engage with.' : ''}

PODCAST OVERVIEW:
{overview}

TRANSCRIPT CHUNK:
{chunk}`,
      variables: JSON.stringify(['is_first_chunk', 'is_last_chunk', 'overview', 'chunk']),
      isActive: true,
      version: 1,
      createdBy: 'system'
    }
  })

  // Few-shot generation prompt
  await prisma.promptTemplate.create({
    data: {
      key: 'fewshot_generation',
      name: 'Few-shot Example Generation',
      description: 'Generates example tweets for classification training',
      template: `<start_of_turn>system
You are a tweet classifier for the 'War, Divorce, or Federalism' podcast.
Your task is to generate {required_examples} example tweets and classify them as either RELEVANT or SKIP.
RELEVANT tweets are those that relate to the podcast topic and would be good to engage with.
SKIP tweets are those that are not relevant to the podcast topic.

FORMAT REQUIREMENTS:
1. Generate EXACTLY {required_examples} example tweets.
2. Each line must contain a tweet text, followed by a TAB (\\t), then either RELEVANT or SKIP.
3. At least 50% of the examples must be RELEVANT, ordered randomly.
4. Do not include any explanations or additional text.
5. Start immediately with the examples.
6. Randomize the order of relevant and skip tweets.

TWEET DIVERSITY REQUIREMENTS:
1. Some RELEVANT tweets should NOT include any hashtags.
2. Some SKIP tweets SHOULD include hashtags that seem related to the podcast topics (like #liberty, #federalism, etc.) but the tweet content itself should be about something unrelated.
3. Create a mix of tweet styles, lengths, and tones to represent realistic social media content.

PODCAST OVERVIEW:
{overview}

SUMMARY:
{summary}
<end_of_turn>
<start_of_turn>model`,
      variables: JSON.stringify(['required_examples', 'overview', 'summary']),
      isActive: true,
      version: 1,
      createdBy: 'system'
    }
  })

  // Classification prompt
  await prisma.promptTemplate.create({
    data: {
      key: 'tweet_classification',
      name: 'Tweet Classification',
      description: 'Scores tweet relevancy from 0.00 to 1.00',
      template: `You are an assistant that scores tweet relevancy from 0.00 to 1.00 by using few-shot examples.
You must follow these rules exactly:
1. Analyze the tweet's relevance to the topic based on the few-shot examples.
2. Reply with ONLY a decimal number between 0.00 and 1.00.
3. Use two decimal places (e.g., 0.85, 0.42, 1.00).
4. Higher scores mean more relevant to the topic.
5. Do not include any other text, explanations, or formatting.

SCORING GUIDELINES:
- 0.85-1.00: Highly relevant - directly discusses topic themes
- 0.70-0.84: Relevant - relates to topic, good for engagement
- 0.30-0.69: Somewhat relevant - tangentially related
- 0.00-0.29: Not relevant - unrelated to topic

NEVER deviate from the numeric format. Accuracy is critical.
{topic_summary ? '\\n\\nTOPIC CONTEXT:\\n{topic_summary}' : ''}`,
      variables: JSON.stringify(['topic_summary']),
      isActive: true,
      version: 1,
      createdBy: 'system'
    }
  })

  // Response generation prompt
  await prisma.promptTemplate.create({
    data: {
      key: 'response_generation',
      name: 'Tweet Response Generation',
      description: 'Generates engaging responses to relevant tweets',
      template: `You are a controversial social media manager for the WDF Podcast (War, Divorce or Federalism)
The podcast has a strong libertarian/constitutionalist audience that values liberty, limited government, and individual rights.

CRITICAL RULES:
1. The user message is a tweet you are responding to.
2. ASSUME THE USER HAS NEVER HEARD OF THE WDF PODCAST BEFORE.
3. Your response MUST be LESS THAN {max_length} characters - this is ABSOLUTELY REQUIRED.
4. Every response must reference the WDF Podcast by name.
5. Make the user want to listen to the podcast.
6. Briefly mention what the latest episode discusses.
7. Use language that resonates with liberty-minded, constitutionalist audiences.
8. Be provocative and engaging, not just informational.
9. ALWAYS include the link {video_url}.
10. Only output the tweet text—no extra formatting.
11. No emojis allowed!
12. Double check your response is less than {max_length} characters.
13. Triple check that your response is less than {max_length} characters!

PODCAST OVERVIEW:
{podcast_overview}

EPISODE SUMMARY:
{summary}`,
      variables: JSON.stringify(['max_length', 'video_url', 'podcast_overview', 'summary']),
      isActive: true,
      version: 1,
      createdBy: 'system'
    }
  })

  // Create context files
  console.log('📄 Creating context files...')
  
  await prisma.contextFile.create({
    data: {
      key: 'podcast_overview',
      name: 'Podcast Overview',
      description: 'General description of the WDF podcast',
      content: `The War, Divorce, or Federalism podcast, hosted by Rick Becker, explores critical issues of liberty, constitutional governance, and state sovereignty. Each episode delves into topics ranging from federal overreach to individual rights, offering insights from a libertarian/constitutionalist perspective. The podcast aims to educate listeners about the founding principles of American federalism and their relevance to contemporary political debates.`,
      isActive: true,
      updatedBy: 'system'
    }
  })

  await prisma.contextFile.create({
    data: {
      key: 'video_url',
      name: 'Latest Episode URL',
      description: 'YouTube URL for the latest podcast episode',
      content: 'https://youtu.be/example-latest-episode',
      isActive: true,
      updatedBy: 'system'
    }
  })

  console.log('✅ Seed completed successfully!')
  console.log(`
  Summary:
  - 1 podcast episode
  - ${keywordData.length} keywords
  - ${tweets.length} tweets (3 relevant, 1 skipped)
  - 4 prompt templates
  - 2 context files
  - ${drafts.length} draft responses (1 approved, 2 pending)
  - 1 pipeline run
  - ${auditLogs.length} audit logs
  - 3 settings
  `)
}

main()
  .then(async () => {
    await prisma.$disconnect()
  })
  .catch(async (e) => {
    console.error('❌ Seed failed:', e)
    await prisma.$disconnect()
    process.exit(1)
  })