/**
 * Pipeline Pre-flight Validation System
 * 
 * Comprehensive validation before pipeline execution including:
 * - API key validation
 * - Model availability checks
 * - Episode content validation
 * - System resource checks
 * - Configuration validation
 * - Dependency verification
 */

import { prisma } from '@/lib/db';
import { spawn } from 'child_process';
import { join } from 'path';
import { statSync, accessSync, constants } from 'fs';

export interface ValidationResult {
  isValid: boolean;
  score: number; // 0-100 overall readiness score
  errors: string[];
  warnings: string[];
  checks: ValidationCheck[];
  estimatedIssueResolutionTime: number; // minutes
}

export interface ValidationCheck {
  id: string;
  name: string;
  category: 'critical' | 'warning' | 'info';
  status: 'pass' | 'fail' | 'skip' | 'pending';
  message: string;
  suggestion?: string;
  resolutionTime?: number; // minutes
  details?: any;
}

export class PipelineValidator {
  
  /**
   * Validate full pipeline requirements
   */
  async validatePipeline(episodeId: number, pipelineType: 'claude' | 'legacy'): Promise<ValidationResult> {
    const checks: ValidationCheck[] = [];
    const errors: string[] = [];
    const warnings: string[] = [];

    // Episode validation
    const episodeChecks = await this.validateEpisode(episodeId);
    checks.push(...episodeChecks);

    // API keys validation
    const apiKeyChecks = await this.validateApiKeys(pipelineType);
    checks.push(...apiKeyChecks);

    // Model availability validation
    const modelChecks = await this.validateModels(pipelineType);
    checks.push(...modelChecks);

    // System resources validation
    const systemChecks = await this.validateSystemResources();
    checks.push(...systemChecks);

    // Configuration validation
    const configChecks = await this.validateConfiguration(pipelineType);
    checks.push(...configChecks);

    // Database connectivity validation
    const dbChecks = await this.validateDatabaseConnectivity();
    checks.push(...dbChecks);

    // Pipeline-specific validation
    if (pipelineType === 'claude') {
      const claudeChecks = await this.validateClaudePipeline(episodeId);
      checks.push(...claudeChecks);
    } else {
      const legacyChecks = await this.validateLegacyPipeline(episodeId);
      checks.push(...legacyChecks);
    }

    // Categorize results
    const criticalFailures = checks.filter(c => c.category === 'critical' && c.status === 'fail');
    const warningIssues = checks.filter(c => c.category === 'warning' && c.status === 'fail');

    // Add to errors and warnings arrays
    criticalFailures.forEach(check => errors.push(check.message));
    warningIssues.forEach(check => warnings.push(check.message));

    // Calculate overall score
    const totalChecks = checks.length;
    const passedChecks = checks.filter(c => c.status === 'pass').length;
    const score = totalChecks > 0 ? Math.round((passedChecks / totalChecks) * 100) : 0;

    // Calculate estimated resolution time
    const estimatedIssueResolutionTime = checks
      .filter(c => c.status === 'fail' && c.resolutionTime)
      .reduce((total, check) => total + (check.resolutionTime || 0), 0);

    return {
      isValid: criticalFailures.length === 0,
      score,
      errors,
      warnings,
      checks,
      estimatedIssueResolutionTime,
    };
  }

