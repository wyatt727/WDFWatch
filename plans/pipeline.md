### Pipeline Steps

0. Start @main.py to orchestrate pipeline logic with a beautiful and verbose output
1. @gemini_summarize.py feeds transcripts/latest.txt to gemini-cli to generate an extremely comprehensive summary of transcript. The target audience of the summary is an expert social media manager whose job it is to promote the specific episode of the War, Divorce, or Federalism (WDF) podcast hosted by Rick Becker. The summary should also include keywords that will be saved to @addtranscripts/keywords.json The final summary will be saved to @transcripts/summary.md
2. @twitter.py uses @addtranscripts/keywords.json to find relevant (mock) tweets and adds them to @transcripts/tweets.json
2. @3nfewshotter.py uses the gemma-3n model to read @transcripts/podcast_overview.txt and @transcripts/summary.md, and then generates 20 "few shot" examples of relevant/unrelevant tweets. This NEEDS to be in a specific format and saved to @transcripts/fewshots.json.
3. Use @3n.py dynamically repopulates it's FEWSHOT_EXAMPLES with the examples in @transcripts/fewshots.json. Then it uses those + @transcripts/summary.md to determine if a tweet is relevant.
4. Send relevant tweets to deepseek.py which uses @transcripts/summary.md and @transcripts/podcast_overview.txt to generate a response thats under 275 characters, is directly relevant, and draws an audience to the episode URL which is in VIDEO_URL.txt. It then adds those tweets to queue.py
5. @queue.py shows the original tweet, the generated response, and allows the user to manually edit the response, approve, or reject the post. 
8. Approved tweets are published as a comment on the original tweet using @twitter.py