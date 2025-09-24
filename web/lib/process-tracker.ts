/**
 * Pipeline Process Tracker
 * 
 * Centralized tracking and management of running pipeline processes.
 * Handles both individual stage processes and full pipeline processes.
 * Provides process termination functionality for episode deletion.
 */

import { ChildProcess } from 'child_process';

export interface ProcessInfo {
  process: ChildProcess;
  episodeId: number;
  type: 'stage' | 'full_pipeline';
  stage?: string; // Only for stage processes
  runId: string;
  startedAt: Date;
}

export class ProcessTracker {
  private processes = new Map<string, ProcessInfo>();

  /**
   * Register a running process
   */
  register(key: string, info: ProcessInfo): void {
    this.processes.set(key, info);
    console.log(`[ProcessTracker] Registered process: ${key} (type: ${info.type})`);
  }

  /**
   * Unregister a completed process
   */
  unregister(key: string): void {
    const removed = this.processes.delete(key);
    if (removed) {
      console.log(`[ProcessTracker] Unregistered process: ${key}`);
    }
  }

  /**
   * Get all running processes for an episode
   */
  getProcessesForEpisode(episodeId: number): ProcessInfo[] {
    const episodeProcesses: ProcessInfo[] = [];
    
    this.processes.forEach((info, key) => {
      if (info.episodeId === episodeId) {
        episodeProcesses.push(info);
      }
    });
    
    return episodeProcesses;
  }

  /**
   * Kill all processes for an episode
   */
  killProcessesForEpisode(episodeId: number): Promise<{ killed: number; failed: string[] }> {
    return new Promise((resolve) => {
      const episodeProcesses = this.getProcessesForEpisode(episodeId);
      
      if (episodeProcesses.length === 0) {
        console.log(`[ProcessTracker] No running processes found for episode ${episodeId}`);
        resolve({ killed: 0, failed: [] });
        return;
      }

      let killedCount = 0;
      const failedKeys: string[] = [];
      let remaining = episodeProcesses.length;

      console.log(`[ProcessTracker] Attempting to kill ${episodeProcesses.length} processes for episode ${episodeId}`);

      episodeProcesses.forEach((info) => {
        const processKey = this.findKeyForProcess(info);
        
        if (!processKey) {
          failedKeys.push(`unknown-${info.type}-${info.runId}`);
          remaining--;
          if (remaining === 0) {
            resolve({ killed: killedCount, failed: failedKeys });
          }
          return;
        }

        try {
          // Try graceful termination first (SIGTERM)
          info.process.kill('SIGTERM');
          
          // Force kill after 5 seconds if still running
          const forceKillTimeout = setTimeout(() => {
            if (!info.process.killed) {
              console.log(`[ProcessTracker] Force killing process: ${processKey}`);
              info.process.kill('SIGKILL');
            }
          }, 5000);

          // Handle process exit
          info.process.on('exit', (code, signal) => {
            clearTimeout(forceKillTimeout);
            console.log(`[ProcessTracker] Process ${processKey} exited with code ${code}, signal ${signal}`);
            
            this.unregister(processKey);
            killedCount++;
            remaining--;
            
            if (remaining === 0) {
              resolve({ killed: killedCount, failed: failedKeys });
            }
          });

          // Handle kill errors
          info.process.on('error', (error) => {
            clearTimeout(forceKillTimeout);
            console.error(`[ProcessTracker] Error killing process ${processKey}:`, error);
            
            failedKeys.push(processKey);
            remaining--;
            
            if (remaining === 0) {
              resolve({ killed: killedCount, failed: failedKeys });
            }
          });

        } catch (error) {
          console.error(`[ProcessTracker] Failed to kill process ${processKey}:`, error);
          failedKeys.push(processKey);
          remaining--;
          
          if (remaining === 0) {
            resolve({ killed: killedCount, failed: failedKeys });
          }
        }
      });
    });
  }

  /**
   * Check if a specific stage is running for an episode
   */
  isStageRunning(episodeId: number, stage: string): boolean {
    const key = `${episodeId}-${stage}`;
    return this.processes.has(key);
  }

  /**
   * Check if the full pipeline is running for an episode
   */
  isFullPipelineRunning(episodeId: number): boolean {
    let isRunning = false;
    this.processes.forEach((info) => {
      if (info.episodeId === episodeId && info.type === 'full_pipeline') {
        isRunning = true;
      }
    });
    return isRunning;
  }

  /**
   * Get all running processes (for debugging)
   */
  getAllProcesses(): Map<string, ProcessInfo> {
    return new Map(this.processes);
  }

  /**
   * Find the key for a given process info (internal helper)
   */
  private findKeyForProcess(targetInfo: ProcessInfo): string | null {
    let foundKey: string | null = null;
    this.processes.forEach((info, key) => {
      if (info === targetInfo) {
        foundKey = key;
      }
    });
    return foundKey;
  }

  /**
   * Generate key for stage process
   */
  static getStageKey(episodeId: number, stage: string): string {
    return `${episodeId}-${stage}`;
  }

  /**
   * Generate key for full pipeline process
   */
  static getFullPipelineKey(episodeId: number, runId: string): string {
    return `${episodeId}-full-${runId}`;
  }
}

// Export singleton instance
export const processTracker = new ProcessTracker();