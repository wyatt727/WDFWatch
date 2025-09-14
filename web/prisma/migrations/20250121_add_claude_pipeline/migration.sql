-- Add Claude-specific fields to podcast_episodes
ALTER TABLE "podcast_episodes" 
ADD COLUMN IF NOT EXISTS "claude_episode_dir" VARCHAR(255),
ADD COLUMN IF NOT EXISTS "claude_context_generated" BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS "claude_pipeline_status" VARCHAR(50),
ADD COLUMN IF NOT EXISTS "pipeline_type" VARCHAR(20) DEFAULT 'legacy';

-- Create claude_pipeline_runs table
CREATE TABLE "claude_pipeline_runs" (
  "id" SERIAL PRIMARY KEY,
  "episode_id" INTEGER NOT NULL,
  "run_id" VARCHAR(255) UNIQUE NOT NULL,
  "stage" VARCHAR(50) NOT NULL,
  "claude_mode" VARCHAR(20) NOT NULL,
  "input_tokens" INTEGER DEFAULT 0,
  "output_tokens" INTEGER DEFAULT 0,
  "cost_usd" DECIMAL(10, 4) DEFAULT 0,
  "duration_seconds" INTEGER,
  "status" VARCHAR(20) DEFAULT 'running',
  "error_message" TEXT,
  "started_at" TIMESTAMP DEFAULT NOW(),
  "completed_at" TIMESTAMP,
  "metadata" JSONB,
  CONSTRAINT "fk_claude_pipeline_runs_episode" FOREIGN KEY ("episode_id") REFERENCES "podcast_episodes"("id")
);

CREATE INDEX "idx_claude_pipeline_runs_episode_id" ON "claude_pipeline_runs"("episode_id");
CREATE INDEX "idx_claude_pipeline_runs_status" ON "claude_pipeline_runs"("status");
CREATE INDEX "idx_claude_pipeline_runs_started_at" ON "claude_pipeline_runs"("started_at" DESC);

-- Create claude_costs table
CREATE TABLE "claude_costs" (
  "id" SERIAL PRIMARY KEY,
  "date" DATE NOT NULL,
  "mode" VARCHAR(20) NOT NULL,
  "total_input_tokens" BIGINT DEFAULT 0,
  "total_output_tokens" BIGINT DEFAULT 0,
  "total_cost_usd" DECIMAL(10, 4) DEFAULT 0,
  "run_count" INTEGER DEFAULT 0,
  "created_at" TIMESTAMP DEFAULT NOW(),
  "updated_at" TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX "idx_claude_costs_date_mode" ON "claude_costs"("date", "mode");
CREATE INDEX "idx_claude_costs_date" ON "claude_costs"("date");

-- Create episode_contexts table
CREATE TABLE "episode_contexts" (
  "id" SERIAL PRIMARY KEY,
  "episode_id" INTEGER NOT NULL,
  "context_type" VARCHAR(50) NOT NULL,
  "context_content" TEXT NOT NULL,
  "claude_mode" VARCHAR(20),
  "version" INTEGER DEFAULT 1,
  "is_active" BOOLEAN DEFAULT true,
  "created_at" TIMESTAMP DEFAULT NOW(),
  "updated_at" TIMESTAMP DEFAULT NOW(),
  CONSTRAINT "fk_episode_contexts_episode" FOREIGN KEY ("episode_id") REFERENCES "podcast_episodes"("id")
);

CREATE INDEX "idx_episode_contexts_episode_id" ON "episode_contexts"("episode_id");
CREATE INDEX "idx_episode_contexts_context_type" ON "episode_contexts"("context_type");

-- Add trigger for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_claude_costs_updated_at BEFORE UPDATE ON "claude_costs" 
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_episode_contexts_updated_at BEFORE UPDATE ON "episode_contexts" 
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();