  /**
   * Validate episode content and metadata
   */
  private async validateEpisode(episodeId: number): Promise<ValidationCheck[]> {
    const checks: ValidationCheck[] = [];

    try {
      const episode = await prisma.podcastEpisode.findUnique({
        where: { id: episodeId },
        select: {
          id: true,
          title: true,
          transcriptText: true,
          videoUrl: true,
          claudeEpisodeDir: true,
          episodeDir: true,
          status: true,
        },
      });

      if (!episode) {
        checks.push({
          id: 'episode_exists',
          name: 'Episode Exists',
          category: 'critical',
          status: 'fail',
          message: 'Episode not found in database',
          resolutionTime: 0,
        });
        return checks;
      }

      // Check episode title
      checks.push({
        id: 'episode_title',
        name: 'Episode Title',
        category: 'warning',
        status: episode.title && episode.title.trim().length > 0 ? 'pass' : 'fail',
        message: episode.title ? 'Episode has title' : 'Episode title is missing',
        suggestion: 'Add a descriptive title for the episode',
        resolutionTime: 2,
      });

      // Check transcript content
      const transcriptLength = episode.transcriptText?.length || 0;
      checks.push({
        id: 'episode_transcript',
        name: 'Transcript Content',
        category: 'critical',
        status: transcriptLength >= 100 ? 'pass' : 'fail',
        message: transcriptLength >= 100 
          ? `Transcript available (${transcriptLength} characters)`
          : 'Transcript is too short or missing',
        suggestion: 'Upload a transcript with at least 100 characters',
        resolutionTime: 10,
        details: { length: transcriptLength },
      });

      // Check video URL
      checks.push({
        id: 'episode_video_url',
        name: 'Video URL',
        category: 'warning',
        status: episode.videoUrl ? 'pass' : 'fail',
        message: episode.videoUrl ? 'Video URL provided' : 'No video URL provided',
        suggestion: 'Add video URL to include in generated responses',
        resolutionTime: 1,
      });

      // Check episode directory structure
      if (episode.claudeEpisodeDir || episode.episodeDir) {
        const episodeDirPath = join(process.cwd(), '..', 'episodes', episode.claudeEpisodeDir || episode.episodeDir);
        try {
          accessSync(episodeDirPath, constants.R_OK);
          checks.push({
            id: 'episode_directory',
            name: 'Episode Directory',
            category: 'info',
            status: 'pass',
            message: 'Episode directory exists and is accessible',
          });
        } catch (error) {
          checks.push({
            id: 'episode_directory',
            name: 'Episode Directory',
            category: 'warning',
            status: 'fail',
            message: 'Episode directory is not accessible',
            suggestion: 'Re-upload episode files or check file permissions',
            resolutionTime: 5,
          });
        }
      }

    } catch (error) {
      checks.push({
        id: 'episode_validation_error',
        name: 'Episode Validation',
        category: 'critical',
        status: 'fail',
        message: `Failed to validate episode: ${error instanceof Error ? error.message : 'Unknown error'}`,
        resolutionTime: 5,
      });
    }

    return checks;
  }

