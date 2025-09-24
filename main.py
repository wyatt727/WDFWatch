#!/Users/pentester/Tools/gemma-3n/venv/bin/python3
"""
Main pipeline orchestrator for WDF tweet-engagement workflow.
Run `python main.py --help` for options.
"""

import argparse
import datetime
import json
import logging
import os
import subprocess
import sys
import time
import threading
from pathlib import Path

import structlog
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from prometheus_client import start_http_server, Histogram

# Create logs directory
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

# Stage timing log
STAGE_LOG = LOGS_DIR / "stage_times.json"

# Hash files for caching
SUMMARY_HASH_FILE = Path("transcripts/summary.hash")
FEWSHOTS_HASH_FILE = Path("transcripts/fewshots.hash")

# Rich console for pretty output
console = Console()

# Prometheus metrics
PROCESSING_LATENCY = Histogram(
    "processing_latency_seconds",
    "End-to-end processing latency for pipeline stages",
    ["stage", "run_id"],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600]
)

# Track files and workers for each stage
PIPELINE_INFO = {
    "gemini_summarize": {
        "input_files": ["transcripts/latest.txt", "transcripts/podcast_overview.txt", "transcripts/VIDEO_URL.txt"],
        "output_files": ["transcripts/summary.md", "transcripts/summary.hash"],
        "workers": None,
        "description": "Generates summary using Gemini API",
        "model": "gemini-2.5-pro"
    },
    "fewshot_generation": {
        "input_files": ["transcripts/summary.md"],
        "output_files": ["transcripts/fewshots.json", "transcripts/fewshots.hash"],
        "workers": None,
        "description": "Generates few-shot examples for classification",
        "model": "gemini-2.5-pro"
    },
    "twitter_scrape": {
        "input_files": ["transcripts/keywords.json"],
        "output_files": ["transcripts/tweets.json"],
        "workers": None,
        "description": "Scrapes Twitter for relevant tweets"
    },
    "tweet_classification": {
        "input_files": ["transcripts/tweets.json", "transcripts/fewshots.json", "transcripts/summary.md"],
        "output_files": ["transcripts/classified.json", "transcripts/relevant_tweets.json"],
        "workers": 8,  # Default from tweet_classifier.py
        "description": "Classifies tweets using configured classification model",
        "model": "gemma3n:e4b"
    },
    "deepseek_responses": {
        "input_files": [
            "transcripts/relevant_tweets.json",
            "transcripts/summary.md",
            "transcripts/podcast_overview.txt",
            "transcripts/VIDEO_URL.txt"
        ],
        "output_files": ["transcripts/responses.json"],
        "workers": 1,  # Updated to single worker mode for better performance
        "description": "Generates responses using DeepSeek model",
        "model": "deepseek-r1:latest"
    },
    "moderation_queue": {
        "input_files": ["transcripts/responses.json"],
        "output_files": ["transcripts/published.json"],
        "workers": None,
        "description": "Interactive moderation of responses"
    }
}


def _timeit(label: str, callable_or_cmd, run_id: str = "unknown"):
    """Run callable_or_cmd, time it, and persist timing metadata."""
    stage_info = PIPELINE_INFO.get(label, {"input_files": [], "output_files": [], "workers": None, "description": "Unknown stage"})
    
    # Display stage information
    console.print(f"[bold cyan]Running:[/bold cyan] {label}")
    console.print(f"[cyan]Description:[/cyan] {stage_info['description']}")
    console.print(f"[cyan]Input files:[/cyan] {', '.join(stage_info['input_files']) or 'None'}")
    console.print(f"[cyan]Output files:[/cyan] {', '.join(stage_info['output_files']) or 'None'}")
    if stage_info['workers'] is not None:
        console.print(f"[cyan]Workers:[/cyan] {stage_info['workers']}")
    if 'model' in stage_info:
        console.print(f"[cyan]Model:[/cyan] {stage_info['model']}")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(f"Running {label}...", total=None)
        
        t0 = time.perf_counter()
        
        try:
            if callable(callable_or_cmd):
                result = callable_or_cmd()
            else:  # assume list/tuple -> subprocess
                result = subprocess.run(
                    callable_or_cmd,
                    check=True,
                    capture_output=True,
                    text=True
                )
                
            elapsed = time.perf_counter() - t0
            progress.update(task, completed=100)
            
            console.print(f"[bold green]✓[/bold green] {label} finished in [bold]{elapsed:.2f}s[/bold]")
            
            # Check if output files exist and display their sizes
            if label in PIPELINE_INFO and PIPELINE_INFO[label]["output_files"]:
                file_table = Table(title="Output Files", show_header=True, header_style="bold magenta")
                file_table.add_column("File", style="dim")
                file_table.add_column("Size", justify="right", style="green")
                file_table.add_column("Status", justify="center", style="cyan")
                file_table.add_column("Last Modified", style="yellow")
                
                for outfile in PIPELINE_INFO[label]["output_files"]:
                    path = Path(outfile)
                    if path.exists():
                        size = path.stat().st_size
                        size_str = f"{size / 1024:.2f} KB" if size >= 1024 else f"{size} bytes"
                        modified = datetime.datetime.fromtimestamp(path.stat().st_mtime).strftime("%H:%M:%S")
                        file_table.add_row(outfile, size_str, "✓", modified)
                    else:
                        file_table.add_row(outfile, "N/A", "✗", "N/A")
                
                console.print(file_table)
            
            # Log timing data
            data = {
                label: {
                    "seconds": elapsed,
                    "finished": datetime.datetime.utcnow().isoformat()
                }
            }
            _append_json(STAGE_LOG, data)
            
            # Record Prometheus metric
            PROCESSING_LATENCY.labels(stage=label, run_id=run_id).observe(elapsed)
            
            return result
            
        except subprocess.CalledProcessError as e:
            elapsed = time.perf_counter() - t0
            console.print(f"[bold red]✗[/bold red] {label} failed after [bold]{elapsed:.2f}s[/bold]")
            console.print(f"[red]Error:[/red] {e}")
            console.print(f"[dim]STDOUT:[/dim] {e.stdout}")
            console.print(f"[dim]STDERR:[/dim] {e.stderr}")
            sys.exit(1)
            
        except Exception as e:
            elapsed = time.perf_counter() - t0
            console.print(f"[bold red]✗[/bold red] {label} failed after [bold]{elapsed:.2f}s[/bold]")
            console.print(f"[red]Error:[/red] {e}")
            sys.exit(1)


