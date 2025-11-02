/**
 * Individual Pipeline Stage Execution API Route
 * 
 * Runs individual pipeline stages for an episode with real-time updates.
 * Integrates with: Python task modules via subprocess, SSE for progress updates
 */

import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';
import { z } from 'zod';
import { spawn, ChildProcess } from 'child_process';
import { join } from 'path';
import { existsSync, readFileSync } from 'fs';
import { processTracker } from '@/lib/process-tracker';
import { ProcessTracker } from '@/lib/process-tracker';

// Schema for stage execution request
const legacyStageSchema = z.object({
  stageId: z.enum(['summarization', 'fewshot', 'scraping', 'classification', 'response', 'moderation']),
  useCached: z.boolean().optional().default(false),
  force: z.boolean().optional().default(false),
  forceRefresh: z.boolean().optional().default(false), // For scraping: ignore cache
});

const claudeStageSchema = z.object({
  stageId: z.enum(['summarization', 'scraping', 'classification', 'response', 'moderation', 'full']),
  useCached: z.boolean().optional().default(false),
  force: z.boolean().optional().default(false),
  forceRefresh: z.boolean().optional().default(false), // For scraping: ignore cache
});

// Stage to Python task mapping for legacy pipeline
const LEGACY_STAGE_TO_TASK: Record<string, string> = {
  'summarization': 'src/wdf/tasks/summarise.py',
  'fewshot': 'src/wdf/tasks/fewshot.py',
  'scraping': 'src/wdf/tasks/scrape.py',
  'classification': 'src/wdf/tasks/classify.py',
  'response': 'src/wdf/tasks/deepseek.py',
  'moderation': 'src/wdf/tasks/web_moderation.py',
};

// Stage to Claude pipeline mapping
const CLAUDE_STAGE_TO_TASK: Record<string, string> = {
  'summarization': 'web/scripts/claude_pipeline_bridge.py --stage summarize',
  'scraping': 'web/scripts/claude_pipeline_bridge.py --stage scraping',
  'classification': 'web/scripts/claude_pipeline_bridge.py --stage classify',
  'response': 'web/scripts/claude_pipeline_bridge.py --stage respond',
  'moderation': 'web/scripts/claude_pipeline_bridge.py --stage moderate',
  'full': 'web/scripts/claude_pipeline_bridge.py --stage full',
};

// Map web UI stage names to Claude pipeline stage names
const WEB_TO_CLAUDE_STAGE_MAP: Record<string, string> = {
  'summarization': 'summarize',
  'scraping': 'scraping',
  'classification': 'classify',
  'response': 'respond',
  'moderation': 'moderate',
  'full': 'full',
};

// Load environment variables from .env file
function loadEnvVariables(): Record<string, string> {
  const envVars: Record<string, string> = {};

  try {
    // Load from main .env file in project root - use absolute path to avoid confusion
    const envPath = '/home/debian/Tools/WDFWatch/.env';
    console.log('Looking for main .env file at:', envPath);
    if (existsSync(envPath)) {
      const envContent = readFileSync(envPath, 'utf8');
      envContent.split('\n').forEach(line => {
        if (line.trim() && !line.startsWith('#')) {
          const [key, ...valueParts] = line.split('=');
          if (key && valueParts.length > 0) {
            let value = valueParts.join('=').trim();
            // Remove quotes if present
            if ((value.startsWith('"') && value.endsWith('"')) ||
                (value.startsWith("'") && value.endsWith("'"))) {
              value = value.slice(1, -1);
            }
            envVars[key.trim()] = value;
          }
        }
      });
    }

    // Also try to load from .env.wdfwatch for WDFwatch tokens
    const wdfwatchEnvPath = '/home/debian/Tools/WDFWatch/.env.wdfwatch';
    console.log('Looking for .env.wdfwatch file at:', wdfwatchEnvPath);
    if (existsSync(wdfwatchEnvPath)) {
      const wdfwatchContent = readFileSync(wdfwatchEnvPath, 'utf8');
      wdfwatchContent.split('\n').forEach(line => {
        if (line.trim() && !line.startsWith('#')) {
          const [key, ...valueParts] = line.split('=');
          if (key && valueParts.length > 0) {
            let value = valueParts.join('=').trim();
            // Remove quotes if present
            if ((value.startsWith('"') && value.endsWith('"')) ||
                (value.startsWith("'") && value.endsWith("'"))) {
              value = value.slice(1, -1);
            }
            // WDFwatch tokens take precedence
            envVars[key.trim()] = value;
          }
        }
      });
    }
  } catch (error) {
    console.error('Error loading environment variables:', error);
  }

  // Log loaded API keys for debugging (only show if they exist)
  console.log('Loaded environment variables:', {
    API_KEY: envVars.API_KEY ? 'FOUND' : 'MISSING',
    WDFWATCH_ACCESS_TOKEN: envVars.WDFWATCH_ACCESS_TOKEN ? 'FOUND' : 'MISSING',
    BEARER_TOKEN: envVars.BEARER_TOKEN ? 'FOUND' : 'MISSING',
    CLIENT_ID: envVars.CLIENT_ID ? 'FOUND' : 'MISSING',
  });

  return envVars;
}

