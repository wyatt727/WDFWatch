#!/bin/bash
# Simple script to process pending tweets from queue

echo "🚀 Processing pending tweets from queue"
echo "=" | tr "=" "="

# Get first 3 pending tweets from database
cd web
npx prisma db execute --stdin <<EOF | tail -n +4 | head -n 3 > /tmp/pending_tweets.txt
SELECT twitterId, metadata->>'responseText' as response
FROM tweet_queue
WHERE status = 'pending'
AND source = 'approved_draft'
ORDER BY addedAt ASC
LIMIT 3;
EOF

cd ..

# Process each tweet
COUNT=0
while IFS='|' read -r tweet_id response; do
    # Skip header line and empty lines
    [[ -z "$tweet_id" ]] && continue
    [[ "$tweet_id" == "twitterId" ]] && continue

    # Clean up the values
    tweet_id=$(echo "$tweet_id" | xargs)
    response=$(echo "$response" | xargs)

    COUNT=$((COUNT + 1))
    echo ""
    echo "[$COUNT] Processing tweet: $tweet_id"
    echo "Response: ${response:0:80}..."

    # Call the safe Twitter reply script
    ./venv/bin/python scripts/safe_twitter_reply.py \
        --tweet-id "$tweet_id" \
        --message "$response" 2>&1 | grep -E "✅|❌|Successfully|Failed|Error"

    # Wait between tweets to respect rate limits
    if [ $COUNT -lt 3 ]; then
        echo "⏳ Waiting 10 seconds..."
        sleep 10
    fi
done < /tmp/pending_tweets.txt

echo ""
echo "=" | tr "=" "="
echo "✅ Processing complete! Processed $COUNT tweets"