def _append_json(path: Path, obj: dict):
    """Append JSON object to a file, creating it if it doesn't exist."""
    if path.exists():
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}
    
    # Update with new data
    data.update(obj)
    
    # Write back to file
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def start_metrics_server(port: int = 8000):
    """Start Prometheus metrics HTTP server in a separate thread."""
    def _run_server():
        start_http_server(port)
        console.print(f"[bold green]Prometheus metrics server started on port {port}[/bold green]")
    
    thread = threading.Thread(target=_run_server, daemon=True)
    thread.start()
    return thread


def force_regeneration():
    """Delete hash files to force regeneration of summary and fewshots."""
    files_removed = []
    
    if SUMMARY_HASH_FILE.exists():
        SUMMARY_HASH_FILE.unlink()
        files_removed.append(str(SUMMARY_HASH_FILE))
        
    if FEWSHOTS_HASH_FILE.exists():
        FEWSHOTS_HASH_FILE.unlink()
        files_removed.append(str(FEWSHOTS_HASH_FILE))
    
    if files_removed:
        console.print(f"[bold yellow]Removed hash files:[/bold yellow] {', '.join(files_removed)}")
        console.print("[bold yellow]Will force regeneration of summary and fewshots[/bold yellow]")
    else:
        console.print("[bold yellow]No hash files found, will generate fresh summary and fewshots[/bold yellow]")


def get_worker_settings():
    """
    Get worker settings from environment variables or defaults
    
    Returns:
        dict: Worker settings for different pipeline stages
    """
    worker_settings = {}
    
    # Get from environment variables
    gemma_threads = os.environ.get("WDF_GEMMA_THREADS")
    if gemma_threads and gemma_threads.isdigit():
        worker_settings["gemma_threads"] = int(gemma_threads)
    
    deepseek_workers = os.environ.get("WDF_DEEPSEEK_WORKERS")
    if deepseek_workers and deepseek_workers.isdigit():
        worker_settings["deepseek_workers"] = int(deepseek_workers)
    
    return worker_settings


