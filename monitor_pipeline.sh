#!/bin/bash

# Pipeline Runner Monitor Script
# Detects crashes and provides better alerting

PIPELINE_RUNNER_LOG="/home/debian/Tools/WDFWatch/pipeline_runner.log"
PIPELINE_SCRIPT="/home/debian/Tools/WDFWatch/pipeline_runner.py"
JOB_STATUS_SCRIPT="/home/debian/Tools/WDFWatch/job_status_monitor.py"
ALERT_LOG="/home/debian/Tools/WDFWatch/pipeline_alerts.log"

log_alert() {
    echo "[$(date)] ALERT: $1" | tee -a "$ALERT_LOG"
}

check_pipeline_runner() {
    local pid=$(ps aux | grep "python3 pipeline_runner.py" | grep -v grep | awk '{print $2}')

    if [ -z "$pid" ]; then
        log_alert "Pipeline runner process NOT FOUND - crashed or stopped!"

        # Auto-restart
        cd /home/debian/Tools/WDFWatch
        nohup python3 pipeline_runner.py >> pipeline_runner.log 2>&1 &
        local new_pid=$!

        log_alert "Restarted pipeline runner with PID: $new_pid"
        return 1
    else
        echo "[$(date)] Pipeline runner healthy (PID: $pid)" >> "$ALERT_LOG"
        return 0
    fi
}

check_job_status_monitor() {
    local pid=$(ps aux | grep "python3 job_status_monitor.py" | grep -v grep | awk '{print $2}')

    if [ -z "$pid" ]; then
        log_alert "Job status monitor process NOT FOUND - crashed or stopped!"

        # Auto-restart
        cd /home/debian/Tools/WDFWatch
        nohup python3 job_status_monitor.py >> job_status_monitor.log 2>&1 &
        local new_pid=$!

        log_alert "Restarted job status monitor with PID: $new_pid"
        return 1
    else
        echo "[$(date)] Job status monitor healthy (PID: $pid)" >> "$ALERT_LOG"
        return 0
    fi
}

check_stuck_jobs() {
    # Check for jobs running longer than 10 minutes without completion
    local stuck_jobs=$(docker exec wdfwatch-postgres psql -U wdfwatch -d wdfwatch -c \
        "SELECT COUNT(*) FROM pipeline_runs WHERE status = 'running' AND started_at < NOW() - INTERVAL '10 minutes';" \
        -t | xargs)

    if [ "$stuck_jobs" -gt 0 ]; then
        log_alert "Found $stuck_jobs stuck jobs running longer than 10 minutes!"

        # List the stuck jobs
        docker exec wdfwatch-postgres psql -U wdfwatch -d wdfwatch -c \
            "SELECT id, run_id, episode_id, stage, started_at FROM pipeline_runs WHERE status = 'running' AND started_at < NOW() - INTERVAL '10 minutes';" \
            >> "$ALERT_LOG"
    fi
}

check_failed_jobs() {
    # Check for jobs that have result files but are still marked as running
    local job_files_count=$(find /home/debian/Tools/WDFWatch/claude-pipeline/jobs -name "*.result" | wc -l)
    local running_jobs_count=$(docker exec wdfwatch-postgres psql -U wdfwatch -d wdfwatch -c \
        "SELECT COUNT(*) FROM pipeline_runs WHERE status = 'running';" -t | xargs)

    if [ "$running_jobs_count" -gt 0 ] && [ "$job_files_count" -ge "$running_jobs_count" ]; then
        log_alert "Potential silent failures detected - $running_jobs_count running jobs but $job_files_count result files exist"
    fi
}

# Main monitoring loop
log_alert "Pipeline monitor started"

while true; do
    check_pipeline_runner
    check_job_status_monitor
    check_stuck_jobs
    check_failed_jobs
    sleep 60  # Check every minute
done