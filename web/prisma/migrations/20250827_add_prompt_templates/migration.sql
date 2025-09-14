-- CreateTable for original prompt backups
CREATE TABLE "prompt_originals" (
    "stage" VARCHAR(50) NOT NULL,
    "content" TEXT NOT NULL,
    "file_path" VARCHAR(255) NOT NULL,
    "backed_up_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "prompt_originals_pkey" PRIMARY KEY ("stage")
);

-- Add stage column to existing prompt_templates table
ALTER TABLE "prompt_templates" ADD COLUMN "stage" VARCHAR(50);

-- Update existing prompt templates to have stages based on their key
UPDATE "prompt_templates" 
SET "stage" = CASE 
    WHEN "key" LIKE '%classifier%' THEN 'classifier'
    WHEN "key" LIKE '%moderator%' THEN 'moderator' 
    WHEN "key" LIKE '%responder%' THEN 'responder'
    WHEN "key" LIKE '%summarizer%' THEN 'summarizer'
    ELSE 'custom'
END;

-- CreateIndex for finding prompts by stage
CREATE INDEX "prompt_templates_stage_idx" ON "prompt_templates"("stage");