def run_claude_pipeline(episode_id: str, verbose: bool = False, force: bool = False):
    """
    Run the Claude-powered pipeline for a specific episode.
    
    Args:
        episode_id: Episode ID (required for Claude pipeline)
        verbose: Enable verbose logging
        force: Force regeneration
    
    Returns:
        Dict with pipeline results
    """
    console.print(Panel.fit(
        "[bold]WDF Claude Pipeline[/bold]\n"
        "Using Claude for all pipeline stages",
        border_style="cyan"
    ))
    
    # Check if we're in web mode
    if os.environ.get("WDF_WEB_MODE", "false").lower() != "true":
        console.print("[bold red]Error:[/bold red] Claude pipeline requires WDF_WEB_MODE=true")
        console.print("[yellow]Please set WDF_WEB_MODE=true to use Claude pipeline with database integration[/yellow]")
        return None
    
    # Import the Claude pipeline bridge
    try:
        sys.path.insert(0, str(Path(__file__).parent / "web" / "scripts"))
        from claude_pipeline_bridge import ClaudePipelineBridge
        
        # Parse episode_id to extract integer ID
        try:
            # Handle different episode_id formats (e.g., "1", "ep1", "episode_1")
            if episode_id.isdigit():
                ep_id = int(episode_id)
            elif episode_id.startswith("ep"):
                ep_id = int(episode_id[2:])
            elif episode_id.startswith("episode_"):
                ep_id = int(episode_id[8:])
            else:
                ep_id = int(episode_id)
        except (ValueError, TypeError):
            console.print(f"[bold red]Error:[/bold red] Invalid episode ID format: {episode_id}")
            return None
        
        console.print(f"[bold cyan]Episode ID:[/bold cyan] {ep_id}")
        
        # Initialize the bridge
        bridge = ClaudePipelineBridge(episode_id=ep_id)
        
        # Run the full Claude pipeline
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            TimeElapsedColumn(),
            console=console,
            transient=False,
        ) as progress:
            task = progress.add_task("Running Claude pipeline...", total=None)
            
            try:
                # Run full pipeline
                results = bridge.run_full_pipeline(force=force)
                
                progress.update(task, completed=100)
                
                # Display results summary
                console.print("\n[bold green]✓ Claude Pipeline Complete[/bold green]\n")
                
                # Display stage results
                stages_table = Table(title="Pipeline Stages", show_header=True, header_style="bold magenta")
                stages_table.add_column("Stage", style="cyan")
                stages_table.add_column("Status", justify="center")
                stages_table.add_column("Cost", justify="right", style="yellow")
                stages_table.add_column("Duration", justify="right", style="dim")
                
                for stage_name, stage_data in results.get('stages', {}).items():
                    status = "✓" if stage_data.get('success') else "✗"
                    cost = f"${stage_data.get('cost', 0):.4f}"
                    duration = f"{stage_data.get('duration', 0):.2f}s"
                    stages_table.add_row(stage_name, status, cost, duration)
                
                console.print(stages_table)
                
                # Display cost summary
                total_cost = results.get('total_cost', 0)
                console.print(f"\n[bold]Total Claude API Cost:[/bold] [yellow]${total_cost:.4f}[/yellow]")
                
                # Display any errors
                if results.get('errors'):
                    console.print("\n[bold red]Errors encountered:[/bold red]")
                    for error in results['errors']:
                        console.print(f"  • {error}")
                
                return results
                
            except Exception as e:
                progress.update(task, completed=100)
                console.print(f"\n[bold red]✗ Pipeline failed:[/bold red] {e}")
                if verbose:
                    import traceback
                    console.print(traceback.format_exc())
                return None
                
    except ImportError as e:
        console.print(f"[bold red]Error:[/bold red] Failed to import Claude pipeline bridge: {e}")
        console.print("[yellow]Ensure claude_pipeline_bridge.py is available in web/scripts/[/yellow]")
        return None