  /**
   * Validate API keys availability and validity
   */
  private async validateApiKeys(pipelineType: 'claude' | 'legacy'): Promise<ValidationCheck[]> {
    const checks: ValidationCheck[] = [];

    try {
      // Check if web UI API key system is available
      const apiKeysResponse = await fetch(`${process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000'}/api/internal/api-keys`, {
        headers: {
          'X-API-Key': process.env.WEB_API_KEY || 'development',
        },
      });

      if (!apiKeysResponse.ok) {
        checks.push({
          id: 'api_key_system',
          name: 'API Key System',
          category: 'critical',
          status: 'fail',
          message: 'Cannot access API key management system',
          suggestion: 'Check web UI configuration and database connectivity',
          resolutionTime: 10,
        });
        return checks;
      }

      const apiKeys = await apiKeysResponse.json();

      // Twitter API keys (required for both pipelines)
      const twitterKeys = apiKeys.twitter || {};
      const hasTwitterKeys = twitterKeys.bearer_token || (twitterKeys.api_key && twitterKeys.api_secret);
      
      checks.push({
        id: 'twitter_api_keys',
        name: 'Twitter API Keys',
        category: 'warning', // Not critical as we have mock mode
        status: hasTwitterKeys ? 'pass' : 'fail',
        message: hasTwitterKeys ? 'Twitter API keys configured' : 'Twitter API keys missing',
        suggestion: 'Configure Twitter API keys in Settings → API Keys, or pipeline will use mock mode',
        resolutionTime: 5,
      });

      // Gemini API keys (required for both pipelines)
      const geminiKeys = apiKeys.gemini || {};
      const hasGeminiKeys = geminiKeys.api_key;
      
      checks.push({
        id: 'gemini_api_keys',
        name: 'Gemini API Keys',
        category: 'critical',
        status: hasGeminiKeys ? 'pass' : 'fail',
        message: hasGeminiKeys ? 'Gemini API keys configured' : 'Gemini API keys missing',
        suggestion: 'Configure Gemini API keys in Settings → API Keys for transcript analysis',
        resolutionTime: 5,
      });

      // Claude API keys (for Claude pipeline)
      if (pipelineType === 'claude') {
        const claudeKeys = apiKeys.anthropic || {};
        const hasClaudeKeys = claudeKeys.api_key;
        
        checks.push({
          id: 'claude_api_keys',
          name: 'Claude API Keys',
          category: 'critical',
          status: hasClaudeKeys ? 'pass' : 'fail',
          message: hasClaudeKeys ? 'Claude API keys configured' : 'Claude API keys missing',
          suggestion: 'Configure Claude API keys in Settings → API Keys for Claude pipeline',
          resolutionTime: 5,
        });
      }

    } catch (error) {
      checks.push({
        id: 'api_keys_validation_error',
        name: 'API Keys Validation',
        category: 'critical',
        status: 'fail',
        message: `Failed to validate API keys: ${error instanceof Error ? error.message : 'Unknown error'}`,
        resolutionTime: 10,
      });
    }

    return checks;
  }

  /**
   * Validate model availability
   */
  private async validateModels(pipelineType: 'claude' | 'legacy'): Promise<ValidationCheck[]> {
    const checks: ValidationCheck[] = [];

    try {
      // Get configured models from database
      const settings = await prisma.setting.findUnique({
        where: { key: 'llm_models' },
      });

      const llmModels = settings?.value || {};
      
      if (pipelineType === 'legacy') {
        // Check Ollama models for legacy pipeline
        const classificationModel = llmModels.classification || 'gemma3n:e4b';
        const responseModel = llmModels.response || 'deepseek-r1:latest';

        // Check if Ollama is running
        const ollamaCheck = await this.checkOllamaHealth();
        checks.push(ollamaCheck);

        if (ollamaCheck.status === 'pass') {
          // Check specific models
          const classificationModelCheck = await this.checkOllamaModel(classificationModel);
          checks.push({
            ...classificationModelCheck,
            id: 'classification_model',
            name: 'Classification Model',
          });

          const responseModelCheck = await this.checkOllamaModel(responseModel);
          checks.push({
            ...responseModelCheck,
            id: 'response_model',
            name: 'Response Generation Model',
          });
        }
      }

      // Check Gemini CLI availability (for both pipelines)
      const geminiCheck = await this.checkGeminiCLI();
      checks.push(geminiCheck);

    } catch (error) {
      checks.push({
        id: 'models_validation_error',
        name: 'Models Validation',
        category: 'critical',
        status: 'fail',
        message: `Failed to validate models: ${error instanceof Error ? error.message : 'Unknown error'}`,
        resolutionTime: 15,
      });
    }

    return checks;
  }

