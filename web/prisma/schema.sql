-- WDFWatch PostgreSQL Schema
-- Tables for episodes, tweets, drafts, and audit logging
-- Includes pgvector extension for semantic search

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";

-- Podcast episodes table
CREATE TABLE podcast_episodes (
  id SERIAL PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  transcript_text TEXT,
  summary_text TEXT,
  keywords JSONB,
  status VARCHAR(50) DEFAULT 'no_transcript',
  summary_embedding vector(1536), -- For semantic search
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tweets table
CREATE TABLE tweets (
  id SERIAL PRIMARY KEY,
  twitter_id VARCHAR(50) UNIQUE NOT NULL,
  author_handle VARCHAR(100) NOT NULL,
  author_name VARCHAR(255),
  full_text TEXT NOT NULL,
  text_preview VARCHAR(280), -- First 280 chars for list view
  relevance_score FLOAT,
  classification_rationale TEXT,
  status VARCHAR(20) DEFAULT 'unclassified', -- unclassified, relevant, skipped, drafted, posted
  thread_data JSONB, -- Store full thread context
  metrics JSONB, -- likes, retweets, etc
  flags JSONB, -- toxicity, duplicate flags
  embedding vector(768), -- For similarity search
  scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  episode_id INTEGER REFERENCES podcast_episodes(id),
  
  INDEX idx_tweets_status (status),
  INDEX idx_tweets_twitter_id (twitter_id),
  INDEX idx_tweets_created_at (created_at DESC)
);

-- Draft replies table
CREATE TABLE draft_replies (
  id SERIAL PRIMARY KEY,
  tweet_id INTEGER REFERENCES tweets(id) ON DELETE CASCADE,
  model_name VARCHAR(50) NOT NULL,
  prompt_version VARCHAR(50),
  text TEXT NOT NULL,
  status VARCHAR(20) DEFAULT 'pending', -- pending, approved, rejected
  style_score FLOAT,
  toxicity_score FLOAT,
  character_count INTEGER,
  version INTEGER DEFAULT 1,
  superseded BOOLEAN DEFAULT FALSE,
  approved_by VARCHAR(100),
  approved_at TIMESTAMP,
  rejected_by VARCHAR(100),
  rejected_at TIMESTAMP,
  rejection_reason TEXT,
  scheduled_for TIMESTAMP,
  posted_at TIMESTAMP,
  twitter_reply_id VARCHAR(50),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  INDEX idx_drafts_tweet_id (tweet_id),
  INDEX idx_drafts_status (status),
  INDEX idx_drafts_created_at (created_at DESC)
);

-- Draft edit history
CREATE TABLE draft_edits (
  id SERIAL PRIMARY KEY,
  draft_id INTEGER REFERENCES draft_replies(id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  text TEXT NOT NULL,
  edited_by VARCHAR(100),
  edited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  diff_from_previous JSONB -- Store character-level diff
);

-- Keywords table for search terms
CREATE TABLE keywords (
  id SERIAL PRIMARY KEY,
  episode_id INTEGER REFERENCES podcast_episodes(id) ON DELETE CASCADE,
  keyword VARCHAR(100) NOT NULL,
  weight FLOAT DEFAULT 1.0,
  frequency INTEGER DEFAULT 0,
  last_used TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  UNIQUE(episode_id, keyword),
  INDEX idx_keywords_episode (episode_id),
  INDEX idx_keywords_frequency (frequency DESC)
);

-- Quota tracking table
CREATE TABLE quota_usage (
  id SERIAL PRIMARY KEY,
  period_start DATE NOT NULL,
  period_end DATE NOT NULL,
  total_allowed INTEGER DEFAULT 10000,
  used INTEGER DEFAULT 0,
  source_breakdown JSONB, -- {stream: 0, search: 0, threadLookups: 0}
  daily_usage JSONB, -- {date: count} for trend tracking
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  UNIQUE(period_start, period_end)
);

-- Audit log for compliance
CREATE TABLE audit_log (
  id SERIAL PRIMARY KEY,
  user_id VARCHAR(100),
  action VARCHAR(50) NOT NULL, -- approve_draft, reject_draft, edit_draft, etc
  resource_type VARCHAR(50), -- tweet, draft, episode
  resource_id INTEGER,
  old_value JSONB,
  new_value JSONB,
  metadata JSONB, -- Additional context
  ip_address VARCHAR(45),
  user_agent TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  INDEX idx_audit_user (user_id),
  INDEX idx_audit_action (action),
  INDEX idx_audit_created (created_at DESC)
);

-- Pipeline runs for tracking
CREATE TABLE pipeline_runs (
  id SERIAL PRIMARY KEY,
  run_id VARCHAR(100) UNIQUE NOT NULL,
  episode_id INTEGER REFERENCES podcast_episodes(id),
  stage VARCHAR(50) NOT NULL,
  status VARCHAR(20) DEFAULT 'running', -- running, completed, failed
  started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP,
  error_message TEXT,
  metrics JSONB, -- tweets_found, classified, drafts_generated, etc
  artifacts_path VARCHAR(255),
  
  INDEX idx_runs_status (status),
  INDEX idx_runs_started (started_at DESC)
);

-- Settings table for configuration
CREATE TABLE settings (
  key VARCHAR(100) PRIMARY KEY,
  value JSONB NOT NULL,
  description TEXT,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_by VARCHAR(100)
);

-- Create update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to all tables with updated_at
CREATE TRIGGER update_podcast_episodes_updated_at BEFORE UPDATE ON podcast_episodes
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tweets_updated_at BEFORE UPDATE ON tweets
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_draft_replies_updated_at BEFORE UPDATE ON draft_replies
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_quota_usage_updated_at BEFORE UPDATE ON quota_usage
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create view for tweet inbox with draft counts
CREATE VIEW tweet_inbox AS
SELECT 
  t.*,
  COUNT(DISTINCT d.id) FILTER (WHERE d.status = 'pending' AND NOT d.superseded) as pending_drafts,
  COUNT(DISTINCT d.id) FILTER (WHERE d.status = 'approved' AND NOT d.superseded) as approved_drafts,
  MAX(d.created_at) as latest_draft_at
FROM tweets t
LEFT JOIN draft_replies d ON t.id = d.tweet_id
GROUP BY t.id;

-- Initial settings
INSERT INTO settings (key, value, description) VALUES
  ('quota_warning_threshold', '{"percentage": 80}', 'Show warning when quota usage exceeds this percentage'),
  ('quota_danger_threshold', '{"percentage": 95}', 'Show danger alert when quota usage exceeds this percentage'),
  ('auto_refresh_interval', '{"minutes": 10}', 'Auto-refresh interval for quota display'),
  ('default_draft_model', '{"model": "deepseek-r1:latest"}', 'Default model for generating draft responses');