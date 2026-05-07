import sqlite3
import json
import os
from datetime import datetime, timedelta

DB_PATH = os.environ.get("DB_PATH", "chatbot.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
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
    # Migrare DB existent — adauga coloana daca lipseste
    try:
        cursor.execute("ALTER TABLE conversations ADD COLUMN follow_up_sent BOOLEAN NOT NULL DEFAULT 0")
    except Exception:
        pass
    conn.commit()
    conn.close()


def get_conversation(sender_id: str) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM conversations WHERE sender_id = ?", (sender_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "sender_id": row["sender_id"],
            "messages": json.loads(row["messages"]),
            "needs_human": bool(row["needs_human"]),
        }

    now = datetime.utcnow().isoformat()
    conn = get_connection()
    conn.execute(
        "INSERT INTO conversations (sender_id, messages, needs_human, follow_up_sent, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (sender_id, "[]", 0, 0, now, now),
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
    conn.execute(
        "UPDATE conversations SET messages = ?, updated_at = ? WHERE sender_id = ?",
        (json.dumps(conv["messages"]), now, sender_id),
    )
    conn.commit()
    conn.close()


def set_needs_human(sender_id: str, value: bool):
    now = datetime.utcnow().isoformat()
    conn = get_connection()
    conn.execute(
        "UPDATE conversations SET needs_human = ?, updated_at = ? WHERE sender_id = ?",
        (1 if value else 0, now, sender_id),
    )
    conn.commit()
    conn.close()


def get_conversations_needing_followup(hours: int = 72) -> list[dict]:
    threshold = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT sender_id, messages FROM conversations WHERE needs_human = 0 AND follow_up_sent = 0 AND updated_at < ?",
        (threshold,),
    )
    rows = cursor.fetchall()
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
    conn.execute(
        "UPDATE conversations SET follow_up_sent = 1, updated_at = ? WHERE sender_id = ?",
        (now, sender_id),
    )
    conn.commit()
    conn.close()


def get_all_conversations():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT sender_id, needs_human, updated_at FROM conversations ORDER BY updated_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
