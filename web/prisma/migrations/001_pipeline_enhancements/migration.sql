-- Pipeline Enhancement Migration
-- Adds tables and columns for enhanced pipeline management

-- Add pipeline error tracking table
CREATE TABLE IF NOT EXISTS pipeline_errors (
    id SERIAL PRIMARY KEY,
    episode_id INTEGER NOT NULL REFERENCES podcast_episodes(id) ON DELETE CASCADE,
    run_id VARCHAR(255) NOT NULL,
    stage VARCHAR(100) NOT NULL,
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    attempt_number INTEGER NOT NULL DEFAULT 1,
    system_state JSONB,
    suggested_action JSONB,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Add indexes for pipeline_errors
CREATE INDEX IF NOT EXISTS idx_pipeline_errors_episode_id ON pipeline_errors(episode_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_errors_run_id ON pipeline_errors(run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_errors_stage ON pipeline_errors(stage);
CREATE INDEX IF NOT EXISTS idx_pipeline_errors_error_type ON pipeline_errors(error_type);
CREATE INDEX IF NOT EXISTS idx_pipeline_errors_timestamp ON pipeline_errors(timestamp);

-- Update pipeline_runs table with enhanced fields
ALTER TABLE pipeline_runs 
ADD COLUMN IF NOT EXISTS run_id VARCHAR(255) UNIQUE,
ADD COLUMN IF NOT EXISTS current_stage VARCHAR(100),
ADD COLUMN IF NOT EXISTS progress INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
ADD COLUMN IF NOT EXISTS estimated_completion TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- Add indexes for pipeline_runs enhanced fields
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_run_id ON pipeline_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_current_stage ON pipeline_runs(current_stage);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_progress ON pipeline_runs(progress);

-- Add pipeline validation results table
CREATE TABLE IF NOT EXISTS pipeline_validations (
    id SERIAL PRIMARY KEY,
    episode_id INTEGER NOT NULL REFERENCES podcast_episodes(id) ON DELETE CASCADE,
    pipeline_type VARCHAR(50) NOT NULL,
    is_valid BOOLEAN NOT NULL,
    score INTEGER NOT NULL CHECK (score >= 0 AND score <= 100),
    validation_results JSONB NOT NULL,
    estimated_resolution_time INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Add indexes for pipeline_validations
CREATE INDEX IF NOT EXISTS idx_pipeline_validations_episode_id ON pipeline_validations(episode_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_validations_pipeline_type ON pipeline_validations(pipeline_type);
CREATE INDEX IF NOT EXISTS idx_pipeline_validations_is_valid ON pipeline_validations(is_valid);
CREATE INDEX IF NOT EXISTS idx_pipeline_validations_created_at ON pipeline_validations(created_at);

-- Add pipeline stage metrics table for detailed tracking
CREATE TABLE IF NOT EXISTS pipeline_stage_metrics (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(255) NOT NULL,
    stage VARCHAR(100) NOT NULL,
    episode_id INTEGER NOT NULL REFERENCES podcast_episodes(id) ON DELETE CASCADE,
    items_processed INTEGER DEFAULT 0,
    total_items INTEGER DEFAULT 0,
    processing_rate DECIMAL(10,4) DEFAULT 0,
    api_calls_used INTEGER DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    cost_incurred DECIMAL(10,6) DEFAULT 0,
    memory_used INTEGER DEFAULT 0,
    cpu_usage DECIMAL(5,2) DEFAULT 0,
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Add indexes for pipeline_stage_metrics
CREATE INDEX IF NOT EXISTS idx_pipeline_stage_metrics_run_id ON pipeline_stage_metrics(run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_stage_metrics_episode_id ON pipeline_stage_metrics(episode_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_stage_metrics_stage ON pipeline_stage_metrics(stage);
CREATE INDEX IF NOT EXISTS idx_pipeline_stage_metrics_created_at ON pipeline_stage_metrics(created_at);

-- Add trigger for updated_at on pipeline_stage_metrics
CREATE OR REPLACE FUNCTION update_pipeline_stage_metrics_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_pipeline_stage_metrics_updated_at ON pipeline_stage_metrics;
CREATE TRIGGER trigger_pipeline_stage_metrics_updated_at
    BEFORE UPDATE ON pipeline_stage_metrics
    FOR EACH ROW
    EXECUTE FUNCTION update_pipeline_stage_metrics_updated_at();

-- Add pipeline configuration history table
CREATE TABLE IF NOT EXISTS pipeline_configurations (
    id SERIAL PRIMARY KEY,
    episode_id INTEGER REFERENCES podcast_episodes(id) ON DELETE CASCADE,
    configuration_type VARCHAR(100) NOT NULL, -- 'llm_models', 'scoring', 'keywords', etc.
    configuration_data JSONB NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT true,
    applied_at TIMESTAMP WITH TIME ZONE,
    created_by VARCHAR(255) DEFAULT 'system',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Add indexes for pipeline_configurations
CREATE INDEX IF NOT EXISTS idx_pipeline_configurations_episode_id ON pipeline_configurations(episode_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_configurations_type ON pipeline_configurations(configuration_type);
CREATE INDEX IF NOT EXISTS idx_pipeline_configurations_is_active ON pipeline_configurations(is_active);
CREATE INDEX IF NOT EXISTS idx_pipeline_configurations_created_at ON pipeline_configurations(created_at);

-- Add performance metrics table for analytics
CREATE TABLE IF NOT EXISTS pipeline_performance_metrics (
    id SERIAL PRIMARY KEY,
    stage VARCHAR(100) NOT NULL,
    pipeline_type VARCHAR(50) NOT NULL,
    duration_minutes DECIMAL(10,4) NOT NULL,
    success BOOLEAN NOT NULL,
    items_processed INTEGER DEFAULT 0,
    throughput_per_minute DECIMAL(10,4) DEFAULT 0,
    cost_usd DECIMAL(10,6) DEFAULT 0,
    memory_peak_mb INTEGER DEFAULT 0,
    cpu_avg_percent DECIMAL(5,2) DEFAULT 0,
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    episode_id INTEGER REFERENCES podcast_episodes(id) ON DELETE SET NULL,
    run_id VARCHAR(255)
);

-- Add indexes for pipeline_performance_metrics
CREATE INDEX IF NOT EXISTS idx_pipeline_performance_metrics_stage ON pipeline_performance_metrics(stage);
CREATE INDEX IF NOT EXISTS idx_pipeline_performance_metrics_pipeline_type ON pipeline_performance_metrics(pipeline_type);
CREATE INDEX IF NOT EXISTS idx_pipeline_performance_metrics_recorded_at ON pipeline_performance_metrics(recorded_at);
CREATE INDEX IF NOT EXISTS idx_pipeline_performance_metrics_success ON pipeline_performance_metrics(success);

-- Add resource usage tracking table
CREATE TABLE IF NOT EXISTS pipeline_resource_usage (
    id SERIAL PRIMARY KEY,
    episode_id INTEGER NOT NULL REFERENCES podcast_episodes(id) ON DELETE CASCADE,
    run_id VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    memory_usage_mb INTEGER DEFAULT 0,
    cpu_usage_percent DECIMAL(5,2) DEFAULT 0,
    disk_io_mb_per_sec DECIMAL(10,4) DEFAULT 0,
    network_io_mb_per_sec DECIMAL(10,4) DEFAULT 0,
    active_connections INTEGER DEFAULT 0,
    queue_length INTEGER DEFAULT 0
);

-- Add indexes for pipeline_resource_usage
CREATE INDEX IF NOT EXISTS idx_pipeline_resource_usage_episode_id ON pipeline_resource_usage(episode_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_resource_usage_run_id ON pipeline_resource_usage(run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_resource_usage_timestamp ON pipeline_resource_usage(timestamp);

-- Add recovery actions table
CREATE TABLE IF NOT EXISTS pipeline_recovery_actions (
    id SERIAL PRIMARY KEY,
    episode_id INTEGER NOT NULL REFERENCES podcast_episodes(id) ON DELETE CASCADE,
    run_id VARCHAR(255) NOT NULL,
    stage VARCHAR(100) NOT NULL,
    error_type VARCHAR(100) NOT NULL,
    action_type VARCHAR(50) NOT NULL, -- 'retry', 'skip', 'rollback', 'manual_intervention'
    action_description TEXT,
    automated BOOLEAN NOT NULL DEFAULT false,
    success BOOLEAN,
    executed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    result_message TEXT
);

-- Add indexes for pipeline_recovery_actions
CREATE INDEX IF NOT EXISTS idx_pipeline_recovery_actions_episode_id ON pipeline_recovery_actions(episode_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_recovery_actions_run_id ON pipeline_recovery_actions(run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_recovery_actions_stage ON pipeline_recovery_actions(stage);
CREATE INDEX IF NOT EXISTS idx_pipeline_recovery_actions_action_type ON pipeline_recovery_actions(action_type);
CREATE INDEX IF NOT EXISTS idx_pipeline_recovery_actions_executed_at ON pipeline_recovery_actions(executed_at);

-- Update podcast_episodes table with enhanced pipeline fields
ALTER TABLE podcast_episodes 
ADD COLUMN IF NOT EXISTS pipeline_type VARCHAR(20) DEFAULT 'legacy',
ADD COLUMN IF NOT EXISTS claude_pipeline_status VARCHAR(100),
ADD COLUMN IF NOT EXISTS last_validation_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS last_validation_score INTEGER CHECK (last_validation_score >= 0 AND last_validation_score <= 100),
ADD COLUMN IF NOT EXISTS pipeline_configuration JSONB DEFAULT '{}';

-- Add indexes for new podcast_episodes fields
CREATE INDEX IF NOT EXISTS idx_podcast_episodes_claude_pipeline_status ON podcast_episodes(claude_pipeline_status);
CREATE INDEX IF NOT EXISTS idx_podcast_episodes_last_validation_at ON podcast_episodes(last_validation_at);

-- Create views for common queries

-- Pipeline status overview
CREATE OR REPLACE VIEW pipeline_status_overview AS
SELECT 
    pe.id as episode_id,
    pe.title,
    pe.pipeline_type,
    pe.claude_pipeline_status,
    pe.last_validation_score,
    pr.run_id,
    pr.status as current_status,
    pr.current_stage,
    pr.progress,
    pr.started_at,
    pr.estimated_completion,
    COUNT(per.id) as error_count,
    MAX(per.timestamp) as last_error_at
FROM podcast_episodes pe
LEFT JOIN pipeline_runs pr ON pe.id = pr.episode_id 
    AND pr.started_at = (
        SELECT MAX(started_at) 
        FROM pipeline_runs 
        WHERE episode_id = pe.id
    )
LEFT JOIN pipeline_errors per ON pe.id = per.episode_id 
    AND pr.run_id IS NOT NULL
    AND per.run_id = pr.run_id
GROUP BY pe.id, pe.title, pe.pipeline_type, pe.claude_pipeline_status, 
         pe.last_validation_score, pr.run_id, pr.status, pr.current_stage, 
         pr.progress, pr.started_at, pr.estimated_completion;

-- Stage performance summary
CREATE OR REPLACE VIEW stage_performance_summary AS
SELECT 
    stage,
    pipeline_type,
    COUNT(*) as execution_count,
    COUNT(CASE WHEN success THEN 1 END) as success_count,
    ROUND(AVG(duration_minutes)::numeric, 2) as avg_duration_minutes,
    ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_minutes))::numeric, 2) as median_duration_minutes,
    ROUND(AVG(throughput_per_minute)::numeric, 2) as avg_throughput,
    ROUND(SUM(cost_usd)::numeric, 4) as total_cost_usd,
    MAX(recorded_at) as last_execution
FROM pipeline_performance_metrics
WHERE recorded_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY stage, pipeline_type
ORDER BY stage, pipeline_type;

-- Error frequency analysis
CREATE OR REPLACE VIEW error_frequency_analysis AS
SELECT 
    error_type,
    stage,
    COUNT(*) as occurrence_count,
    COUNT(DISTINCT episode_id) as affected_episodes,
    AVG(attempt_number) as avg_attempts,
    MAX(timestamp) as last_occurrence,
    ROUND(
        (COUNT(*) * 100.0 / SUM(COUNT(*)) OVER())::numeric, 
        2
    ) as percentage_of_total_errors
FROM pipeline_errors
WHERE timestamp >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY error_type, stage
ORDER BY occurrence_count DESC;

-- Resource usage trends
CREATE OR REPLACE VIEW resource_usage_trends AS
SELECT 
    DATE_TRUNC('hour', timestamp) as hour,
    COUNT(DISTINCT episode_id) as concurrent_episodes,
    ROUND(AVG(memory_usage_mb)::numeric, 2) as avg_memory_mb,
    ROUND(MAX(memory_usage_mb)::numeric, 2) as peak_memory_mb,
    ROUND(AVG(cpu_usage_percent)::numeric, 2) as avg_cpu_percent,
    ROUND(MAX(cpu_usage_percent)::numeric, 2) as peak_cpu_percent,
    ROUND(AVG(active_connections)::numeric, 2) as avg_connections
FROM pipeline_resource_usage
WHERE timestamp >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY DATE_TRUNC('hour', timestamp)
ORDER BY hour;

-- Recovery success rates
CREATE OR REPLACE VIEW recovery_success_rates AS
SELECT 
    action_type,
    error_type,
    COUNT(*) as total_attempts,
    COUNT(CASE WHEN success THEN 1 END) as successful_attempts,
    ROUND(
        (COUNT(CASE WHEN success THEN 1 END) * 100.0 / COUNT(*))::numeric, 
        2
    ) as success_rate_percent,
    ROUND((AVG(EXTRACT(EPOCH FROM (completed_at - executed_at)) / 60))::numeric, 2) as avg_duration_minutes
FROM pipeline_recovery_actions
WHERE executed_at >= CURRENT_DATE - INTERVAL '30 days'
    AND completed_at IS NOT NULL
GROUP BY action_type, error_type
ORDER BY success_rate_percent DESC;

-- Add comments for documentation
COMMENT ON TABLE pipeline_errors IS 'Tracks errors that occur during pipeline execution with context for recovery';
COMMENT ON TABLE pipeline_stage_metrics IS 'Detailed metrics for individual pipeline stages';
COMMENT ON TABLE pipeline_configurations IS 'Version history of pipeline configurations';
COMMENT ON TABLE pipeline_performance_metrics IS 'Performance analytics data for pipeline optimization';
COMMENT ON TABLE pipeline_resource_usage IS 'System resource usage tracking during pipeline execution';
COMMENT ON TABLE pipeline_recovery_actions IS 'Log of automated and manual recovery actions taken';

COMMENT ON VIEW pipeline_status_overview IS 'Current status of all episodes with pipeline information';
COMMENT ON VIEW stage_performance_summary IS 'Performance statistics by stage and pipeline type';
COMMENT ON VIEW error_frequency_analysis IS 'Error patterns and frequency analysis';
COMMENT ON VIEW resource_usage_trends IS 'System resource usage trends over time';
COMMENT ON VIEW recovery_success_rates IS 'Effectiveness of different recovery strategies';