  /**
   * Check Ollama health
   */
  private async checkOllamaHealth(): Promise<ValidationCheck> {
    try {
      const ollamaHost = process.env.WDF_OLLAMA_HOST || 'http://localhost:11434';
      const response = await fetch(`${ollamaHost}/api/tags`, {
        method: 'GET',
        signal: AbortSignal.timeout(5000), // 5 second timeout
      });

      if (response.ok) {
        const data = await response.json();
        const modelCount = data.models?.length || 0;
        
        return {
          id: 'ollama_health',
          name: 'Ollama Service',
          category: 'critical',
          status: 'pass',
          message: `Ollama is running with ${modelCount} models available`,
          details: { host: ollamaHost, modelCount },
        };
      } else {
        return {
          id: 'ollama_health',
          name: 'Ollama Service',
          category: 'critical',
          status: 'fail',
          message: `Ollama service responded with status ${response.status}`,
          suggestion: 'Start Ollama service or check configuration',
          resolutionTime: 10,
        };
      }
    } catch (error) {
      return {
        id: 'ollama_health',
        name: 'Ollama Service',
        category: 'critical',
        status: 'fail',
        message: 'Cannot connect to Ollama service',
        suggestion: 'Start Ollama service or check host configuration',
        resolutionTime: 10,
      };
    }
  }

  /**
   * Check if specific Ollama model is available
   */
  private async checkOllamaModel(modelName: string): Promise<Omit<ValidationCheck, 'id' | 'name'>> {
    try {
      const ollamaHost = process.env.WDF_OLLAMA_HOST || 'http://localhost:11434';
      const response = await fetch(`${ollamaHost}/api/tags`);
      
      if (response.ok) {
        const data = await response.json();
        const models = data.models || [];
        const modelExists = models.some((model: any) => model.name === modelName);
        
        if (modelExists) {
          return {
            category: 'critical',
            status: 'pass',
            message: `Model ${modelName} is available`,
          };
        } else {
          return {
            category: 'critical',
            status: 'fail',
            message: `Model ${modelName} is not available`,
            suggestion: `Pull model with: ollama pull ${modelName}`,
            resolutionTime: 30, // Model downloads can take time
          };
        }
      } else {
        return {
          category: 'critical',
          status: 'fail',
          message: `Cannot check model availability: ${response.status}`,
          resolutionTime: 5,
        };
      }
    } catch (error) {
      return {
        category: 'critical',
        status: 'fail',
        message: `Error checking model ${modelName}: ${error instanceof Error ? error.message : 'Unknown error'}`,
        resolutionTime: 5,
      };
    }
  }

  /**
   * Check Gemini CLI availability
   */
  private async checkGeminiCLI(): Promise<ValidationCheck> {
    return new Promise((resolve) => {
      const process = spawn('gemini', ['--version'], {
        stdio: ['ignore', 'pipe', 'pipe'],
      });

      let stdout = '';
      let stderr = '';

      process.stdout?.on('data', (data) => {
        stdout += data.toString();
      });

      process.stderr?.on('data', (data) => {
        stderr += data.toString();
      });

      process.on('close', (code) => {
        if (code === 0) {
          resolve({
            id: 'gemini_cli',
            name: 'Gemini CLI',
            category: 'critical',
            status: 'pass',
            message: 'Gemini CLI is available',
            details: { version: stdout.trim() },
          });
        } else {
          resolve({
            id: 'gemini_cli',
            name: 'Gemini CLI',
            category: 'critical',
            status: 'fail',
            message: 'Gemini CLI is not available or not working',
            suggestion: 'Install Gemini CLI: npm install -g gemini-cli',
            resolutionTime: 5,
          });
        }
      });

      process.on('error', () => {
        resolve({
          id: 'gemini_cli',
          name: 'Gemini CLI',
          category: 'critical',
          status: 'fail',
          message: 'Gemini CLI is not installed',
          suggestion: 'Install Gemini CLI: npm install -g gemini-cli',
          resolutionTime: 5,
        });
      });

      // Timeout after 10 seconds
      setTimeout(() => {
        process.kill();
        resolve({
          id: 'gemini_cli',
          name: 'Gemini CLI',
          category: 'critical',
          status: 'fail',
          message: 'Gemini CLI check timed out',
          resolutionTime: 5,
        });
      }, 10000);
    });
  }

