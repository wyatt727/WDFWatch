-- Create Tweet Queue table for persistent tweet management
CREATE TABLE IF NOT EXISTS tweet_queue (
  id SERIAL PRIMARY KEY,
  tweet_id VARCHAR(100) UNIQUE NOT NULL,
  twitter_id VARCHAR(50) NOT NULL,
  source VARCHAR(50) NOT NULL, -- 'manual', 'scrape', 'direct_url'
  priority INTEGER DEFAULT 0, -- Higher = more important
  status VARCHAR(20) DEFAULT 'pending', -- pending, processing, completed, failed
  episode_id INTEGER,
  added_by VARCHAR(100),
  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  processed_at TIMESTAMP,
  metadata JSONB,
  retry_count INTEGER DEFAULT 0
);

-- Index for efficient queue processing
CREATE INDEX idx_tweet_queue_status_priority ON tweet_queue(status, priority DESC, added_at);

-- Prevent duplicate tweets in queue
CREATE UNIQUE INDEX idx_tweet_queue_twitter_id ON tweet_queue(twitter_id) WHERE status != 'completed';

-- Add queue_id to tweets table (only if tweets table exists)
DO $$ 
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'tweets') THEN
    ALTER TABLE tweets ADD COLUMN IF NOT EXISTS queue_id INTEGER REFERENCES tweet_queue(id);
  END IF;
END $$;

-- Create Tweet Response Request table for single tweet responses
CREATE TABLE IF NOT EXISTS tweet_response_requests (
  id SERIAL PRIMARY KEY,
  tweet_url VARCHAR(500) NOT NULL,
  tweet_id VARCHAR(50),
  tweet_text TEXT,
  requested_by VARCHAR(100),
  requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  response_generated TEXT,
  status VARCHAR(20) DEFAULT 'pending',
  episode_context_id INTEGER,
  approved BOOLEAN DEFAULT FALSE,
  approved_at TIMESTAMP,
  published BOOLEAN DEFAULT FALSE,
  published_at TIMESTAMP,
  error_message TEXT
);

-- Track API usage per scraping session
CREATE TABLE IF NOT EXISTS scraping_sessions (
  id SERIAL PRIMARY KEY,
  session_id VARCHAR(100) UNIQUE NOT NULL,
  started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP,
  api_calls_used INTEGER DEFAULT 0,
  tweets_found INTEGER DEFAULT 0,
  tweets_cached INTEGER DEFAULT 0,
  tweets_new INTEGER DEFAULT 0,
  keywords_used JSONB,
  parameters JSONB,
  error_log JSONB,
  status VARCHAR(20) DEFAULT 'running' -- running, completed, failed, cancelled
);

-- Add index for scraping sessions
CREATE INDEX IF NOT EXISTS idx_scraping_sessions_started_at ON scraping_sessions(started_at);

-- Create Monitoring Alerts table
CREATE TABLE IF NOT EXISTS monitoring_alerts (
  id SERIAL PRIMARY KEY,
  alert_type VARCHAR(50) NOT NULL,
  severity VARCHAR(20) NOT NULL,
  message TEXT NOT NULL,
  triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  resolved_at TIMESTAMP,
  metadata JSONB
);

-- Add indexes for monitoring alerts
CREATE INDEX IF NOT EXISTS idx_monitoring_alerts_type ON monitoring_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_monitoring_alerts_triggered ON monitoring_alerts(triggered_at);
CREATE INDEX IF NOT EXISTS idx_monitoring_alerts_resolved ON monitoring_alerts(resolved_at);