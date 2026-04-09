import uuid
from datetime import datetime

import aiosqlite
from alice.config import settings

CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_MESSAGES = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_PREFERENCES = """
CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_MSG_INDEX = """
CREATE INDEX IF NOT EXISTS idx_messages_session
    ON messages(session_id, created_at);
"""


async def init_db() -> None:
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(CREATE_SESSIONS)
        await db.execute(CREATE_MESSAGES)
        await db.execute(CREATE_PREFERENCES)
        await db.execute(CREATE_MSG_INDEX)
        await db.commit()


async def create_session() -> str:
    session_id = str(uuid.uuid4())
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "INSERT INTO sessions (id) VALUES (?)", (session_id,)
        )
        await db.commit()
    return session_id


async def save_message(session_id: str, role: str, content: str) -> None:
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        await db.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), session_id),
        )
        await db.commit()


async def get_history(session_id: str, limit: int | None = None) -> list[dict]:
    cap = limit or settings.max_history_messages
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT role, content FROM messages
            WHERE session_id = ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (session_id, cap),
        ) as cursor:
            rows = await cursor.fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


async def set_preference(key: str, value: str, confidence: float = 1.0) -> None:
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            """
            INSERT INTO preferences (key, value, confidence, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                confidence = excluded.confidence,
                updated_at = excluded.updated_at
            """,
            (key, value, confidence),
        )
        await db.commit()


async def get_preference(key: str) -> str | None:
    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(
            "SELECT value FROM preferences WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
    return row[0] if row else None


async def get_all_preferences() -> dict[str, str]:
    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute("SELECT key, value FROM preferences") as cursor:
            rows = await cursor.fetchall()
    return {r[0]: r[1] for r in rows}