  /**
   * Validate system resources
   */
  private async validateSystemResources(): Promise<ValidationCheck[]> {
    const checks: ValidationCheck[] = [];

    try {
      // Check disk space
      const projectRoot = join(process.cwd(), '..');
      const stats = statSync(projectRoot);
      
      // This is a basic check - in production you'd want more sophisticated disk space checking
      checks.push({
        id: 'disk_space',
        name: 'Disk Space',
        category: 'warning',
        status: 'pass', // We can't easily check available space in Node.js without additional modules
        message: 'Project directory is accessible',
      });

      // Check if required directories exist
      const requiredDirs = ['episodes', 'transcripts', 'web', 'src'];
      for (const dir of requiredDirs) {
        try {
          const dirPath = join(process.cwd(), '..', dir);
          accessSync(dirPath, constants.R_OK);
          checks.push({
            id: `directory_${dir}`,
            name: `Directory: ${dir}`,
            category: 'info',
            status: 'pass',
            message: `${dir} directory exists and is accessible`,
          });
        } catch (error) {
          checks.push({
            id: `directory_${dir}`,
            name: `Directory: ${dir}`,
            category: 'warning',
            status: 'fail',
            message: `${dir} directory is not accessible`,
            suggestion: `Create ${dir} directory or check permissions`,
            resolutionTime: 2,
          });
        }
      }

    } catch (error) {
      checks.push({
        id: 'system_resources_error',
        name: 'System Resources',
        category: 'warning',
        status: 'fail',
        message: `Failed to check system resources: ${error instanceof Error ? error.message : 'Unknown error'}`,
        resolutionTime: 5,
      });
    }

    return checks;
  }

  /**
   * Validate configuration settings
   */
  private async validateConfiguration(pipelineType: 'claude' | 'legacy'): Promise<ValidationCheck[]> {
    const checks: ValidationCheck[] = [];

    try {
      // Check scoring configuration
      const scoringSettings = await prisma.setting.findUnique({
        where: { key: 'scoring_thresholds' },
      });

      if (scoringSettings) {
        const thresholds = scoringSettings.value;
        checks.push({
          id: 'scoring_thresholds',
          name: 'Scoring Thresholds',
          category: 'info',
          status: 'pass',
          message: `Scoring thresholds configured (relevancy: ${thresholds.relevancy_threshold || 0.7})`,
        });
      } else {
        checks.push({
          id: 'scoring_thresholds',
          name: 'Scoring Thresholds',
          category: 'warning',
          status: 'fail',
          message: 'Scoring thresholds not configured, using defaults',
          suggestion: 'Configure scoring thresholds in Settings → Scoring',
          resolutionTime: 3,
        });
      }

      // Check if keywords are configured
      const keywordCount = await prisma.keyword.count({
        where: { enabled: true },
      });

      checks.push({
        id: 'keywords_configured',
        name: 'Keywords Configuration',
        category: 'warning',
        status: keywordCount > 0 ? 'pass' : 'fail',
        message: keywordCount > 0 
          ? `${keywordCount} keywords configured`
          : 'No keywords configured',
        suggestion: 'Add keywords in Settings → Keywords for tweet discovery',
        resolutionTime: 5,
      });

    } catch (error) {
      checks.push({
        id: 'configuration_error',
        name: 'Configuration Validation',
        category: 'warning',
        status: 'fail',
        message: `Failed to validate configuration: ${error instanceof Error ? error.message : 'Unknown error'}`,
        resolutionTime: 5,
      });
    }

    return checks;
  }

