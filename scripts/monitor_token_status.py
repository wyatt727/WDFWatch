#!/usr/bin/env python3
"""
Monitor OAuth token status and health.
Provides detailed information about token age, validity, and refresh history.

Usage:
    python scripts/monitor_token_status.py          # Show current status
    python scripts/monitor_token_status.py --watch  # Continuous monitoring
    python scripts/monitor_token_status.py --json   # Output as JSON
"""

import os
import sys
import json
import time
import argparse
import requests
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

console = Console()

def load_env_files():
    """Load environment files."""
    env_path = Path(__file__).parent.parent / ".env"
    wdfwatch_env_path = Path(__file__).parent.parent / ".env.wdfwatch"

    if env_path.exists():
        load_dotenv(env_path)
    if wdfwatch_env_path.exists():
        load_dotenv(wdfwatch_env_path, override=True)

def get_token_info():
    """Get comprehensive token information."""
    token_info = {}

    # Load token timestamp
    token_file = Path(__file__).parent.parent / ".wdfwatch_token_info.json"
    if token_file.exists():
        with open(token_file, 'r') as f:
            stored_info = json.load(f)
            issued_at = datetime.fromisoformat(stored_info.get('issued_at', ''))
            expires_in = stored_info.get('expires_in', 7200)

            token_info['issued_at'] = issued_at
            token_info['expires_in'] = expires_in
            token_info['expires_at'] = issued_at + timedelta(seconds=expires_in)

            # Calculate age and time remaining
            now = datetime.now()
            age = now - issued_at
            remaining = token_info['expires_at'] - now

            token_info['age_minutes'] = age.total_seconds() / 60
            token_info['remaining_minutes'] = remaining.total_seconds() / 60
            token_info['is_expired'] = remaining.total_seconds() <= 0
            token_info['needs_refresh'] = remaining.total_seconds() < 1800  # Less than 30 minutes
    else:
        token_info['error'] = 'No token info file found'

    # Check if tokens exist in environment
    load_env_files()
    token_info['has_access_token'] = bool(os.getenv("WDFWATCH_ACCESS_TOKEN"))
    token_info['has_refresh_token'] = bool(os.getenv("WDFWATCH_REFRESH_TOKEN"))
    token_info['has_api_key'] = bool(os.getenv("API_KEY") or os.getenv("CLIENT_ID"))

    # Get refresh history from logs
    refresh_log = Path(__file__).parent.parent / "logs" / "token_refresh.log"
    if refresh_log.exists():
        with open(refresh_log, 'r') as f:
            lines = f.readlines()
            # Get last 5 refresh attempts
            refresh_lines = [l for l in lines if 'refreshed successfully' in l.lower() or 'refresh failed' in l.lower()]
            token_info['refresh_history'] = refresh_lines[-5:] if refresh_lines else []

    # Test token validity if not expired
    if token_info.get('has_access_token') and not token_info.get('is_expired'):
        access_token = os.getenv("WDFWATCH_ACCESS_TOKEN")
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(
                "https://api.twitter.com/2/users/me",
                headers=headers,
                timeout=5
            )
            if response.status_code == 200:
                user_data = response.json()
                token_info['account'] = user_data.get('data', {}).get('username', 'unknown')
                token_info['is_valid'] = True
            else:
                token_info['is_valid'] = False
                token_info['validation_error'] = f"API returned {response.status_code}"
        except Exception as e:
            token_info['is_valid'] = False
            token_info['validation_error'] = str(e)

    return token_info

