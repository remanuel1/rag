import json
import logging
from typing import Optional, List, Dict, Any
import psycopg
from vector_store import get_psycopg_connection

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS chat_logs (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255),
    stream_id VARCHAR(255),
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    sources JSONB DEFAULT '[]'::jsonb,
    language VARCHAR(50) DEFAULT 'English',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_chat_logs_created_at ON chat_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_chat_logs_session_id ON chat_logs (session_id);
"""


def ensure_chat_logs_table() -> None:
    """Ensure the chat_logs table and indexes exist in PostgreSQL."""
    try:
        with psycopg.connect(get_psycopg_connection()) as conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_TABLE_SQL)
            conn.commit()
        logger.info("chat_logs table verified/created successfully.")
    except Exception as e:
        logger.error(f"Failed to ensure chat_logs table: {e}")


def save_chat_log(
    session_id: Optional[str],
    stream_id: Optional[str],
    question: str,
    answer: str,
    sources: Optional[List[str]] = None,
    language: str = "English",
) -> None:
    """
    Saves a user query and LLM answer to the database.
    Wrapped in try/except so logging never interrupts user-facing functionality.
    """
    try:
        sources_json = json.dumps(sources or [])
        with psycopg.connect(get_psycopg_connection()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chat_logs (session_id, stream_id, question, answer, sources, language)
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                    """,
                    (session_id, stream_id, question, answer, sources_json, language),
                )
            conn.commit()
    except Exception as e:
        logger.error(f"Error saving chat log to database: {e}")


def get_recent_chat_logs(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves recent chat logs ordered by creation time descending."""
    with psycopg.connect(get_psycopg_connection()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, session_id, stream_id, question, answer, sources, language, created_at
                FROM chat_logs
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
            logs = []
            for row in rows:
                raw_sources = row[5]
                if isinstance(raw_sources, list):
                    parsed_sources = raw_sources
                elif isinstance(raw_sources, str):
                    try:
                        parsed_sources = json.loads(raw_sources)
                    except Exception:
                        parsed_sources = [raw_sources]
                else:
                    parsed_sources = []

                logs.append({
                    "id": row[0],
                    "session_id": row[1],
                    "stream_id": row[2],
                    "question": row[3],
                    "answer": row[4],
                    "sources": parsed_sources,
                    "language": row[6],
                    "created_at": row[7].isoformat() if row[7] else None,
                })
            return logs
