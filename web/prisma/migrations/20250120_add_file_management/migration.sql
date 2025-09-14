-- Add file management columns to podcast_episodes table
ALTER TABLE "podcast_episodes" 
ADD COLUMN "episode_dir" VARCHAR(255),
ADD COLUMN "file_config" JSON DEFAULT '{}',
ADD COLUMN "pipeline_state" JSON DEFAULT '{}';

-- Create index for episode directory lookups
CREATE INDEX "idx_episodes_episode_dir" ON "podcast_episodes"("episode_dir");

-- Add comment explaining the JSON structure
COMMENT ON COLUMN "podcast_episodes"."file_config" IS 'JSON object containing file paths and configuration for the episode pipeline';
COMMENT ON COLUMN "podcast_episodes"."pipeline_state" IS 'JSON object tracking the state and history of each pipeline stage';

-- Update existing episodes to have a default episode directory
UPDATE "podcast_episodes" 
SET "episode_dir" = CONCAT('episodes/', TO_CHAR("created_at", 'YYYYMMDD'), '-ep', "id", '-episode')
WHERE "episode_dir" IS NULL;