def run(verbose: bool = False, non_interactive: bool = False, metrics_port: int = 8000, force: bool = False, workers: int = None, episode_id: str = None):
    """
    Run the full WDF pipeline
    
    Args:
        verbose: Enable verbose logging
        non_interactive: Skip interactive moderation
        metrics_port: Port for Prometheus metrics HTTP server
        force: Force regeneration of summary and fewshots
        workers: Number of worker threads for DeepSeek response generation
        episode_id: Episode ID for file management
    """
    # Check if Claude pipeline is enabled
    use_claude = os.environ.get("WDF_USE_CLAUDE_PIPELINE", "false").lower() == "true"
    
    if use_claude:
        if episode_id:
            # Run full Claude pipeline with episode context
            return run_claude_pipeline(episode_id, verbose, force)
        else:
            # Claude is enabled but no episode - can still use for single tweets
            console.print("[bold yellow]Claude pipeline enabled without episode ID[/bold yellow]")
            console.print("[dim]Claude can still be used for single tweet responses via the API[/dim]")
            console.print("[dim]For full pipeline, provide --episode-id[/dim]")
            # Continue with regular pipeline but use Claude for responses
            os.environ["WDF_USE_CLAUDE_RESPONSES"] = "true"
    
    # Set environment variable to disable automatic Twitter scraping
    os.environ["WDF_NO_AUTO_SCRAPE"] = "true"
    
    # Set episode ID environment variable if provided
    if episode_id:
        os.environ["WDF_EPISODE_ID"] = episode_id
        console.print(f"[bold cyan]Using episode-based file management:[/bold cyan] {episode_id}")
    
    # Start metrics server
    metrics_thread = start_metrics_server(metrics_port)
    
    # Generate a run ID based on timestamp
    run_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    
    # Configure logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOGS_DIR / "pipeline.log")
        ]
    )
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Display header
    console.print(Panel.fit(
        "[bold]WDF Podcast Social-Engagement Pipeline[/bold]\n"
        "War, Divorce, or Federalism",
        border_style="cyan"
    ))
    console.print(f"[bold]Run ID:[/bold] {run_id}")
    
    # Get worker settings from environment
    worker_settings = get_worker_settings()
    gemma_threads = worker_settings.get("gemma_threads")
    deepseek_workers = workers or worker_settings.get("deepseek_workers")
    
    # Update PIPELINE_INFO with worker counts
    if gemma_threads is not None:
        PIPELINE_INFO["tweet_classification"]["workers"] = gemma_threads
    if deepseek_workers is not None:
        PIPELINE_INFO["deepseek_responses"]["workers"] = deepseek_workers
    
    # Load LLM configuration from database if web mode is enabled
    if os.environ.get("WDF_WEB_MODE", "false").lower() == "true":
        try:
            # Load LLM config from database
            result = subprocess.run(
                [sys.executable, "scripts/load_llm_config.py"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                # Execute the export commands to set environment variables
                for line in result.stdout.strip().split('\n'):
                    if line.startswith('export '):
                        key_value = line[7:]  # Remove 'export '
                        key, value = key_value.split('=', 1)
                        os.environ[key] = value.strip('"')
                console.print("[green]✓[/green] Loaded LLM configuration from database")
        except Exception as e:
            console.print(f"[yellow]Warning:[/yellow] Failed to load LLM config from database: {e}")
        
        # Load scoring configuration from database
        try:
            result = subprocess.run(
                [sys.executable, "web/scripts/load_scoring_config.py"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                # Execute the export commands to set environment variables
                for line in result.stdout.strip().split('\n'):
                    if line.startswith('export '):
                        key_value = line[7:]  # Remove 'export '
                        key, value = key_value.split('=', 1)
                        os.environ[key] = value.strip('"')
                console.print("[green]✓[/green] Loaded scoring configuration from database")
        except Exception as e:
            console.print(f"[yellow]Warning:[/yellow] Failed to load scoring config from database: {e}")
        
        # Load prompts and context files from database
        try:
            console.print("[cyan]Loading prompts from database...[/cyan]")
            result = subprocess.run(
                [sys.executable, "scripts/load_prompts.py"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                loaded_count = 0
                # Execute the export commands to set environment variables
                for line in result.stdout.strip().split('\n'):
                    if line.startswith('export '):
                        key_value = line[7:]  # Remove 'export '
                        if '=' in key_value:
                            key, value = key_value.split('=', 1)
                            # Remove surrounding quotes
                            if value.startswith("'") and value.endswith("'"):
                                value = value[1:-1]
                            os.environ[key] = value
                            loaded_count += 1
                console.print(f"[green]✓[/green] Loaded {loaded_count} prompts and context files from database")
            else:
                console.print(f"[yellow]Warning:[/yellow] Failed to load prompts from database")
        except Exception as e:
            console.print(f"[yellow]Warning:[/yellow] Failed to load prompts: {e}")
            console.print("[dim]Using hardcoded prompts as fallback[/dim]")
    
    # Try to get model information from settings module
    try:
        from src.wdf.settings import get_settings
        settings = get_settings()
        
        # Update model information if available
        if hasattr(settings, "llm_models"):
            # Use task-specific models
            if hasattr(settings.llm_models, "classification"):
                PIPELINE_INFO["tweet_classification"]["model"] = settings.llm_models.classification
            if hasattr(settings.llm_models, "response"):
                PIPELINE_INFO["deepseek_responses"]["model"] = settings.llm_models.response
            if hasattr(settings.llm_models, "summarization"):
                PIPELINE_INFO["gemini_summarize"]["model"] = settings.llm_models.summarization
            if hasattr(settings.llm_models, "fewshot"):
                PIPELINE_INFO["fewshot_generation"]["model"] = settings.llm_models.fewshot
    except (ImportError, AttributeError):
        pass
    
    # Display configuration information
    config_table = Table(title="Pipeline Configuration", show_header=True, header_style="bold green")
    config_table.add_column("Setting", style="cyan")
    config_table.add_column("Value")
    config_table.add_column("Source", style="dim")
    config_table.add_row("Verbose Logging", str(verbose), "Command line")
    config_table.add_row("Interactive Moderation", str(not non_interactive), "Command line")
    config_table.add_row("Metrics Port", str(metrics_port), "Command line")
    config_table.add_row("Force Regeneration", str(force), "Command line")
    
    # Worker information
    worker_source = "Command line" if workers is not None else "Environment" if deepseek_workers is not None else "Default"
    config_table.add_row(
        "DeepSeek Workers", 
        str(PIPELINE_INFO["deepseek_responses"]["workers"]), 
        worker_source
    )
    
    gemma_source = "Environment" if gemma_threads is not None else "Default"
    config_table.add_row(
        "Gemma 3N Workers", 
        str(PIPELINE_INFO["tweet_classification"]["workers"]), 
        gemma_source
    )
    
    # Try to get additional settings from settings module
    try:
        from src.wdf.settings import get_settings
        settings = get_settings()
        
        # Add ollama host information
        config_table.add_row(
            "Ollama Host", 
            getattr(settings, "ollama_host", "Unknown"),
            "Settings"
        )
        
        # Add model information if available
        if hasattr(settings, "llm_models"):
            config_table.add_row(
                "Gemma Model", 
                getattr(settings.llm_models, "gemma", "Unknown"),
                "Settings"
            )
            config_table.add_row(
                "DeepSeek Model", 
                getattr(settings.llm_models, "deepseek", "Unknown"),
                "Settings"
            )
            config_table.add_row(
                "Gemini Model", 
                getattr(settings.llm_models, "gemini", "Unknown"),
                "Settings"
            )
    except (ImportError, AttributeError):
        pass
    
    # Add scoring threshold information
    try:
        from src.wdf.constants import RELEVANCY_THRESHOLD, HIGH_RELEVANCY_THRESHOLD
        config_table.add_row(
            "Relevancy Threshold", 
            f"{RELEVANCY_THRESHOLD:.2f}",
            "Scoring"
        )
        config_table.add_row(
            "Priority Threshold", 
            f"{HIGH_RELEVANCY_THRESHOLD:.2f}",
            "Scoring"
        )
    except (ImportError, AttributeError):
        pass
    
    console.print(config_table)
    
    # Display warning about Twitter API usage
    console.print("")
    console.print(Panel.fit(
        "[bold yellow]⚠ TWITTER API NOTICE[/bold yellow]\n\n"
        "Automatic Twitter scraping is [bold red]DISABLED[/bold red] to prevent unintended API usage.\n\n"
        "The pipeline will:\n"
        "• Use cached tweets from previous runs (if available)\n"
        "• Generate sample tweets as fallback (if enabled)\n"
        "• Continue with empty tweets file (if no cache)\n\n"
        "To scrape new tweets, use the manual trigger in the web UI:\n"
        "[bold cyan]http://localhost:3000/settings/scraping[/bold cyan]",
        title="API Usage Policy",
        border_style="yellow"
    ))
    console.print("")
    
    # Force regeneration if requested
    if force:
        force_regeneration()
    
    # Import settings early to check model selection
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from src.wdf.settings import get_settings
        settings = get_settings()
    except ImportError:
        settings = None
    
    # Run each stage of the pipeline
    # Check if Claude is selected for summarization
    if settings and hasattr(settings, 'llm_models') and settings.llm_models.summarization == "claude":
        console.print("[bold cyan]Using Claude for summarization[/bold cyan]")
        _timeit("transcript_analysis", [sys.executable, "scripts/claude_summarizer.py"] + (["--verbose"] if verbose else []), run_id)
    else:
        _timeit("transcript_analysis", ["node", "scripts/transcript_summarizer.js"] + (["--verbose"] if verbose else []), run_id)
    
    # Import the tasks here to avoid import errors if run from outside the package
    sys.path.insert(0, str(Path(__file__).parent))
    
    try:
        from src.wdf.tasks import scrape, fewshot, classify, moderation
        from src.wdf.settings import get_settings
        
        # Get current settings
        settings = get_settings()
        
        # Import response generator based on provider
        if settings.llm_models.response_provider == "claude":
            from src.wdf.tasks import claude as response_generator
            response_task_name = "claude_responses"
            console.print("[bold cyan]Using Claude for response generation[/bold cyan]")
        else:
            from src.wdf.tasks import deepseek as response_generator
            response_task_name = "deepseek_responses"
            console.print("[bold cyan]Using DeepSeek for response generation[/bold cyan]")
        
        # Update PIPELINE_INFO with worker counts from settings
        if hasattr(settings, "GEMMA_THREADS"):
            PIPELINE_INFO["tweet_classification"]["workers"] = settings.GEMMA_THREADS
        if workers is None and hasattr(settings, "DEEPSEEK_WORKERS"):
            PIPELINE_INFO["deepseek_responses"]["workers"] = settings.DEEPSEEK_WORKERS
        elif workers is not None:
            PIPELINE_INFO["deepseek_responses"]["workers"] = workers
        
        # Generate fewshots first so that tweet scraping can use them
        # Check if Claude is selected for fewshot generation
        if hasattr(settings.llm_models, 'fewshot') and settings.llm_models.fewshot == "claude":
            from src.wdf.tasks import claude_fewshot
            console.print("[bold cyan]Using Claude for few-shot generation[/bold cyan]")
            _timeit("fewshot_generation", lambda: claude_fewshot.run(run_id=run_id, episode_id=episode_id), run_id)
        else:
            _timeit("fewshot_generation", lambda: fewshot.run(run_id=run_id, force=force, episode_id=episode_id), run_id)
        
        # Sync keywords from database to JSON file if in web mode
        if os.getenv("WDF_WEB_MODE", "false").lower() == "true":
            console.print("[bold blue]Syncing keywords from database...[/bold blue]")
            try:
                # Import and run sync_keywords script
                sync_result = subprocess.run(
                    [sys.executable, "web/scripts/sync_keywords.py"],
                    capture_output=True,
                    text=True
                )
                if sync_result.returncode == 0:
                    console.print("[bold green]✓ Keywords synced from database[/bold green]")
                else:
                    console.print(f"[bold yellow]⚠ Keyword sync failed: {sync_result.stderr}[/bold yellow]")
            except Exception as e:
                console.print(f"[bold yellow]⚠ Could not sync keywords: {e}[/bold yellow]")
        
        # Run Twitter scraping (will be skipped due to WDF_NO_AUTO_SCRAPE)
        console.print("[bold yellow]⚠ Twitter scraping is disabled in automatic mode[/bold yellow]")
        console.print("[dim]Will use cached tweets from previous runs if available[/dim]")
        console.print("[dim]To scrape new tweets, use the manual trigger in the web UI at http://localhost:3000/settings/scraping[/dim]")
        _timeit("twitter_scrape", lambda: scrape.run(run_id=run_id, episode_id=episode_id), run_id)
        
        # Check if Claude is selected for classification
        if hasattr(settings.llm_models, 'classification') and settings.llm_models.classification == "claude":
            from src.wdf.tasks import claude_classify
            console.print("[bold cyan]Using Claude for classification (direct reasoning, no few-shot)[/bold cyan]")
            _timeit("tweet_classification", lambda: claude_classify.run(run_id=run_id, episode_id=episode_id), run_id)
        else:
            _timeit("tweet_classification", lambda: classify.run(run_id=run_id, episode_id=episode_id), run_id)
        
        # Display classification statistics
        try:
            classified_path = Path("transcripts/classified.json")
            if classified_path.exists():
                with open(classified_path, "r") as f:
                    classified_tweets = json.load(f)
                
                total_count = len(classified_tweets)
                relevant_count = sum(1 for t in classified_tweets if t.get("relevance_score", 0) >= 0.70)
                skip_count = sum(1 for t in classified_tweets if t.get("relevance_score", 0) < 0.70)
                avg_score = sum(t.get("relevance_score", 0) for t in classified_tweets) / total_count if total_count > 0 else 0
                relevancy_percentage = (relevant_count / total_count * 100) if total_count > 0 else 0
                
                # Create classification stats table
                stats_table = Table(title="Tweet Scoring Statistics", show_header=True, header_style="bold magenta")
                stats_table.add_column("Metric", style="cyan")
                stats_table.add_column("Value", justify="right", style="green")
                stats_table.add_row("Total Tweets", str(total_count))
                stats_table.add_row("Average Score", f"{avg_score:.2f}")
                stats_table.add_row("Relevant (≥ 0.70)", f"{relevant_count} ({relevancy_percentage:.1f}%)")
                stats_table.add_row("Not Relevant (< 0.70)", f"{skip_count} ({100 - relevancy_percentage:.1f}%)")
                console.print(stats_table)
                
                # Create relevant tweets file for deepseek
                relevant_tweets = [t for t in classified_tweets if t.get("relevance_score", 0) >= 0.70]
                relevant_tweets_path = Path("transcripts/relevant_tweets.json")
                with open(relevant_tweets_path, "w") as f:
                    json.dump(relevant_tweets, f, indent=2)
                console.print(f"[bold green]✓[/bold green] Created relevant_tweets.json with {len(relevant_tweets)} tweets (score ≥ 0.70)")
        except Exception as e:
            console.print(f"[yellow]Could not display classification statistics: {e}[/yellow]")
        
        # Generate and document responses
        responses_path = _timeit(response_task_name, lambda: response_generator.run(run_id=run_id, num_workers=workers, episode_id=episode_id), run_id)
        provider_name = "Claude" if settings.llm_models.response_provider == "claude" else "DeepSeek"
        console.print(f"[bold green]{provider_name} responses saved to:[/bold green] {responses_path}")
        console.print("[bold cyan]To view responses:[/bold cyan] cat " + str(responses_path))
        
        # Launch moderation based on mode
        if os.getenv("WDF_WEB_MODE", "false").lower() == "true":
            # Use web-based moderation
            from src.wdf.tasks import web_moderation
            console.print("[bold magenta]Using web-based moderation...[/bold magenta]")
            console.print("[bold]Approve drafts at:[/bold] http://localhost:3000/review")
            moderated_path = _timeit("moderation_queue", lambda: web_moderation.run(run_id=run_id), run_id)
            console.print(f"[bold green]Published drafts saved to:[/bold green] {moderated_path}")
        else:
            # Use CLI moderation
            if non_interactive:
                console.print("[bold yellow]Skipping interactive moderation TUI (non-interactive mode)[/bold yellow]")
                _timeit("moderation_queue", lambda: moderation.run(run_id=run_id, non_interactive=non_interactive), run_id)
            else:
                console.print("[bold magenta]Launching moderation TUI...[/bold magenta]")
                console.print("[bold]Instructions:[/bold] Use [a]pprove | [e]dit | [r]eject | [q]uit")
                moderated_path = _timeit("moderation_queue", lambda: moderation.run(run_id=run_id, non_interactive=non_interactive), run_id)
                console.print(f"[bold green]Moderation results saved to:[/bold green] {moderated_path}")
        
    except ImportError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        console.print("[yellow]Falling back to direct script execution[/yellow]")
        
        # Check if Claude is selected for fewshot generation
        if settings and hasattr(settings.llm_models, 'fewshot') and settings.llm_models.fewshot == "claude":
            console.print("[bold cyan]Using Claude for few-shot generation[/bold cyan]")
            fewshot_cmd = [sys.executable, "src/wdf/tasks/claude_fewshot.py", f"--run-id={run_id}"]
        else:
            # Add --force flag to fewshot.py if force is True
            fewshot_cmd = [sys.executable, "src/wdf/tasks/fewshot.py", f"--run-id={run_id}"]
            if force:
                fewshot_cmd.append("--force")
        _timeit("fewshot_generation", fewshot_cmd, run_id)
        
        # Sync keywords from database to JSON file if in web mode
        if os.getenv("WDF_WEB_MODE", "false").lower() == "true":
            console.print("[bold blue]Syncing keywords from database...[/bold blue]")
            try:
                sync_result = subprocess.run(
                    [sys.executable, "web/scripts/sync_keywords.py"],
                    capture_output=True,
                    text=True
                )
                if sync_result.returncode == 0:
                    console.print("[bold green]✓ Keywords synced from database[/bold green]")
                else:
                    console.print(f"[bold yellow]⚠ Keyword sync failed: {sync_result.stderr}[/bold yellow]")
            except Exception as e:
                console.print(f"[bold yellow]⚠ Could not sync keywords: {e}[/bold yellow]")
        
        # Run tweet scraping after fewshot generation (will be skipped due to WDF_NO_AUTO_SCRAPE)
        console.print("[bold yellow]⚠ Twitter scraping is disabled in automatic mode[/bold yellow]")
        console.print("[dim]Will use cached tweets from previous runs if available[/dim]")
        console.print("[dim]To scrape new tweets, use the manual trigger in the web UI at http://localhost:3000/settings/scraping[/dim]")
        _timeit("twitter_scrape", [sys.executable, "src/wdf/tasks/scrape.py", f"--run-id={run_id}"], run_id)
        
        # Check if Claude is selected for classification
        if settings and hasattr(settings.llm_models, 'classification') and settings.llm_models.classification == "claude":
            console.print("[bold cyan]Using Claude for classification (direct reasoning, no few-shot)[/bold cyan]")
            _timeit("tweet_classification", [sys.executable, "src/wdf/tasks/claude_classify.py", f"--run-id={run_id}"], run_id)
        else:
            _timeit("tweet_classification", [sys.executable, "src/wdf/tasks/classify.py", f"--run-id={run_id}"], run_id)
        
        # Display classification statistics
        try:
            classified_path = Path("transcripts/classified.json")
            if classified_path.exists():
                with open(classified_path, "r") as f:
                    classified_tweets = json.load(f)
                
                total_count = len(classified_tweets)
                relevant_count = sum(1 for t in classified_tweets if t.get("relevance_score", 0) >= 0.70)
                skip_count = sum(1 for t in classified_tweets if t.get("relevance_score", 0) < 0.70)
                avg_score = sum(t.get("relevance_score", 0) for t in classified_tweets) / total_count if total_count > 0 else 0
                relevancy_percentage = (relevant_count / total_count * 100) if total_count > 0 else 0
                
                # Create classification stats table
                stats_table = Table(title="Tweet Scoring Statistics", show_header=True, header_style="bold magenta")
                stats_table.add_column("Metric", style="cyan")
                stats_table.add_column("Value", justify="right", style="green")
                stats_table.add_row("Total Tweets", str(total_count))
                stats_table.add_row("Average Score", f"{avg_score:.2f}")
                stats_table.add_row("Relevant (≥ 0.70)", f"{relevant_count} ({relevancy_percentage:.1f}%)")
                stats_table.add_row("Not Relevant (< 0.70)", f"{skip_count} ({100 - relevancy_percentage:.1f}%)")
                console.print(stats_table)
                
                # Create relevant tweets file for deepseek
                relevant_tweets = [t for t in classified_tweets if t.get("relevance_score", 0) >= 0.70]
                relevant_tweets_path = Path("transcripts/relevant_tweets.json")
                with open(relevant_tweets_path, "w") as f:
                    json.dump(relevant_tweets, f, indent=2)
                console.print(f"[bold green]✓[/bold green] Created relevant_tweets.json with {len(relevant_tweets)} tweets (score ≥ 0.70)")
        except Exception as e:
            console.print(f"[yellow]Could not display classification statistics: {e}[/yellow]")
        
        # Generate and document responses based on provider
        from src.wdf.settings import get_settings
        settings = get_settings()
        if settings.llm_models.response_provider == "claude":
            responses_cmd = [sys.executable, "src/wdf/tasks/claude.py", f"--run-id={run_id}"]
            response_task_name = "claude_responses"
            provider_name = "Claude"
        else:
            responses_cmd = [sys.executable, "src/wdf/tasks/deepseek.py", f"--run-id={run_id}"]
            if workers is not None:
                responses_cmd.append(f"--workers={workers}")
                PIPELINE_INFO["deepseek_responses"]["workers"] = workers
            response_task_name = "deepseek_responses"
            provider_name = "DeepSeek"
        responses_result = _timeit(response_task_name, responses_cmd, run_id)
        console.print(f"[bold green]{provider_name} responses generated[/bold green]")
        console.print("[bold cyan]To view responses:[/bold cyan] cat transcripts/responses.json")
        
        # Launch moderation based on mode
        if os.getenv("WDF_WEB_MODE", "false").lower() == "true":
            # Use web-based moderation
            console.print("[bold magenta]Using web-based moderation...[/bold magenta]")
            console.print("[bold]Approve drafts at:[/bold] http://localhost:3000/review")
            _timeit("moderation_queue", [sys.executable, "src/wdf/tasks/web_moderation.py", f"--run-id={run_id}"], run_id)
            console.print("[bold green]Published drafts complete![/bold green]")
        else:
            # Use CLI moderation
            if non_interactive:
                console.print("[bold yellow]Skipping interactive moderation TUI (non-interactive mode)[/bold yellow]")
                _timeit("moderation_queue", [sys.executable, "src/wdf/tasks/moderation.py", f"--run-id={run_id}", "--non-interactive"], run_id)
            else:
                console.print("[bold magenta]Launching moderation TUI...[/bold magenta]")
                console.print("[bold]Instructions:[/bold] Use [a]pprove | [e]dit | [r]eject | [q]uit")
                _timeit("moderation_queue", [sys.executable, "src/wdf/tasks/moderation.py", f"--run-id={run_id}"], run_id)
                console.print("[bold green]Moderation complete![/bold green]")
    
    # Display summary of pipeline execution
    summary_table = Table(title=f"Pipeline Summary (Run ID: {run_id})", show_header=True, header_style="bold blue")
    summary_table.add_column("Stage", style="cyan")
    summary_table.add_column("Description", style="yellow")
    summary_table.add_column("Workers", justify="center")
    summary_table.add_column("Model", style="magenta")
    summary_table.add_column("Input Files", style="dim")
    summary_table.add_column("Output Files")
    
    for stage, info in PIPELINE_INFO.items():
        workers_str = str(info["workers"]) if info["workers"] is not None else "N/A"
        model_str = info.get("model", "N/A")
        inputs = ", ".join(info["input_files"]) if info["input_files"] else "None"
        outputs = ", ".join(info["output_files"]) if info["output_files"] else "None"
        summary_table.add_row(stage, info["description"], workers_str, model_str, inputs, outputs)
    
    console.print(summary_table)
    
    console.print("[bold green]🎉 Pipeline completed successfully![/bold green]")


def main():
    """Parse command-line arguments and run the pipeline."""
    parser = argparse.ArgumentParser(description="Run full WDF tweet pipeline")
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG logging")
    parser.add_argument("--non-interactive", action="store_true", help="Skip interactive moderation")
    parser.add_argument("--metrics-port", type=int, default=8000, help="Port for Prometheus metrics HTTP server")
    parser.add_argument("--force", action="store_true", help="Force regeneration of summary and fewshots")
    parser.add_argument("--workers", type=int, help="Number of worker threads for DeepSeek response generation")
    parser.add_argument("--episode-id", type=str, help="Episode ID for file management")
    args = parser.parse_args()
    
    run(verbose=args.debug, non_interactive=args.non_interactive, metrics_port=args.metrics_port, force=args.force, workers=args.workers, episode_id=args.episode_id)


if __name__ == "__main__":
    main()