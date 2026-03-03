from datetime import datetime, date, timedelta
import asyncio, os, sqlite3
from aiogram import Bot

from database import database as db

database = db()

# sqlite file where bot keeps local state (users, reminders)
SQLITE_PATH = "local_storage.sql"

# --- local storage helpers --------------------------------------------------

def _ensure_reminder_table():
    """Create local tables for sent reminders and target chat."""
    conn = sqlite3.connect(SQLITE_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reminders_sent (
            block_id INTEGER,
            remind_type TEXT,
            remind_date DATE,
            PRIMARY KEY (block_id, remind_type, remind_date)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reminder_target (
            chat_id INTEGER PRIMARY KEY,
            thread_id INTEGER
        )
        """
    )
    conn.commit()
    cur.close()
    conn.close()


def _set_reminder_target(chat_id: int, thread_id: int):
    conn = sqlite3.connect(SQLITE_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO reminder_target (chat_id, thread_id) VALUES (?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET thread_id = excluded.thread_id",
        (chat_id, thread_id),
    )
    conn.commit()
    cur.close()
    conn.close()


def _get_reminder_target():
    conn = sqlite3.connect(SQLITE_PATH)
    cur = conn.cursor()
    cur.execute("SELECT chat_id, thread_id FROM reminder_target LIMIT 1")
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return row[0], row[1] or 0
    return 0, 0


def _record_sent(block_id: int, rtype: str, when: date):
    conn = sqlite3.connect(SQLITE_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO reminders_sent (block_id, remind_type, remind_date) VALUES (?, ?, ?)",
        (block_id, rtype, when),
    )
    conn.commit()
    cur.close()
    conn.close()

def _compose_reminder_text(block: dict, rtype: str) -> str:
    ename = block.get('event_name', 'мероприятие')
    bname = block.get('name', 'этап')
    if rtype == 'start':
        return f"🔔 Этап «{bname}» мероприятия «{ename}» начался сегодня."
    if rtype == 'end_minus_7':
        return f"🔔 До окончания этапа «{bname}» мероприятия «{ename}» осталось 7 дней."
    if rtype == 'end_minus_3':
        return f"🔔 До окончания этапа «{bname}» мероприятия «{ename}» осталось 3 дня."
    if rtype == 'end_minus_1':
        return f"🔔 До окончания этапа «{bname}» мероприятия «{ename}» остался 1 день."
    return "🔔 Напоминание по этапу."

async def _check_and_send(bot: Bot):
    target_chat, target_thread = _get_reminder_target()
    if target_chat == 0:
        return
    today = date.today()
    with database.get_cursor() as cur:
        cur.execute("""
            SELECT eb.*, ev.name AS event_name
            FROM event_blocks eb
            LEFT JOIN events ev ON ev.id = eb.event_id
        """)
        cols = [d[0] for d in cur.description]
        blocks = [dict(zip(cols, row)) for row in cur.fetchall()]

    for b in blocks:
        bid = b['id']
        start = b['start_date'].date() if isinstance(b['start_date'], datetime) else b['start_date']
        end = b['end_date'].date() if isinstance(b['end_date'], datetime) else b['end_date']
        checks = [
            ('start', start),
            ('end_minus_7', end - timedelta(days=7)),
            ('end_minus_3', end - timedelta(days=3)),
            ('end_minus_1', end),
        ]
        for rtype, rdate in checks:
            if rdate != today:
                continue
            conn = sqlite3.connect(SQLITE_PATH)
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM reminders_sent WHERE block_id=? AND remind_type=? AND remind_date=?",
                (bid, rtype, rdate),
            )
            if cur.fetchone():
                cur.close()
                conn.close()
                continue
            cur.close()
            conn.close()
            text = _compose_reminder_text(b, rtype)
            try:
                await bot.send_message(
                    chat_id=target_chat,
                    text=text,
                    message_thread_id=target_thread or None,
                )
            except Exception:
                pass
            _record_sent(bid, rtype, rdate)


async def reminder_worker(bot: Bot):
    _ensure_reminder_table()
    while True:
        try:
            await _check_and_send(bot)
        except Exception:
            pass
        await asyncio.sleep(6 * 3600)