// Process tracking is now handled by the shared processTracker

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const episodeId = parseInt(params.id);
    const body = await request.json();
    
    // Check if episode exists and get pipeline type
    const episode = await prisma.podcastEpisode.findUnique({
      where: { id: episodeId },
      select: {
        id: true,
        title: true,
        pipelineType: true,
        claudeEpisodeDir: true,
        episodeDir: true,
      },
    });
    
    if (!episode) {
      return NextResponse.json(
        { error: 'Episode not found' },
        { status: 404 }
      );
    }

    // Validate input based on pipeline type
    const isClaudePipeline = episode.pipelineType === 'claude';
    let stageId: string, useCached: boolean, force: boolean, forceRefresh: boolean;
    
    if (isClaudePipeline) {
      const { stageId: claudeStageId, useCached: claudeUseCached, force: claudeForce, forceRefresh: claudeForceRefresh } = claudeStageSchema.parse(body);
      stageId = claudeStageId;
      useCached = claudeUseCached;
      force = claudeForce;
      forceRefresh = claudeForceRefresh;
    } else {
      const { stageId: legacyStageId, useCached: legacyUseCached, force: legacyForce, forceRefresh: legacyForceRefresh } = legacyStageSchema.parse(body);
      stageId = legacyStageId;
      useCached = legacyUseCached;
      force = legacyForce;
      forceRefresh = legacyForceRefresh;
    }
    
    // Check if stage is already running
    if (processTracker.isStageRunning(episodeId, stageId)) {
      return NextResponse.json(
        { error: 'Stage is already running for this episode' },
        { status: 400 }
      );
    }
    
    // Generate run ID
    const runId = `episode-${episodeId}-${stageId}-${Date.now()}`;

    // Helper function to handle process completion - defined at top level for all execution paths
    async function handleProcessCompletion(episodeId: number, stageId: string, runId: string, exitCode: number | null, signal: string | null) {
      const timestamp = new Date().toISOString();
      console.log(`[${timestamp}] [PROCESS COMPLETE] Exit Code: ${exitCode}, Signal: ${signal}`);

      // Unregister from tracker
      const processKey = ProcessTracker.getStageKey(episodeId, stageId);
      processTracker.unregister(processKey);

      const status = exitCode === 0 ? 'completed' : 'failed';
      const completedAt = new Date();

      try {
        // Update pipeline run record
        const pipelineRun = await prisma.pipelineRun.findFirst({
          where: { runId },
        });

        if (pipelineRun) {
          const duration = completedAt.getTime() - pipelineRun.startedAt.getTime();

          await prisma.pipelineRun.update({
            where: { id: pipelineRun.id },
            data: {
              status,
              completedAt,
              errorMessage: exitCode !== 0 ? `Process exited with code ${exitCode}` : null,
              metrics: {
                duration,
                exitCode: exitCode || 0,
              },
            },
          });
        }

        // Create audit log entry
        await prisma.auditLog.create({
          data: {
            action: `pipeline_stage_${status}`,
            resourceType: 'episode',
            resourceId: episodeId,
            metadata: {
              runId,
              stage: stageId,
              exitCode: exitCode || 0,
            },
          },
        });

        // Emit SSE event for completion
        await emitSSEEvent({
          type: 'pipeline_stage_completed',
          episodeId: episodeId.toString(),
          stage: stageId,
          runId,
          status,
          exitCode: exitCode || 0,
        });

      } catch (error) {
        console.error('Failed to update pipeline run status:', error);
      }
    }

    // Create pipeline run record
    await prisma.pipelineRun.create({
      data: {
        runId,
        episodeId,
        stage: stageId,
        status: 'running',
        startedAt: new Date(),
      },
    });
    
    // Create audit log entry
    await prisma.auditLog.create({
      data: {
        action: 'pipeline_stage_started',
        resourceType: 'episode',
        resourceId: episodeId,
        metadata: {
          runId,
          stage: stageId,
          useCached,
          force,
        },
      },
    });
    
    // Emit SSE event for stage start
    await emitSSEEvent({
      type: 'pipeline_stage_started',
      episodeId: episodeId.toString(),
      stage: stageId,
      runId,
    });
    
    // Spawn appropriate pipeline process
    // Use venv Python path to ensure all dependencies are available
    const venvPath = join(process.cwd(), '..', 'venv', 'bin', 'python');
    const pythonPath = existsSync(venvPath) ? venvPath : (process.env.PYTHON_PATH || 'python');
    let taskProcess;
    
    // All Claude pipeline episodes (including scraping) now go through the unified orchestrator
    if (isClaudePipeline) {
      // OPTION 3: Use exec() with zsh shell to run in proper CLI environment
      console.log('🚀 OPTION 3: Using exec() with zsh shell - Episode:', episodeId, 'Stage:', stageId);

      // Import exec from child_process
      const { exec } = require('child_process');

      // Map web stage IDs to Claude pipeline stage names
      const claudeStage = WEB_TO_CLAUDE_STAGE_MAP[stageId] || stageId;
      const episodeDirName = episode.claudeEpisodeDir || episode.episodeDir || '';

      console.log(`Option 3 exec() execution: stage=${claudeStage}, episode=${episodeDirName}, forceRefresh=${forceRefresh}`);

      // Build the shell command using 'script' to provide a PTY
      // This is critical for claude CLI to work properly
      // Add --force-refresh flag when scraping with force refresh enabled
      const forceRefreshFlag = (stageId === 'scraping' && forceRefresh) ? ' --force-refresh' : '';
      const pythonCommand = `/home/debian/Tools/WDFWatch/venv/bin/python claude-pipeline/orchestrator.py --episode-id ${episodeDirName} --stages ${claudeStage}${forceRefreshFlag}`;

      const shellCommand = `
        source ~/.zshrc && \
        cd /home/debian/Tools/WDFWatch && \
        script -q -c "${pythonCommand}" /dev/null
      `.trim();

      console.log('=== OPTION 3 COMMAND ===');
      console.log('Shell: /bin/zsh');
      console.log('Command:', shellCommand);
      console.log('======================');

      // Load API keys from .env files
      const envVars = loadEnvVariables();

      // Debug: Log what credentials were loaded
      console.log('DEBUG: Loaded credentials:', {
        WDFWATCH_ACCESS_TOKEN: envVars.WDFWATCH_ACCESS_TOKEN ? 'FOUND' : 'MISSING',
        API_KEY: envVars.API_KEY ? 'FOUND' : 'MISSING',
        WDF_NO_AUTO_SCRAPE: envVars.WDF_NO_AUTO_SCRAPE || 'NOT SET',
        stageId,
        willSetAutoScrape: stageId === 'scraping' ? 'false' : 'true'
      });

      // Set timeout to 900 seconds (15 minutes) for Claude operations
      // This provides enough time for classification and response generation with large tweet batches
      const execOptions = {
        shell: '/bin/zsh',
        timeout: 900000, // 900 seconds (15 minutes) max
        maxBuffer: 10 * 1024 * 1024, // 10MB buffer for output
        env: {
          // Pass minimal environment to avoid conflicts
          HOME: process.env.HOME || '/home/debian',
          USER: process.env.USER || 'debian',
          PATH: `/home/debian/Tools/WDFWatch/venv/bin:${process.env.PATH}`, // CRITICAL: Ensure venv Python is used
          PYTHONPATH: '/home/debian/Tools/WDFWatch/web/scripts:/home/debian/Tools/WDFWatch', // CRITICAL: For web_bridge import
          WDF_WEB_MODE: 'true',
          WDF_EPISODE_ID: episodeId.toString(),  // Numeric database ID for web_bridge
          WDF_CURRENT_EPISODE_ID: episodeId.toString(), // CRITICAL: Numeric database ID (web_bridge expects this)
          WDF_RUN_ID: runId,
          DATABASE_URL: (process.env.DATABASE_URL || '').split('?')[0] || 'postgresql://postgres:password@localhost:5432/wdfwatch',
          WEB_URL: process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:8888',
          WEB_API_KEY: process.env.WEB_API_KEY || 'development-internal-api-key', // CRITICAL: web_bridge needs this
          PYTHONUNBUFFERED: '1', // For real-time output
          // Claude Code environment variables (added back for testing)
          CLAUDECODE: '1',
          CLAUDE_CODE_ENTRYPOINT: 'cli',
          // Twitter API credentials from .env files (OAuth 2.0 compatible)
          TWITTER_API_KEY: envVars.API_KEY || '',
          TWITTER_API_SECRET: envVars.API_KEY_SECRET || '',
          TWITTER_ACCESS_TOKEN: envVars.WDFWATCH_ACCESS_TOKEN || '',
          TWITTER_ACCESS_TOKEN_SECRET: '', // OAuth 2.0 doesn't use access token secret

          // Also pass the WDFwatch OAuth 2.0 tokens directly (critical for scraping!)
          WDFWATCH_ACCESS_TOKEN: envVars.WDFWATCH_ACCESS_TOKEN || '',
          WDFWATCH_REFRESH_TOKEN: envVars.WDFWATCH_REFRESH_TOKEN || '',
          WDFWATCH_ACCESS_TOKEN_SECRET: envVars.WDFWATCH_ACCESS_TOKEN_SECRET || '',

          // Override auto-scrape protection for Web UI triggered scraping
          WDF_NO_AUTO_SCRAPE: stageId === 'scraping' ? 'false' : (envVars.WDF_NO_AUTO_SCRAPE || 'true'),
          // Bypass quota check for manual triggers from Web UI
          WDF_BYPASS_QUOTA_CHECK: stageId === 'scraping' ? 'true' : 'false',
          BEARER_TOKEN: envVars.BEARER_TOKEN || '',
          CLIENT_ID: envVars.CLIENT_ID || '',
          CLIENT_SECRET: envVars.CLIENT_SECRET || '',
          // Also set the original names for backward compatibility
          API_KEY: envVars.API_KEY || '',
          API_KEY_SECRET: envVars.API_KEY_SECRET || '',
          WDFWATCH_ACCESS_TOKEN: envVars.WDFWATCH_ACCESS_TOKEN || '',
          WDFWATCH_REFRESH_TOKEN: envVars.WDFWATCH_REFRESH_TOKEN || '',
          WDFWATCH_TOKEN_TYPE: envVars.WDFWATCH_TOKEN_TYPE || '',
          WDFWATCH_EXPIRES_IN: envVars.WDFWATCH_EXPIRES_IN || '',
          WDFWATCH_SCOPE: envVars.WDFWATCH_SCOPE || '',
        }
      };

      console.log('Executing with exec() options:', {
        shell: execOptions.shell,
        timeout: execOptions.timeout,
        maxBuffer: execOptions.maxBuffer,
        envKeys: Object.keys(execOptions.env)
      });

      // Execute the command using exec()
      const childProcess = exec(shellCommand, execOptions, (error, stdout, stderr) => {
        const timestamp = new Date().toISOString();

        if (error) {
          console.error(`[${timestamp}] [EXEC ERROR]`, error);
          console.error(`[${timestamp}] [EXEC STDERR]`, stderr);

          // Process failed
          handleProcessCompletion(episodeId, stageId, runId, error.code || 1, error.signal || null);
        } else {
          console.log(`[${timestamp}] [EXEC COMPLETE] Success`);
          if (stdout) console.log(`[${timestamp}] [EXEC STDOUT]`, stdout);
          if (stderr) console.error(`[${timestamp}] [EXEC STDERR]`, stderr);

          // Process succeeded
          handleProcessCompletion(episodeId, stageId, runId, 0, null);
        }
      });

      // Store the process reference for tracking
      taskProcess = childProcess;
      console.log('Process created with PID:', childProcess.pid);

      // Stream stdout data in real-time
      if (childProcess.stdout) {
        childProcess.stdout.on('data', (data) => {
          const timestamp = new Date().toISOString();
          console.log(`[${timestamp}] [${stageId}] stdout:`, data.toString());

          // Emit progress updates via SSE
          emitSSEEvent({
            type: 'pipeline_stage_progress',
            episodeId: episodeId.toString(),
            stage: stageId,
            runId,
            output: data.toString(),
          });
        });
      }

      // Stream stderr data in real-time
      if (childProcess.stderr) {
        childProcess.stderr.on('data', (data) => {
          const timestamp = new Date().toISOString();
          const output = data.toString();

          // Don't treat all stderr as errors - Python often uses stderr for logging
          if (output.includes('ERROR') || output.includes('CRITICAL') || output.includes('Traceback')) {
            console.error(`[${timestamp}] [${stageId}] ERROR:`, output);

            // Emit error updates via SSE
            emitSSEEvent({
              type: 'pipeline_stage_error',
              episodeId: episodeId.toString(),
              stage: stageId,
              runId,
              error: output,
            });
          } else {
            console.log(`[${timestamp}] [${stageId}] stderr (info):`, output);

            // Emit as progress since it's just logging
            emitSSEEvent({
              type: 'pipeline_stage_progress',
              episodeId: episodeId.toString(),
              stage: stageId,
              runId,
              output: output,
            });
          }
        });
      }

    } else {
      // Use legacy pipeline tasks
      const stageToTaskMap = LEGACY_STAGE_TO_TASK;
      const taskPath = join(process.cwd(), '..', stageToTaskMap[stageId]);
      
      const args = [taskPath];
      if (force) args.push('--force');
      
      // For scraping stage, add manual_trigger flag to actually call Twitter API
      // and pass episode-id to ensure we use episode-specific keywords
      if (stageId === 'scraping') {
        args.push('--manual-trigger');
        args.push('--episode-id', episodeId.toString());
        console.log('Adding manual trigger flag and episode ID for scraping stage', episodeId);
      }
      
      taskProcess = spawn(pythonPath, args, {
        cwd: join(process.cwd(), '..'),
        env: {
          ...process.env,
          WDF_WEB_MODE: 'true',
          WDF_EPISODE_ID: episodeId.toString(),
          WDF_RUN_ID: runId,
          // Strip Prisma-specific query parameters that psycopg2 doesn't understand
          DATABASE_URL: (process.env.DATABASE_URL || '').split('?')[0],
          WEB_URL: process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:8888',
        },
      });
    }
    
    // Register the process with the tracker
    const processKey = ProcessTracker.getStageKey(episodeId, stageId);
    processTracker.register(processKey, {
      process: taskProcess,
      episodeId,
      type: 'stage',
      stage: stageId,
      runId,
      startedAt: new Date(),
    });
    
    // Add immediate process state monitoring
    const processMonitor = setInterval(() => {
      console.log(`[MONITOR] Process ${taskProcess.pid} - killed: ${taskProcess.killed}, exitCode: ${taskProcess.exitCode}, signalCode: ${taskProcess.signalCode}`);
    }, 5000);

    // Log task output with timestamps
    taskProcess.stdout.on('data', (data) => {
      const timestamp = new Date().toISOString();
      console.log(`[${timestamp}] [${stageId}] stdout:`, data.toString());

      // Emit progress updates via SSE
      emitSSEEvent({
        type: 'pipeline_stage_progress',
        episodeId: episodeId.toString(),
        stage: stageId,
        runId,
        output: data.toString(),
      });
    });

    taskProcess.stderr.on('data', (data) => {
      const timestamp = new Date().toISOString();
      console.error(`[${timestamp}] [${stageId}] stderr:`, data.toString());

      // Emit error updates via SSE
      emitSSEEvent({
        type: 'pipeline_stage_error',
        episodeId: episodeId.toString(),
        stage: stageId,
        runId,
        error: data.toString(),
      });
    });

    // Handle task completion with detailed logging
    taskProcess.on('close', async (code, signal) => {
      clearInterval(processMonitor);
      const timestamp = new Date().toISOString();
      console.log(`[${timestamp}] [PROCESS CLOSE] Code: ${code}, Signal: ${signal}, PID: ${taskProcess.pid}`);
      // Unregister the process from tracker
      processTracker.unregister(processKey);
      
      const status = code === 0 ? 'completed' : 'failed';
      const completedAt = new Date();

      console.log(`[PROCESS CLOSE] Status: ${status}, Duration: ${completedAt.getTime() - new Date().getTime()}ms`);
      
      try {
        // Update pipeline run record
        const pipelineRun = await prisma.pipelineRun.findFirst({
          where: { runId },
        });
        
        if (pipelineRun) {
          const duration = completedAt.getTime() - pipelineRun.startedAt.getTime();
          
          await prisma.pipelineRun.update({
            where: { id: pipelineRun.id },
            data: {
              status,
              completedAt,
              errorMessage: code !== 0 ? `Process exited with code ${code}` : null,
              metrics: {
                duration,
                exitCode: code,
              },
            },
          });
        }
        
        // Create audit log entry
        await prisma.auditLog.create({
          data: {
            action: `pipeline_stage_${status}`,
            resourceType: 'episode',
            resourceId: episodeId,
            metadata: {
              runId,
              stage: stageId,
              exitCode: code,
            },
          },
        });
        
        // Emit SSE event for completion
        await emitSSEEvent({
          type: 'pipeline_stage_completed',
          episodeId: episodeId.toString(),
          stage: stageId,
          runId,
          status,
          exitCode: code,
        });
        
      } catch (error) {
        console.error('Failed to update pipeline run status:', error);
      }
    });

    // Also monitor for disconnect/exit events
    taskProcess.on('disconnect', () => {
      console.log(`[PROCESS] Process ${taskProcess.pid} disconnected`);
    });

    taskProcess.on('exit', (code, signal) => {
      const timestamp = new Date().toISOString();
      console.log(`[${timestamp}] [PROCESS EXIT] Code: ${code}, Signal: ${signal}, PID: ${taskProcess.pid}`);
    });

    // Log after 10 seconds if process is still running
    setTimeout(() => {
      if (!taskProcess.killed && taskProcess.exitCode === null) {
        console.log(`[10s CHECK] Process ${taskProcess.pid} still running - this is GOOD`);
      } else {
        console.log(`[10s CHECK] Process ${taskProcess.pid} already terminated - killed: ${taskProcess.killed}, exitCode: ${taskProcess.exitCode}`);
      }
    }, 10000);

    return NextResponse.json({
      message: `Started ${stageId} stage for episode ${episodeId}`,
      episodeId,
      runId,
      stage: stageId,
    });
    
  } catch (error) {
    console.error('Failed to start pipeline stage:', error);
    
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid input', details: error.errors },
        { status: 400 }
      );
    }
    
    return NextResponse.json(
      { error: 'Failed to start pipeline stage' },
      { status: 500 }
    );
  }
}

// Helper function to emit SSE events
async function emitSSEEvent(eventData: any) {
  try {
    const sseResponse = await fetch(`${process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:8888'}/api/internal/events`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': process.env.WEB_API_KEY || 'development-internal-api-key',
      },
      body: JSON.stringify(eventData),
    });
    
    if (!sseResponse.ok) {
      console.error('Failed to emit SSE event:', eventData);
    }
  } catch (error) {
    console.error('Error emitting SSE event:', error);
  }
}