#!/usr/bin/env python3
"""
Keyword Learning Report Generator

Shows the current state of keyword learning, effectiveness tracking,
and provides recommendations for optimization.

Usage:
    python scripts/keyword_learning_report.py               # Show full report
    python scripts/keyword_learning_report.py --reset       # Reset all learning
    python scripts/keyword_learning_report.py --reset-keyword "politics"  # Reset specific keyword
    python scripts/keyword_learning_report.py --export      # Export to JSON
"""

import argparse
import json
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from wdf.keyword_learning import KeywordLearner
from wdf.keyword_tracker import KeywordTracker

console = Console()


def show_learning_report():
    """Display comprehensive keyword learning report."""
    learner = KeywordLearner()
    tracker = KeywordTracker()
    
    # Get recommendations
    recommendations = learner.get_keyword_recommendations()
    
    # Get API waste report
    waste_report = tracker.get_api_waste_report()
    
    # Display header
    console.print("\n[bold cyan]📊 Keyword Learning Report[/bold cyan]\n")
    
    # High Performers Table
    if recommendations['high_performers']:
        table = Table(title="🎯 High Performing Keywords", box=box.ROUNDED)
        table.add_column("Keyword", style="green")
        table.add_column("Success Rate", justify="right")
        table.add_column("Learned Weight", justify="right")
        
        for kw in recommendations['high_performers'][:10]:
            table.add_row(
                kw['keyword'],
                f"{kw['success_rate']:.1%}",
                f"{kw['weight']:.2f}"
            )
        
        console.print(table)
        console.print()
    
    # Low Performers Table
    if recommendations['low_performers']:
        table = Table(title="⚠️ Low Performing Keywords", box=box.ROUNDED)
        table.add_column("Keyword", style="red")
        table.add_column("Success Rate", justify="right")
        table.add_column("API Waste", justify="right", style="red")
        table.add_column("Weight", justify="right")
        
        for kw in recommendations['low_performers'][:10]:
            table.add_row(
                kw['keyword'],
                f"{kw['success_rate']:.1%}",
                str(kw['api_waste']),
                f"{kw['weight']:.2f}"
            )
        
        console.print(table)
        console.print()
    
    # Rising Stars
    if recommendations['rising_stars']:
        table = Table(title="📈 Rising Stars", box=box.ROUNDED)
        table.add_column("Keyword", style="yellow")
        table.add_column("Trend", justify="right")
        table.add_column("Current Rate", justify="right")
        
        for kw in recommendations['rising_stars']:
            trend_symbol = "↗️" if kw['trend'] > 0 else "→"
            table.add_row(
                kw['keyword'],
                f"{trend_symbol} +{kw['trend']:.2f}",
                f"{kw['current_rate']:.1%}"
            )
        
        console.print(table)
        console.print()
    
    # API Efficiency Summary
    summary = waste_report['summary']
    efficiency_color = "green" if summary['efficiency_percentage'] > 70 else "yellow" if summary['efficiency_percentage'] > 40 else "red"
    
    efficiency_panel = Panel.fit(
        f"""[bold]API Efficiency Report[/bold]
        
Total Tweets Classified: {summary['total_tweets_classified']}
Relevant: {summary['total_relevant']} ({summary['total_relevant']/max(1, summary['total_tweets_classified']):.1%})
Skipped: {summary['total_skipped']} ({summary['total_skipped']/max(1, summary['total_tweets_classified']):.1%})

[{efficiency_color}]Overall Efficiency: {summary['efficiency_percentage']:.1f}%[/{efficiency_color}]
API Calls Wasted: [red]{summary['api_calls_wasted']}[/red]
        """,
        title="💰 API Usage",
        box=box.ROUNDED
    )
    console.print(efficiency_panel)
    console.print()
    
    # Recommendations
    if recommendations['recommendations'] or waste_report['recommendations']:
        console.print("[bold]💡 Recommendations:[/bold]")
        for rec in recommendations['recommendations'][:3]:
            console.print(f"  • {rec}")
        for rec in waste_report['recommendations'][:3]:
            console.print(f"  • {rec}")
        console.print()
    
    # Learning Statistics
    console.print(f"[dim]Total Keywords Learned: {recommendations['total_learned']}[/dim]")
    console.print(f"[dim]Keywords Needing More Data: {len(recommendations.get('needs_exploration', []))}[/dim]")


def export_report(output_file: str = "keyword_learning_report.json"):
    """Export learning data to JSON file."""
    learner = KeywordLearner()
    tracker = KeywordTracker()
    
    # Gather all data
    data = {
        'recommendations': learner.get_keyword_recommendations(),
        'waste_report': tracker.get_api_waste_report(),
        'all_keyword_stats': tracker.get_all_keyword_stats(),
        'learned_weights': learner.learned_weights
    }
    
    # Save to file
    output_path = Path(output_file)
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    console.print(f"[green]✓[/green] Exported report to {output_path}")


def reset_learning(keyword: str = None):
    """Reset learned weights."""
    learner = KeywordLearner()
    
    if keyword:
        learner.reset_learning(keyword)
        console.print(f"[yellow]⟲[/yellow] Reset learning for keyword: {keyword}")
    else:
        # Confirm full reset
        console.print("[red]⚠️ This will reset ALL learned keyword weights![/red]")
        confirm = console.input("Are you sure? (yes/no): ")
        if confirm.lower() == 'yes':
            learner.reset_learning()
            console.print("[green]✓[/green] Reset all keyword learning data")
        else:
            console.print("[dim]Reset cancelled[/dim]")


def main():
    parser = argparse.ArgumentParser(description="Keyword Learning Report")
    parser.add_argument('--reset', action='store_true', help='Reset all learning')
    parser.add_argument('--reset-keyword', type=str, help='Reset specific keyword')
    parser.add_argument('--export', action='store_true', help='Export to JSON')
    parser.add_argument('--output', type=str, default='keyword_learning_report.json', 
                       help='Output file for export')
    
    args = parser.parse_args()
    
    if args.reset:
        reset_learning()
    elif args.reset_keyword:
        reset_learning(args.reset_keyword)
    elif args.export:
        export_report(args.output)
    else:
        show_learning_report()


if __name__ == '__main__':
    main()