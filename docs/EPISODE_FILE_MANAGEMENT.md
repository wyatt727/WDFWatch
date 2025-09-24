# Episode-Based File Management System

This document describes the comprehensive file management system that organizes all pipeline files by episode, ensuring data isolation and easy management.

## Overview

The episode-based file management system provides:
- **Isolated file storage** per episode
- **Visual pipeline management** through the web UI
- **File preview and upload** capabilities
- **Automatic dependency tracking** between pipeline stages
- **Smart caching** to avoid redundant processing
- **Backward compatibility** with legacy file paths

## Architecture

### File Organization

Each episode has its own directory structure:

```
/episodes/
  /20250120-ep123-federal-overreach/
    /inputs/
      transcript.txt         # Uploaded transcript
      podcast_overview.txt   # General podcast description
      video_url.txt         # YouTube URL for episode
    /outputs/
      summary.md            # Generated summary
      keywords.json         # Extracted keywords
      fewshots.json         # Classification examples
      tweets.json           # Scraped tweets
      classified.json       # Classification results
      responses.json        # Generated responses
      published.json        # Approved responses
    /cache/
      summary.hash          # Hash for change detection
      fewshots.hash         # Hash for change detection
    pipeline-config.json    # File mapping configuration
```

### Database Schema

```typescript
interface FileConfig {
  episodeDir: string
  files: {
    transcript: string      // "inputs/transcript.txt"
    overview: string        // "inputs/podcast_overview.txt"
    videoUrl: string        // "inputs/video_url.txt"
    summary: string         // "outputs/summary.md"
    keywords: string        // "outputs/keywords.json"
    fewshots: string        // "outputs/fewshots.json"
    tweets: string          // "outputs/tweets.json"
    classified: string      // "outputs/classified.json"
    responses: string       // "outputs/responses.json"
    published: string       // "outputs/published.json"
  }
}

interface PipelineState {
  stages: {
    [stageId: string]: {
      status: 'pending' | 'running' | 'completed' | 'skipped' | 'error'
      lastRun?: string
      outputHash?: string
      error?: string
      duration?: number
    }
  }
  currentStage?: string
  startedAt?: string
  completedAt?: string
}
```

## Web UI Features

### Pipeline Visualizer

The pipeline visualizer (`/episodes/[id]`) provides:

1. **Visual Pipeline Flow**
   - Shows all stages with status indicators
   - Color-coded states (pending, running, completed, error)
   - Progress bars for running stages

2. **File Management**
   - Preview any file with syntax highlighting
   - Upload replacement files
   - Download generated outputs
   - See file sizes and modification times

3. **Stage Controls**
   - Run individual stages
   - Skip optional stages
   - Use cached outputs when available
   - Reset stages to re-run

4. **Smart Dependency Tracking**
   - Automatically determines which stages can run
   - Shows which files are required for each stage
   - Cascading reset when upstream stages change

### File Preview Dialog

- Syntax-highlighted preview for JSON/Markdown
- Full content viewing with scrolling
- Copy to clipboard functionality
- Download as file

### File Upload Dialog

- Drag-and-drop or click to upload
- File type validation
- Size limit enforcement
- Warning about downstream effects

## Python Integration

### Episode File Manager

```python
from src.wdf.episode_files import EpisodeFileManager

# Initialize for specific episode
fm = EpisodeFileManager(episode_id=123)

# Read input files
transcript = fm.read_input('transcript')
overview = fm.read_input('overview')

# Write output files
fm.write_output('summary', summary_text)
fm.write_output('keywords', keywords_list)

# Check file existence
if fm.file_exists('tweets'):
    tweets = json.loads(fm.read_input('tweets'))

# Get file paths
summary_path = fm.get_output_path('summary')

# List all files with status
files = fm.list_files()
# Returns: {'transcript': {'exists': True, 'size': 1024, ...}}
```

### Pipeline Task Updates

All pipeline tasks support episode-based files:

```python
# In any task file
def run(run_id=None, episode_id=None):
    # Automatic episode file management
    if episode_id or os.environ.get('WDF_EPISODE_ID'):
        fm = get_episode_file_manager(episode_id)
        
        # Read from episode directory
        summary = fm.read_input('summary')
        
        # Write to episode directory
        fm.write_output('responses', responses)
    else:
        # Fall back to legacy paths
        summary = Path('transcripts/summary.md').read_text()
```

