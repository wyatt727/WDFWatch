-- Initialize database schema
-- This script creates all base tables needed for WDFWatch

-- Create podcast_episodes table first (needed by other tables)
CREATE TABLE IF NOT EXISTS "podcast_episodes" (
  "id" SERIAL PRIMARY KEY,
  "title" VARCHAR(255) NOT NULL,
  "uploaded_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  "published_at" TIMESTAMP,
  "transcript_text" TEXT,
  "summary_text" TEXT,
  "summary_data" JSONB,
  "keywords" JSONB,
  "status" VARCHAR(50) DEFAULT 'no_transcript',
  "video_url" VARCHAR(500),
  "episode_dir" VARCHAR(255),
  "created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create tweets table
CREATE TABLE IF NOT EXISTS "tweets" (
  "id" SERIAL PRIMARY KEY,
  "twitter_id" VARCHAR(50) UNIQUE NOT NULL,
  "author_handle" VARCHAR(100) NOT NULL,
  "author_name" VARCHAR(255),
  "full_text" TEXT NOT NULL,
  "text_preview" VARCHAR(280),
  "relevance_score" FLOAT,
  "classification_rationale" TEXT,
  "status" VARCHAR(20) DEFAULT 'unclassified',
  "thread_data" JSONB,
  "metrics" JSONB,
  "flags" JSONB,
  "scraped_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  "created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  "episode_id" INTEGER REFERENCES "podcast_episodes"("id")
);

-- Create draft_replies table
CREATE TABLE IF NOT EXISTS "draft_replies" (
  "id" SERIAL PRIMARY KEY,
  "tweet_id" INTEGER REFERENCES "tweets"("id"),
  "reply_text" TEXT NOT NULL,
  "model_used" VARCHAR(100),
  "status" VARCHAR(20) DEFAULT 'pending',
  "approved_by" VARCHAR(100),
  "created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create keywords table
CREATE TABLE IF NOT EXISTS "keywords" (
  "id" SERIAL PRIMARY KEY,
  "keyword" VARCHAR(100) NOT NULL,
  "weight" FLOAT DEFAULT 1.0,
  "episode_id" INTEGER REFERENCES "podcast_episodes"("id"),
  "created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create pipeline_runs table
CREATE TABLE IF NOT EXISTS "pipeline_runs" (
  "id" SERIAL PRIMARY KEY,
  "episode_id" INTEGER REFERENCES "podcast_episodes"("id"),
  "stage" VARCHAR(50) NOT NULL,
  "status" VARCHAR(20) NOT NULL,
  "started_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  "completed_at" TIMESTAMP,
  "error_message" TEXT,
  "metadata" JSONB
);

-- Create quota_usage table
CREATE TABLE IF NOT EXISTS "quota_usage" (
  "id" SERIAL PRIMARY KEY,
  "period_start" DATE NOT NULL,
  "period_end" DATE NOT NULL,
  "total_allowed" INTEGER DEFAULT 10000,
  "used" INTEGER DEFAULT 0,
  "source_breakdown" JSONB,
  "daily_usage" JSONB,
  "created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create settings table
CREATE TABLE IF NOT EXISTS "settings" (
  "id" SERIAL PRIMARY KEY,
  "key" VARCHAR(50) UNIQUE NOT NULL,
  "value" JSONB,
  "created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create audit_logs table
CREATE TABLE IF NOT EXISTS "audit_logs" (
  "id" SERIAL PRIMARY KEY,
  "user_id" VARCHAR(100),
  "action" VARCHAR(50) NOT NULL,
  "resource_type" VARCHAR(50),
  "resource_id" INTEGER,
  "old_value" JSONB,
  "new_value" JSONB,
  "metadata" JSONB,
  "ip_address" VARCHAR(45),
  "user_agent" TEXT,
  "created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create prompt_templates table
CREATE TABLE IF NOT EXISTS "prompt_templates" (
  "id" SERIAL PRIMARY KEY,
  "key" VARCHAR(50) UNIQUE NOT NULL,
  "name" VARCHAR(100) NOT NULL,
  "description" TEXT,
  "template" TEXT NOT NULL,
  "variables" JSONB,
  "is_active" BOOLEAN DEFAULT true,
  "version" INTEGER DEFAULT 1,
  "created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  "created_by" VARCHAR(100)
);

-- Create prompt_history table
CREATE TABLE IF NOT EXISTS "prompt_history" (
  "id" SERIAL PRIMARY KEY,
  "prompt_id" INTEGER REFERENCES "prompt_templates"("id") ON DELETE CASCADE,
  "version" INTEGER NOT NULL,
  "template" TEXT NOT NULL,
  "changed_by" VARCHAR(100),
  "change_note" TEXT,
  "created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create context_files table
CREATE TABLE IF NOT EXISTS "context_files" (
  "id" SERIAL PRIMARY KEY,
  "key" VARCHAR(50) UNIQUE NOT NULL,
  "name" VARCHAR(100) NOT NULL,
  "description" TEXT,
  "content" TEXT NOT NULL,
  "is_active" BOOLEAN DEFAULT true,
  "created_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  "updated_by" VARCHAR(100)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS "idx_tweets_episode_id" ON "tweets"("episode_id");
CREATE INDEX IF NOT EXISTS "idx_tweets_status" ON "tweets"("status");
CREATE INDEX IF NOT EXISTS "idx_tweets_twitter_id" ON "tweets"("twitter_id");
CREATE INDEX IF NOT EXISTS "idx_draft_replies_tweet_id" ON "draft_replies"("tweet_id");
CREATE INDEX IF NOT EXISTS "idx_draft_replies_status" ON "draft_replies"("status");
CREATE INDEX IF NOT EXISTS "idx_keywords_episode_id" ON "keywords"("episode_id");
CREATE INDEX IF NOT EXISTS "idx_pipeline_runs_episode_id" ON "pipeline_runs"("episode_id");
CREATE INDEX IF NOT EXISTS "idx_audit_logs_created_at" ON "audit_logs"("created_at" DESC);
CREATE INDEX IF NOT EXISTS "idx_audit_logs_action" ON "audit_logs"("action");
CREATE INDEX IF NOT EXISTS "idx_audit_logs_resource" ON "audit_logs"("resource_type", "resource_id");
CREATE INDEX IF NOT EXISTS "idx_prompt_history_prompt_id" ON "prompt_history"("prompt_id");
CREATE INDEX IF NOT EXISTS "idx_prompt_history_created_at" ON "prompt_history"("created_at" DESC);