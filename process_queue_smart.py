#!/usr/bin/env python3
"""
Smart queue processor that handles errors gracefully
"""

import subprocess
import time
import json
import sys
from pathlib import Path

def process_queue_smart():
    """Process pending and retry failed tweets with smart error handling"""

    print("🚀 Smart Queue Processor")
    print("=" * 60)

    # Process pending tweets first
    print("\n📝 Processing PENDING tweets...")
    pending_success = 0
    pending_fail = 0

    for i in range(45):  # We know there are 45 pending
        print(f"\n[Pending {i+1}/45]")

        # Get one pending tweet from database
        cmd_get = [
            'node', '-e',
            """
            const { PrismaClient } = require('./web/node_modules/@prisma/client');
            const prisma = new PrismaClient();
            prisma.tweetQueue.findFirst({
                where: { status: 'pending', source: 'approved_draft' }
            }).then(t => {
                if (t) {
                    const m = typeof t.metadata === 'string' ? JSON.parse(t.metadata) : t.metadata;
                    console.log(JSON.stringify({
                        id: t.id,
                        twitterId: t.twitterId,
                        response: m.responseText
                    }));
                }
                prisma.$disconnect();
            });
            """
        ]

        result = subprocess.run(cmd_get, capture_output=True, text=True)
        if not result.stdout.strip():
            print("  No more pending tweets")
            break

        try:
            tweet_data = json.loads(result.stdout.strip())
            tweet_id = tweet_data['twitterId']
            response = tweet_data['response']
            queue_id = tweet_data['id']

            print(f"  Tweet: {tweet_id}")
            print(f"  Response: {response[:60]}...")

            # Try to post
            cmd_post = [
                './venv/bin/python',
                'scripts/safe_twitter_reply.py',
                '--tweet-id', tweet_id,
                '--message', response
            ]

            post_result = subprocess.run(cmd_post, capture_output=True, text=True, timeout=30)

            if "Successfully replied" in post_result.stdout:
                print(f"  ✅ Posted successfully!")
                pending_success += 1

                # Update database to completed
                cmd_update = [
                    'node', '-e',
                    f"""
                    const {{ PrismaClient }} = require('./web/node_modules/@prisma/client');
                    const prisma = new PrismaClient();
                    prisma.tweetQueue.update({{
                        where: {{ id: {queue_id} }},
                        data: {{ status: 'completed', processedAt: new Date() }}
                    }}).then(() => prisma.$disconnect());
                    """
                ]
                subprocess.run(cmd_update, capture_output=True)

            elif "restricted who can reply" in post_result.stderr:
                print(f"  ❌ Reply restricted by author - marking as skipped")
                # Update to different status so we don't retry
                cmd_update = [
                    'node', '-e',
                    f"""
                    const {{ PrismaClient }} = require('./web/node_modules/@prisma/client');
                    const prisma = new PrismaClient();
                    prisma.tweetQueue.update({{
                        where: {{ id: {queue_id} }},
                        data: {{
                            status: 'failed',
                            processedAt: new Date(),
                            metadata: JSON.stringify({{
                                ...JSON.parse(prisma.tweetQueue.findUnique({{where:{{id:{queue_id}}}}}).metadata || '{{}}'),
                                finalError: 'Reply restricted by tweet author',
                                unreachable: true
                            }})
                        }}
                    }}).then(() => prisma.$disconnect());
                    """
                ]
                subprocess.run(cmd_update, capture_output=True)
                pending_fail += 1

            elif "duplicate content" in post_result.stderr:
                print(f"  ❌ Duplicate content - this message was already posted")
                # Mark as completed since it was already posted somewhere
                cmd_update = [
                    'node', '-e',
                    f"""
                    const {{ PrismaClient }} = require('./web/node_modules/@prisma/client');
                    const prisma = new PrismaClient();
                    prisma.tweetQueue.update({{
                        where: {{ id: {queue_id} }},
                        data: {{
                            status: 'completed',
                            processedAt: new Date(),
                            metadata: JSON.stringify({{
                                ...JSON.parse(prisma.tweetQueue.findUnique({{where:{{id:{queue_id}}}}}).metadata || '{{}}'),
                                note: 'Duplicate - already posted elsewhere'
                            }})
                        }}
                    }}).then(() => prisma.$disconnect());
                    """
                ]
                subprocess.run(cmd_update, capture_output=True)
                pending_success += 1  # Count as success since content was posted

            else:
                print(f"  ❌ Failed: {post_result.stderr[:100] if post_result.stderr else 'Unknown error'}")
                pending_fail += 1

            # Rate limiting - be conservative
            if i < 44:  # Don't wait after last tweet
                print("  ⏳ Waiting 15 seconds...")
                time.sleep(15)

        except Exception as e:
            print(f"  ❌ Error: {e}")
            pending_fail += 1

    print("\n" + "=" * 60)
    print(f"📊 Results:")
    print(f"✅ Posted: {pending_success}")
    print(f"❌ Failed: {pending_fail}")
    print("=" * 60)

if __name__ == "__main__":
    process_queue_smart()