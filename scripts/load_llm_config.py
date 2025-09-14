#!/usr/bin/env python3
"""
Load LLM model configuration from database

This script loads LLM model configuration from the PostgreSQL database
and outputs environment variables that can be sourced in bash.

Usage:
    eval $(python scripts/load_llm_config.py)
    
Or to just view the configuration:
    python scripts/load_llm_config.py --show

Related files:
- /web/app/api/settings/llm-models/route.ts (API endpoint)
- /src/wdf/tasks/*.py (Task implementations)
"""

import json
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("# psycopg2 not installed, using defaults", file=sys.stderr)
    psycopg2 = None

# Default model configuration
DEFAULT_MODELS = {
    "summarization": "gemini-2.5-pro",
    "fewshot": "gemini-2.5-pro",
    "classification": "gemma3n:e4b",
    "response": "deepseek-r1:latest",
}

def get_database_url():
    """Get database URL from environment"""
    return os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/wdfwatch')

def load_llm_config_from_db():
    """Load LLM configuration from database"""
    if not psycopg2:
        return None
        
    try:
        conn = psycopg2.connect(get_database_url())
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT value FROM settings WHERE key = %s",
                ('llm_models',)
            )
            result = cur.fetchone()
            
            if result and result['value']:
                return result['value']
                
        conn.close()
        return None
        
    except Exception as e:
        print(f"# Error loading from database: {e}", file=sys.stderr)
        return None

def get_llm_config():
    """Get LLM configuration from database or defaults"""
    # Try to load from database first
    db_config = load_llm_config_from_db()
    if db_config:
        return db_config
        
    # Fall back to environment variables
    env_config = {}
    for task in DEFAULT_MODELS:
        env_var = f"WDF_LLM_MODEL_{task.upper()}"
        if env_var in os.environ:
            env_config[task] = os.environ[env_var]
            
    # Merge with defaults
    config = DEFAULT_MODELS.copy()
    config.update(env_config)
    
    return config

def export_as_env_vars(config):
    """Export configuration as environment variables"""
    # Export individual task models
    for task, model in config.items():
        print(f'export WDF_LLM_MODEL_{task.upper()}="{model}"')
        
    # Also export as nested environment variables for pydantic-settings
    print(f'export WDF_LLM_MODELS__SUMMARIZATION="{config.get("summarization", DEFAULT_MODELS["summarization"])}"')
    print(f'export WDF_LLM_MODELS__FEWSHOT="{config.get("fewshot", DEFAULT_MODELS["fewshot"])}"')
    print(f'export WDF_LLM_MODELS__CLASSIFICATION="{config.get("classification", DEFAULT_MODELS["classification"])}"')
    print(f'export WDF_LLM_MODELS__RESPONSE="{config.get("response", DEFAULT_MODELS["response"])}"')
    
    # For backward compatibility with existing settings
    print(f'export WDF_LLM_MODELS__GEMINI="{config.get("summarization", DEFAULT_MODELS["summarization"])}"')
    print(f'export WDF_LLM_MODELS__GEMMA="{config.get("classification", DEFAULT_MODELS["classification"])}"')
    print(f'export WDF_LLM_MODELS__DEEPSEEK="{config.get("response", DEFAULT_MODELS["response"])}"')

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Load LLM model configuration')
    parser.add_argument('--show', action='store_true', help='Show configuration instead of exporting')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    args = parser.parse_args()
    
    config = get_llm_config()
    
    if args.show:
        if args.json:
            print(json.dumps(config, indent=2))
        else:
            print("LLM Model Configuration:")
            print("-" * 40)
            for task, model in config.items():
                print(f"{task:15} : {model}")
    else:
        export_as_env_vars(config)

if __name__ == "__main__":
    main()