def display_status(token_info):
    """Display token status in a formatted table."""
    table = Table(title="WDFWatch OAuth Token Status", show_header=True)
    table.add_column("Property", style="cyan", width=30)
    table.add_column("Value", style="white")
    table.add_column("Status", style="white", width=15)

    # Token age
    if 'age_minutes' in token_info:
        age = token_info['age_minutes']
        age_str = f"{age:.1f} minutes"
        if age < 60:
            age_status = "[green]Fresh[/green]"
        elif age < 90:
            age_status = "[yellow]Good[/yellow]"
        elif age < 110:
            age_status = "[orange3]Old[/orange3]"
        else:
            age_status = "[red]Expired[/red]"
        table.add_row("Token Age", age_str, age_status)

    # Time remaining
    if 'remaining_minutes' in token_info:
        remaining = token_info['remaining_minutes']
        if remaining > 0:
            remaining_str = f"{remaining:.1f} minutes"
            if remaining > 60:
                remaining_status = "[green]Good[/green]"
            elif remaining > 30:
                remaining_status = "[yellow]Low[/yellow]"
            else:
                remaining_status = "[orange3]Critical[/orange3]"
        else:
            remaining_str = "EXPIRED"
            remaining_status = "[red]Expired[/red]"
        table.add_row("Time Remaining", remaining_str, remaining_status)

    # Token validity
    if 'is_valid' in token_info:
        if token_info['is_valid']:
            table.add_row("API Validation", "Valid", "[green]✓[/green]")
            table.add_row("Account", f"@{token_info.get('account', 'unknown')}", "[green]✓[/green]")
        else:
            error = token_info.get('validation_error', 'Unknown error')
            table.add_row("API Validation", error, "[red]✗[/red]")

    # Token presence
    table.add_row("Access Token",
                 "Present" if token_info.get('has_access_token') else "Missing",
                 "[green]✓[/green]" if token_info.get('has_access_token') else "[red]✗[/red]")
    table.add_row("Refresh Token",
                 "Present" if token_info.get('has_refresh_token') else "Missing",
                 "[green]✓[/green]" if token_info.get('has_refresh_token') else "[red]✗[/red]")
    table.add_row("API Key",
                 "Present" if token_info.get('has_api_key') else "Missing",
                 "[green]✓[/green]" if token_info.get('has_api_key') else "[red]✗[/red]")

    # Timestamps
    if 'issued_at' in token_info:
        table.add_row("Issued At", token_info['issued_at'].strftime("%Y-%m-%d %H:%M:%S"), "")
        table.add_row("Expires At", token_info['expires_at'].strftime("%Y-%m-%d %H:%M:%S"), "")

    console.print(table)

    # Refresh history
    if token_info.get('refresh_history'):
        console.print("\n[cyan]Recent Refresh History:[/cyan]")
        for line in token_info['refresh_history']:
            console.print(f"  {line.strip()}")

    # Recommendations
    if token_info.get('needs_refresh'):
        console.print("\n[yellow]⚠️  Token should be refreshed soon[/yellow]")
        console.print("Run: python scripts/ensure_fresh_tokens.py")
    elif token_info.get('is_expired'):
        console.print("\n[red]❌ Token is expired and must be refreshed[/red]")
        console.print("Run: python scripts/ensure_fresh_tokens.py --force")

def watch_status(interval=30):
    """Continuously monitor token status."""
    with Live(console=console, refresh_per_second=1) as live:
        while True:
            token_info = get_token_info()

            # Create display
            table = Table(title=f"Token Monitor - {datetime.now().strftime('%H:%M:%S')}")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="white")

            if 'age_minutes' in token_info:
                age = token_info['age_minutes']
                remaining = token_info['remaining_minutes']

                # Color code based on status
                if remaining <= 0:
                    age_style = "red"
                elif remaining < 30:
                    age_style = "orange3"
                elif remaining < 60:
                    age_style = "yellow"
                else:
                    age_style = "green"

                table.add_row("Token Age", f"[{age_style}]{age:.1f} min[/{age_style}]")
                table.add_row("Time Left", f"[{age_style}]{remaining:.1f} min[/{age_style}]")
                table.add_row("Expires At", token_info['expires_at'].strftime("%H:%M:%S"))

                if token_info.get('is_valid'):
                    table.add_row("Status", "[green]VALID ✓[/green]")
                elif token_info.get('is_expired'):
                    table.add_row("Status", "[red]EXPIRED ✗[/red]")
                else:
                    table.add_row("Status", "[yellow]UNKNOWN ?[/yellow]")

            live.update(Panel(table, title="WDFWatch Token Monitor", border_style="blue"))
            time.sleep(interval)

def main():
    parser = argparse.ArgumentParser(description='Monitor OAuth token status')
    parser.add_argument('--watch', action='store_true', help='Continuously monitor')
    parser.add_argument('--interval', type=int, default=30, help='Watch interval in seconds')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()

    if args.watch:
        try:
            watch_status(args.interval)
        except KeyboardInterrupt:
            console.print("\n[yellow]Monitoring stopped[/yellow]")
    else:
        token_info = get_token_info()
        if args.json:
            # Convert datetime objects to strings for JSON serialization
            output = {}
            for key, value in token_info.items():
                if isinstance(value, datetime):
                    output[key] = value.isoformat()
                else:
                    output[key] = value
            print(json.dumps(output, indent=2))
        else:
            display_status(token_info)

if __name__ == "__main__":
    main()