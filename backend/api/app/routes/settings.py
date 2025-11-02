"""
Settings management endpoints.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from app.models.requests import SettingsUpdateRequest
from app.services.db import db_service

router = APIRouter()


@router.get("/llm-models")
async def get_llm_models():
    """Get LLM model configuration from database."""
    try:
        with db_service.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT value FROM settings WHERE key = 'llm_models'
                """)
                result = cursor.fetchone()
                
                if result:
                    import json
                    return json.loads(result[0])
                else:
                    return {
                        "summarization": "claude",
                        "classification": "claude",
                        "response": "claude",
                    }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get LLM models: {e}")


@router.put("/llm-models")
async def update_llm_models(request: Dict[str, Any]):
    """Update LLM model configuration in database."""
    try:
        import json
        with db_service.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO settings (key, value)
                    VALUES ('llm_models', %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
                """, (json.dumps(request),))
                conn.commit()
                
        return {"message": "LLM models updated", "models": request}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update LLM models: {e}")


@router.get("/scoring")
async def get_scoring_config():
    """Get scoring configuration from database."""
    try:
        with db_service.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT value FROM settings WHERE key = 'scoring_config'
                """)
                result = cursor.fetchone()
                
                if result:
                    import json
                    return json.loads(result[0])
                else:
                    return {
                        "relevancy_threshold": 0.70,
                        "priority_threshold": 0.85,
                    }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get scoring config: {e}")


@router.put("/scoring")
async def update_scoring_config(request: Dict[str, Any]):
    """Update scoring configuration in database."""
    try:
        import json
        with db_service.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO settings (key, value)
                    VALUES ('scoring_config', %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
                """, (json.dumps(request),))
                conn.commit()
                
        return {"message": "Scoring config updated", "config": request}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update scoring config: {e}")

