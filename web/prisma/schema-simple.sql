-- WDFWatch PostgreSQL Schema (Simplified without pgvector)
-- Tables for episodes, tweets, drafts, and audit logging

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Podcast episodes table
CREATE TABLE podcast_episodes (
  id SERIAL PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  transcript_text TEXT,
  summary_text TEXT,
  keywords JSONB,
  status VARCHAR(50) DEFAULT 'no_transcript',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tweets table
CREATE TABLE tweets (
  id SERIAL PRIMARY KEY,
  twitter_id VARCHAR(50) UNIQUE NOT NULL,
  episode_id INTEGER REFERENCES podcast_episodes(id) ON DELETE SET NULL,
  author_handle VARCHAR(50) NOT NULL,
  author_name VARCHAR(255),
  full_text TEXT NOT NULL,
  text_preview VARCHAR(280),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  relevance_score FLOAT,
  classification_rationale TEXT,
  status VARCHAR(20) DEFAULT 'unclassified',
  flags JSONB,
  metrics JSONB
);

-- Draft replies table
CREATE TABLE draft_replies (
  id SERIAL PRIMARY KEY,
  tweet_id INTEGER NOT NULL REFERENCES tweets(id) ON DELETE CASCADE,
  model_name VARCHAR(50) NOT NULL,
  text TEXT NOT NULL,
  character_count INTEGER,
  style_score FLOAT,
  toxicity_score FLOAT,
  status VARCHAR(20) DEFAULT 'pending',
  approved_at TIMESTAMP,
  rejected_at TIMESTAMP,
  posted_at TIMESTAMP,
  superseded BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Keywords table
CREATE TABLE keywords (
  id SERIAL PRIMARY KEY,
  episode_id INTEGER NOT NULL REFERENCES podcast_episodes(id) ON DELETE CASCADE,
  keyword VARCHAR(100) NOT NULL,
  weight FLOAT DEFAULT 1.0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(episode_id, keyword)
);

-- Pipeline runs table
CREATE TABLE pipeline_runs (
  id SERIAL PRIMARY KEY,
  run_id VARCHAR(100) UNIQUE NOT NULL,
  episode_id INTEGER REFERENCES podcast_episodes(id) ON DELETE SET NULL,
  stage VARCHAR(50),
  status VARCHAR(20) DEFAULT 'pending',
  started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP,
  error_message TEXT,
  metrics JSONB,
  artifacts_path TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Quota usage table
CREATE TABLE quota_usage (
  id SERIAL PRIMARY KEY,
  service VARCHAR(50) NOT NULL,
  endpoint VARCHAR(100),
  count INTEGER DEFAULT 1,
  quota_period DATE NOT NULL,
  quota_limit INTEGER,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit log table
CREATE TABLE audit_log (
  id SERIAL PRIMARY KEY,
  action VARCHAR(100) NOT NULL,
  resource_type VARCHAR(50),
  resource_id VARCHAR(100),
  user_id VARCHAR(100),
  details JSONB,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Settings table
CREATE TABLE settings (
  id SERIAL PRIMARY KEY,
  key VARCHAR(100) UNIQUE NOT NULL,
  value TEXT,
  description TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_tweets_status ON tweets(status);
CREATE INDEX idx_tweets_episode ON tweets(episode_id);
CREATE INDEX idx_tweets_twitter_id ON tweets(twitter_id);
CREATE INDEX idx_drafts_tweet ON draft_replies(tweet_id);
CREATE INDEX idx_drafts_status ON draft_replies(status);
CREATE INDEX idx_keywords_episode ON keywords(episode_id);
CREATE INDEX idx_pipeline_runs_episode ON pipeline_runs(episode_id);
CREATE INDEX idx_audit_log_resource ON audit_log(resource_type, resource_id);

-- Create updated_at triggers
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_episodes_updated_at BEFORE UPDATE ON podcast_episodes
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_tweets_updated_at BEFORE UPDATE ON tweets
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_drafts_updated_at BEFORE UPDATE ON draft_replies
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_settings_updated_at BEFORE UPDATE ON settings
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();