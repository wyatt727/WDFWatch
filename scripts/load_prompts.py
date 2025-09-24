#!/usr/bin/env python3
"""
Load prompts and context files from the database to environment variables.

This script fetches active prompt templates and context files from PostgreSQL
and exports them as environment variables that can be used by the pipeline tasks.

Usage:
    # Export variables to current shell
    eval $(python scripts/load_prompts.py)
    
    # Show current configuration
    python scripts/load_prompts.py --show
    
    # Test database connection
    python scripts/load_prompts.py --test
"""

import os
import sys
import json
import argparse
from typing import Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse


def get_db_connection() -> psycopg2.extensions.connection:
    """Create database connection from DATABASE_URL."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    # Parse the URL
    parsed = urlparse(database_url)
    
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        database=parsed.path[1:],  # Remove leading /
        user=parsed.username,
        password=parsed.password,
        cursor_factory=RealDictCursor
    )
    
    return conn


def load_prompts(conn: psycopg2.extensions.connection) -> Dict[str, Dict[str, Any]]:
    """Load active prompt templates from database."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT key, name, template, variables, description
            FROM prompt_templates
            WHERE "isActive" = true
            ORDER BY key
        """)
        
        prompts = {}
        for row in cur.fetchall():
            prompts[row['key']] = {
                'template': row['template'],
                'variables': row['variables'] or [],
                'name': row['name'],
                'description': row['description']
            }
        
        return prompts


def load_context_files(conn: psycopg2.extensions.connection) -> Dict[str, Dict[str, Any]]:
    """Load active context files from database."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT key, name, content, description
            FROM context_files
            WHERE "isActive" = true
            ORDER BY key
        """)
        
        context_files = {}
        for row in cur.fetchall():
            context_files[row['key']] = {
                'content': row['content'],
                'name': row['name'],
                'description': row['description']
            }
        
        return context_files


def export_as_env_vars(prompts: Dict[str, Dict[str, Any]], context_files: Dict[str, Dict[str, Any]]) -> None:
    """Export prompts and context files as environment variables."""
    # Export prompts
    for key, data in prompts.items():
        env_key = f"WDF_PROMPT_{key.upper()}"
        # Escape single quotes and newlines for shell export
        template = data['template'].replace("'", "'\"'\"'").replace('\n', '\\n')
        print(f"export {env_key}='{template}'")
        
        # Also export variables list for reference
        if data['variables']:
            vars_key = f"WDF_PROMPT_{key.upper()}_VARS"
            vars_json = json.dumps(data['variables'])
            print(f"export {vars_key}='{vars_json}'")
    
    # Export context files
    for key, data in context_files.items():
        env_key = f"WDF_CONTEXT_{key.upper()}"
        # Escape single quotes and newlines for shell export
        content = data['content'].replace("'", "'\"'\"'").replace('\n', '\\n')
        print(f"export {env_key}='{content}'")


def show_configuration(prompts: Dict[str, Dict[str, Any]], context_files: Dict[str, Dict[str, Any]]) -> None:
    """Display current prompt and context configuration."""
    print("=== PROMPT TEMPLATES ===")
    for key, data in prompts.items():
        print(f"\n{key}:")
        print(f"  Name: {data['name']}")
        if data['description']:
            print(f"  Description: {data['description']}")
        if data['variables']:
            print(f"  Variables: {', '.join(data['variables'])}")
        print(f"  Template Preview: {data['template'][:100]}..." if len(data['template']) > 100 else f"  Template: {data['template']}")
    
    print("\n\n=== CONTEXT FILES ===")
    for key, data in context_files.items():
        print(f"\n{key}:")
        print(f"  Name: {data['name']}")
        if data['description']:
            print(f"  Description: {data['description']}")
        print(f"  Content Preview: {data['content'][:100]}..." if len(data['content']) > 100 else f"  Content: {data['content']}")


def test_connection() -> bool:
    """Test database connection and table access."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Test prompt_templates table
            cur.execute("SELECT COUNT(*) as count FROM prompt_templates WHERE \"isActive\" = true")
            prompt_count = cur.fetchone()['count']
            
            # Test context_files table
            cur.execute("SELECT COUNT(*) as count FROM context_files WHERE \"isActive\" = true")
            context_count = cur.fetchone()['count']
            
            print(f"✓ Database connection successful")
            print(f"  - Active prompts: {prompt_count}")
            print(f"  - Active context files: {context_count}")
            
            conn.close()
            return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description='Load prompts and context files from database')
    parser.add_argument('--show', action='store_true', help='Show current configuration')
    parser.add_argument('--test', action='store_true', help='Test database connection')
    args = parser.parse_args()
    
    if args.test:
        success = test_connection()
        sys.exit(0 if success else 1)
    
    try:
        conn = get_db_connection()
        prompts = load_prompts(conn)
        context_files = load_context_files(conn)
        conn.close()
        
        if args.show:
            show_configuration(prompts, context_files)
        else:
            export_as_env_vars(prompts, context_files)
            
    except Exception as e:
        print(f"# Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()