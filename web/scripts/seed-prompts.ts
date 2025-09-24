/**
 * Minimal seed script for prompt templates and context files only
 * Used to fix missing data in the prompts settings page
 */

import { PrismaClient } from '@prisma/client'

const prisma = new PrismaClient()

async function main() {
  console.log('🌱 Seeding prompt templates and context files...')

  // Create prompt templates
  console.log('📝 Creating prompt templates...')
  
  // Summarization prompt
  await prisma.promptTemplate.upsert({
    where: { key: 'summarization' },
    update: {},
    create: {
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
  await prisma.promptTemplate.upsert({
    where: { key: 'fewshot_generation' },
    update: {},
    create: {
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
  await prisma.promptTemplate.upsert({
    where: { key: 'tweet_classification' },
    update: {},
    create: {
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
  await prisma.promptTemplate.upsert({
    where: { key: 'response_generation' },
    update: {},
    create: {
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
  
  await prisma.contextFile.upsert({
    where: { key: 'podcast_overview' },
    update: {},
    create: {
      key: 'podcast_overview',
      name: 'Podcast Overview',
      description: 'General description of the WDF podcast',
      content: `The War, Divorce, or Federalism podcast, hosted by Rick Becker, explores critical issues of liberty, constitutional governance, and state sovereignty. Each episode delves into topics ranging from federal overreach to individual rights, offering insights from a libertarian/constitutionalist perspective. The podcast aims to educate listeners about the founding principles of American federalism and their relevance to contemporary political debates.`,
      isActive: true,
      updatedBy: 'system'
    }
  })

  await prisma.contextFile.upsert({
    where: { key: 'video_url' },
    update: {},
    create: {
      key: 'video_url',
      name: 'Latest Episode URL',
      description: 'YouTube URL for the latest podcast episode',
      content: 'https://youtu.be/example-latest-episode',
      isActive: true,
      updatedBy: 'system'
    }
  })

  console.log('✅ Prompt templates and context files created successfully!')
  
  // Verify creation
  const promptCount = await prisma.promptTemplate.count({ where: { isActive: true } })
  const contextCount = await prisma.contextFile.count({ where: { isActive: true } })
  
  console.log(`📊 Summary:`)
  console.log(`- ${promptCount} prompt templates`)
  console.log(`- ${contextCount} context files`)
}

main()
  .then(async () => {
    await prisma.$disconnect()
  })
  .catch(async (e) => {
    console.error('❌ Seeding failed:', e)
    await prisma.$disconnect()
    process.exit(1)
  })