### Environment Variables

When running in web mode, these are automatically set:
- `WDF_EPISODE_ID` - Current episode ID
- `WDF_EPISODE_DIR` - Episode directory path
- `WDF_USE_CACHED` - Whether to use cached outputs

## API Endpoints

### File Management

```typescript
// List all files for an episode
GET /api/episodes/[id]/files
Response: {
  episodeDir: string
  files: Record<string, FileReference>
  pipelineState: PipelineState
}

// Preview file content
POST /api/episodes/[id]/files/preview
Body: { fileKey: string }
Response: {
  content: string
  size: number
  lastModified: string
  mimeType: string
}

// Upload replacement file
POST /api/episodes/[id]/files/upload
Body: FormData { file: File, fileKey: string }
Response: {
  success: boolean
  affectedStages: string[]
}

// Reset pipeline stage
POST /api/episodes/[id]/files/reset
Body: { stageId: string }
Response: {
  deletedFiles: string[]
  affectedStages: string[]
}
```

### Pipeline Execution

```typescript
// Run pipeline stage
POST /api/episodes/[id]/pipeline/run
Body: { stageId: string, useCached?: boolean }
Response: {
  runId: string
  stageId: string
  message: string
}
```

## Usage Examples

### Creating a New Episode

1. Upload transcript via Episodes page
2. System automatically:
   - Creates episode directory
   - Initializes file structure
   - Copies global files (overview, video URL)
   - Sets status to "transcript_uploaded"

### Running the Pipeline

1. Navigate to episode detail page
2. Pipeline visualizer shows current state
3. Click "Run" on summarization stage
4. System executes with progress updates
5. Output files appear when complete
6. Continue with next stages

### Updating Files

1. Click upload icon next to any input file
2. Select replacement file
3. System warns about affected stages
4. Dependent stages reset automatically
5. Re-run affected stages as needed

### Using Cached Outputs

When a stage shows "Use Cached":
1. Previous outputs still valid
2. No inputs have changed
3. Click to reuse without reprocessing
4. Saves time and resources

## Best Practices

### File Naming

- Use descriptive episode directories
- Include date for chronological sorting
- Limit special characters in titles

### Pipeline Management

1. **Check Dependencies**: Ensure input files exist before running
2. **Use Caching**: Avoid re-running unchanged stages
3. **Monitor Progress**: Watch for errors in running stages
4. **Clean Outputs**: Reset stages when testing changes

### Error Handling

- Failed stages show error messages
- Check file permissions if uploads fail
- Verify file formats match expectations
- Use preview to validate content

## Migration from Legacy System

### Automatic Fallback

The system maintains backward compatibility:
1. Checks episode directory first
2. Falls back to `transcripts/` if not found
3. Copies legacy files on first access

### Manual Migration

```python
# Migration script for existing episodes
from src.wdf.episode_files import EpisodeFileManager

# For each existing episode
fm = EpisodeFileManager(episode_id)

# Copy legacy files
fm.copy_from_legacy('transcript')
fm.copy_from_legacy('summary')
fm.copy_from_legacy('keywords')
# etc...
```

## Troubleshooting

### Common Issues

1. **"File not found" errors**
   - Check episode directory exists
   - Verify file was uploaded
   - Check file permissions

2. **"Cannot run stage" message**
   - Missing required input files
   - Upload missing files first
   - Check previous stages completed

3. **Slow file operations**
   - Large files take time to preview
   - Consider chunked uploads for huge files
   - Check disk space availability

### Debug Information

Enable debug logging:
```bash
export WDF_DEBUG=true
export EPISODES_DIR=/custom/path  # Override default location
```

View episode file structure:
```bash
tree episodes/20250120-ep123-*
```

## Security Considerations

- File uploads validated for type and size
- Path traversal prevented in file operations
- Audit logs track all file changes
- Backups created before file replacements

## Future Enhancements

1. **Batch Operations**
   - Run entire pipeline with one click
   - Bulk file uploads
   - Multi-episode processing

2. **Advanced Caching**
   - Content-based cache invalidation
   - Partial stage re-runs
   - Cache statistics dashboard

3. **File Versioning**
   - Track file history
   - Diff viewer for changes
   - Rollback capabilities

4. **Cloud Storage**
   - S3/GCS backend option
   - CDN for large files
   - Distributed processing