-- Add keyword search cache table to track searches and prevent redundant API calls
-- This table stores which keywords have been searched and what tweets were found
-- Allows reusing search results for up to 4 days

CREATE TABLE IF NOT EXISTS keyword_search_cache (
    id SERIAL PRIMARY KEY,
    keyword VARCHAR(255) NOT NULL,
    searched_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    episode_id INTEGER REFERENCES podcast_episodes(id) ON DELETE CASCADE,
    tweet_count INTEGER NOT NULL DEFAULT 0,
    tweet_ids TEXT[], -- Array of twitter_ids returned from this search
    search_params JSONB, -- Store search parameters (days_back, max_results, etc.)
    api_calls_used INTEGER DEFAULT 1, -- Track how many API calls this search used
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL DEFAULT (CURRENT_TIMESTAMP + INTERVAL '4 days'),
    
    -- Unique constraint to prevent duplicate active searches
    UNIQUE(keyword, episode_id, expires_at)
);

-- Create indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_keyword_search_cache_keyword ON keyword_search_cache(keyword);
CREATE INDEX IF NOT EXISTS idx_keyword_search_cache_searched_at ON keyword_search_cache(searched_at DESC);
CREATE INDEX IF NOT EXISTS idx_keyword_search_cache_expires_at ON keyword_search_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_keyword_search_cache_episode ON keyword_search_cache(episode_id);
CREATE INDEX IF NOT EXISTS idx_keyword_search_cache_lookup ON keyword_search_cache(keyword, expires_at DESC);

-- Add search metadata to tweets table to track which searches found them
ALTER TABLE tweets ADD COLUMN IF NOT EXISTS search_keywords TEXT[];
ALTER TABLE tweets ADD COLUMN IF NOT EXISTS last_search_date TIMESTAMP;

-- Create a function to clean up expired cache entries
CREATE OR REPLACE FUNCTION cleanup_expired_search_cache()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM keyword_search_cache 
    WHERE expires_at < CURRENT_TIMESTAMP;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Create view for active cache entries
CREATE OR REPLACE VIEW active_keyword_searches AS
SELECT 
    keyword,
    searched_at,
    episode_id,
    tweet_count,
    array_length(tweet_ids, 1) as actual_tweet_count,
    api_calls_used,
    expires_at,
    EXTRACT(EPOCH FROM (expires_at - CURRENT_TIMESTAMP))/3600 as hours_until_expiry
FROM keyword_search_cache
WHERE expires_at > CURRENT_TIMESTAMP
ORDER BY searched_at DESC;

-- Create aggregated view showing keyword search frequency
CREATE OR REPLACE VIEW keyword_search_stats AS
SELECT 
    keyword,
    COUNT(*) as search_count,
    MAX(searched_at) as last_searched,
    SUM(tweet_count) as total_tweets_found,
    SUM(api_calls_used) as total_api_calls_used,
    ARRAY_AGG(DISTINCT episode_id) FILTER (WHERE episode_id IS NOT NULL) as episodes
FROM keyword_search_cache
WHERE searched_at > CURRENT_TIMESTAMP - INTERVAL '30 days'
GROUP BY keyword
ORDER BY search_count DESC, last_searched DESC;