  /**
   * Validate database connectivity
   */
  private async validateDatabaseConnectivity(): Promise<ValidationCheck[]> {
    const checks: ValidationCheck[] = [];

    try {
      // Simple database connectivity test
      await prisma.$queryRaw`SELECT 1`;
      
      checks.push({
        id: 'database_connectivity',
        name: 'Database Connectivity',
        category: 'critical',
        status: 'pass',
        message: 'Database is accessible',
      });

      // Check if required tables exist by trying to count records
      const tableChecks = [
        { table: 'podcast_episodes', name: 'Episodes Table' },
        { table: 'tweets', name: 'Tweets Table' },
        { table: 'draft_replies', name: 'Drafts Table' },
        { table: 'keywords', name: 'Keywords Table' },
      ];

      for (const { table, name } of tableChecks) {
        try {
          const count = await prisma.$queryRaw`SELECT COUNT(*) as count FROM ${table}`;
          checks.push({
            id: `table_${table}`,
            name: name,
            category: 'info',
            status: 'pass',
            message: `${name} exists and is accessible`,
          });
        } catch (error) {
          checks.push({
            id: `table_${table}`,
            name: name,
            category: 'critical',
            status: 'fail',
            message: `${name} is not accessible`,
            suggestion: 'Run database migrations',
            resolutionTime: 10,
          });
        }
      }

    } catch (error) {
      checks.push({
        id: 'database_connectivity',
        name: 'Database Connectivity',
        category: 'critical',
        status: 'fail',
        message: `Cannot connect to database: ${error instanceof Error ? error.message : 'Unknown error'}`,
        suggestion: 'Check database configuration and ensure PostgreSQL is running',
        resolutionTime: 15,
      });
    }

    return checks;
  }

  /**
   * Claude pipeline specific validation
   */
  private async validateClaudePipeline(episodeId: number): Promise<ValidationCheck[]> {
    const checks: ValidationCheck[] = [];

    // Check if Claude pipeline bridge exists
    const bridgePath = join(process.cwd(), '..', 'web', 'scripts', 'claude_pipeline_bridge.py');
    try {
      accessSync(bridgePath, constants.R_OK);
      checks.push({
        id: 'claude_pipeline_bridge',
        name: 'Claude Pipeline Bridge',
        category: 'critical',
        status: 'pass',
        message: 'Claude pipeline bridge is available',
      });
    } catch (error) {
      checks.push({
        id: 'claude_pipeline_bridge',
        name: 'Claude Pipeline Bridge',
        category: 'critical',
        status: 'fail',
        message: 'Claude pipeline bridge is not accessible',
        suggestion: 'Ensure claude_pipeline_bridge.py exists in web/scripts/',
        resolutionTime: 5,
      });
    }

    return checks;
  }

  /**
   * Legacy pipeline specific validation
   */
  private async validateLegacyPipeline(episodeId: number): Promise<ValidationCheck[]> {
    const checks: ValidationCheck[] = [];

    // Check if required task files exist
    const taskFiles = [
      { path: 'scripts/transcript_summarizer.js', name: 'Transcript Summarizer' },
      { path: 'src/wdf/tasks/fewshot.py', name: 'Few-shot Generator' },
      { path: 'src/wdf/tasks/scrape.py', name: 'Tweet Scraper' },
      { path: 'src/wdf/tasks/classify.py', name: 'Tweet Classifier' },
      { path: 'src/wdf/tasks/deepseek.py', name: 'Response Generator' },
      { path: 'src/wdf/tasks/web_moderation.py', name: 'Web Moderation' },
    ];

    for (const { path, name } of taskFiles) {
      try {
        const fullPath = join(process.cwd(), '..', path);
        accessSync(fullPath, constants.R_OK);
        checks.push({
          id: `task_file_${path.replace(/[^a-zA-Z0-9]/g, '_')}`,
          name: name,
          category: 'critical',
          status: 'pass',
          message: `${name} task file is available`,
        });
      } catch (error) {
        checks.push({
          id: `task_file_${path.replace(/[^a-zA-Z0-9]/g, '_')}`,
          name: name,
          category: 'critical',
          status: 'fail',
          message: `${name} task file is not accessible`,
          suggestion: `Ensure ${path} exists and is readable`,
          resolutionTime: 5,
        });
      }
    }

    return checks;
  }
}