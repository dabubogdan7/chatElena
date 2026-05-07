import json
import os
import sqlite3
from datetime import datetime, timedelta

DATABASE_URL = os.environ.get("DATABASE_URL", "")
DB_PATH = os.environ.get("DB_PATH", "chatbot.db")

# Railway uneori da "postgres://" in loc de "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
    PH = "%s"  # placeholder PostgreSQL
else:
    PH = "?"   # placeholder SQLite


def get_connection():
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _cursor(conn):
    if USE_POSTGRES:
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn.cursor()


def init_db():
    conn = get_connection()
    cur = _cursor(conn)
    if USE_POSTGRES:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id SERIAL PRIMARY KEY,
                sender_id TEXT NOT NULL UNIQUE,
                messages TEXT NOT NULL DEFAULT '[]',
                needs_human BOOLEAN NOT NULL DEFAULT FALSE,
                follow_up_sent BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id TEXT NOT NULL,
                messages TEXT NOT NULL DEFAULT '[]',
                needs_human BOOLEAN NOT NULL DEFAULT 0,
                follow_up_sent BOOLEAN NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        try:
            cur.execute("ALTER TABLE conversations ADD COLUMN follow_up_sent BOOLEAN NOT NULL DEFAULT 0")
        except Exception:
            pass
    conn.commit()
    conn.close()


def get_conversation(sender_id: str) -> dict:
    conn = get_connection()
    cur = _cursor(conn)
    cur.execute(f"SELECT * FROM conversations WHERE sender_id = {PH}", (sender_id,))
    row = cur.fetchone()
    conn.close()

    if row:
        return {
            "sender_id": row["sender_id"],
            "messages": json.loads(row["messages"]),
            "needs_human": bool(row["needs_human"]),
        }

    now = datetime.utcnow().isoformat()
    conn = get_connection()
    cur = _cursor(conn)
    cur.execute(
        f"INSERT INTO conversations (sender_id, messages, needs_human, follow_up_sent, created_at, updated_at) VALUES ({PH},{PH},{PH},{PH},{PH},{PH})",
        (sender_id, "[]", False if USE_POSTGRES else 0, False if USE_POSTGRES else 0, now, now),
    )
    conn.commit()
    conn.close()
    return {"sender_id": sender_id, "messages": [], "needs_human": False}


def save_message(sender_id: str, role: str, content: str):
    conv = get_conversation(sender_id)
    conv["messages"].append({"role": role, "content": content})

    if len(conv["messages"]) > 50:
        conv["messages"] = conv["messages"][-50:]

    now = datetime.utcnow().isoformat()
    conn = get_connection()
    cur = _cursor(conn)
    cur.execute(
        f"UPDATE conversations SET messages = {PH}, updated_at = {PH} WHERE sender_id = {PH}",
        (json.dumps(conv["messages"]), now, sender_id),
    )
    conn.commit()
    conn.close()


def set_needs_human(sender_id: str, value: bool):
    now = datetime.utcnow().isoformat()
    conn = get_connection()
    cur = _cursor(conn)
    cur.execute(
        f"UPDATE conversations SET needs_human = {PH}, updated_at = {PH} WHERE sender_id = {PH}",
        (value if USE_POSTGRES else (1 if value else 0), now, sender_id),
    )
    conn.commit()
    conn.close()


def get_conversations_needing_followup(hours: int = 72) -> list[dict]:
    threshold = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    conn = get_connection()
    cur = _cursor(conn)
    cur.execute(
        f"SELECT sender_id, messages FROM conversations WHERE needs_human = {PH} AND follow_up_sent = {PH} AND updated_at < {PH}",
        (False if USE_POSTGRES else 0, False if USE_POSTGRES else 0, threshold),
    )
    rows = cur.fetchall()
    conn.close()
    result = []
    for row in rows:
        messages = json.loads(row["messages"])
        if messages and messages[-1]["role"] == "assistant":
            result.append({"sender_id": row["sender_id"]})
    return result


def mark_followup_sent(sender_id: str):
    now = datetime.utcnow().isoformat()
    conn = get_connection()
    cur = _cursor(conn)
    cur.execute(
        f"UPDATE conversations SET follow_up_sent = {PH}, updated_at = {PH} WHERE sender_id = {PH}",
        (True if USE_POSTGRES else 1, now, sender_id),
    )
    conn.commit()
    conn.close()


def get_all_conversations():
    conn = get_connection()
    cur = _cursor(conn)
    cur.execute("SELECT sender_id, needs_human, updated_at FROM conversations ORDER BY updated_at DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]
