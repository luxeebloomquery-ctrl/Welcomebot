import aiosqlite
from config import DB_PATH, OWNER_ID

_db: aiosqlite.Connection | None = None


async def init_db():
    """Bot start hote hi ye call hota hai. Tables banata hai aur WAL mode on karta hai."""
    global _db
    _db = await aiosqlite.connect(DB_PATH)
    await _db.execute("PRAGMA journal_mode=WAL;")
    await _db.execute(
        """
        CREATE TABLE IF NOT EXISTS welcome_settings (
            chat_id INTEGER PRIMARY KEY,
            chat_name TEXT,
            enabled INTEGER DEFAULT 1,
            text TEXT DEFAULT 'Welcome {mention} to {chatname}! 🎉\nWe are now {count} members.',
            media_file_id TEXT,
            media_type TEXT,
            buttons TEXT,
            parse_mode TEXT DEFAULT 'HTML'
        )
        """
    )
    # Migration: purani DB mein album_json column add karo agar missing hai
    try:
        await _db.execute("ALTER TABLE welcome_settings ADD COLUMN album_json TEXT")
    except Exception:
        pass  # column already exists

    await _db.execute(
        """
        CREATE TABLE IF NOT EXISTS known_groups (
            chat_id INTEGER PRIMARY KEY,
            chat_name TEXT,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    await _db.execute(
        """
        CREATE TABLE IF NOT EXISTS sent_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            message_id INTEGER,
            kind TEXT,
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    await _db.execute(
        """
        CREATE TABLE IF NOT EXISTS broadcast_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            total_groups INTEGER,
            success_count INTEGER,
            fail_count INTEGER,
            had_link INTEGER,
            started_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    await _db.execute(
        """
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            name TEXT,
            text TEXT,
            media_type TEXT,
            media_file_id TEXT,
            album_json TEXT,
            buttons TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(chat_id, name)
        )
        """
    )
    # Migration: random_welcome column (0/1 toggle)
    try:
        await _db.execute("ALTER TABLE welcome_settings ADD COLUMN random_welcome INTEGER DEFAULT 0")
    except Exception:
        pass
    # Migration: auto-delete (seconds, 0 = off) aur welcome delay (seconds)
    try:
        await _db.execute("ALTER TABLE welcome_settings ADD COLUMN auto_delete_seconds INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        await _db.execute("ALTER TABLE welcome_settings ADD COLUMN welcome_delay_seconds INTEGER DEFAULT 0")
    except Exception:
        pass
    await _db.execute(
        """
        CREATE TABLE IF NOT EXISTS goodbye_settings (
            chat_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0,
            text TEXT DEFAULT 'Goodbye {first}, we will miss you! 👋',
            media_file_id TEXT,
            media_type TEXT,
            buttons TEXT
        )
        """
    )
    await _db.execute(
        """
        CREATE TABLE IF NOT EXISTS owners (
            user_id INTEGER PRIMARY KEY,
            added_by INTEGER,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    await _db.execute(
        """
        CREATE TABLE IF NOT EXISTS owner_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # Super-owner (config.py OWNER_ID) hamesha owners list mein rahega
    await _db.execute("INSERT OR IGNORE INTO owners (user_id, added_by) VALUES (?, ?)", (OWNER_ID, OWNER_ID))

    # Migration: clean service messages, welcome card, theme
    for col, coltype in [
        ("clean_service", "INTEGER DEFAULT 0"),
        ("welcome_card", "INTEGER DEFAULT 0"),
        ("welcome_theme", "TEXT DEFAULT 'blue'"),
    ]:
        try:
            await _db.execute(f"ALTER TABLE welcome_settings ADD COLUMN {col} {coltype}")
        except Exception:
            pass

    await _db.execute(
        """
        CREATE TABLE IF NOT EXISTS scheduled_broadcasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_chat_id INTEGER,
            source_message_id INTEGER,
            run_at TEXT,
            created_by INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    await _db.execute(
        """
        CREATE TABLE IF NOT EXISTS template_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            template_name TEXT,
            start_at TEXT,
            end_at TEXT,
            applied INTEGER DEFAULT 0,
            reverted INTEGER DEFAULT 0
        )
        """
    )
    await _db.commit()


def get_db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("Database initialize nahi hui. init_db() pehle call karo.")
    return _db


async def close_db():
    if _db is not None:
        await _db.close()


# ---------- Welcome settings helpers ----------

DEFAULT_TEXT = "Welcome {mention} to {chatname}! 🎉\nWe are now {count} members."


async def ensure_chat_row(chat_id: int, chat_name: str = ""):
    db = get_db()
    await db.execute(
        "INSERT OR IGNORE INTO welcome_settings (chat_id, chat_name) VALUES (?, ?)",
        (chat_id, chat_name),
    )
    await db.execute(
        "INSERT OR IGNORE INTO known_groups (chat_id, chat_name) VALUES (?, ?)",
        (chat_id, chat_name),
    )
    # keep chat_name fresh
    await db.execute(
        "UPDATE welcome_settings SET chat_name = ? WHERE chat_id = ?", (chat_name, chat_id)
    )
    await db.execute(
        "UPDATE known_groups SET chat_name = ? WHERE chat_id = ?", (chat_name, chat_id)
    )
    await db.commit()


async def get_settings(chat_id: int) -> dict:
    db = get_db()
    cursor = await db.execute(
        "SELECT chat_id, chat_name, enabled, text, media_file_id, media_type, buttons, parse_mode, album_json, "
        "random_welcome, auto_delete_seconds, welcome_delay_seconds, clean_service, welcome_card, welcome_theme "
        "FROM welcome_settings WHERE chat_id = ?",
        (chat_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return {
            "chat_id": chat_id,
            "chat_name": "",
            "enabled": 1,
            "text": DEFAULT_TEXT,
            "media_file_id": None,
            "media_type": None,
            "buttons": None,
            "parse_mode": "HTML",
            "album_json": None,
            "random_welcome": 0,
            "auto_delete_seconds": 0,
            "welcome_delay_seconds": 0,
            "clean_service": 0,
            "welcome_card": 0,
            "welcome_theme": "blue",
        }
    keys = [
        "chat_id", "chat_name", "enabled", "text", "media_file_id", "media_type", "buttons", "parse_mode",
        "album_json", "random_welcome", "auto_delete_seconds", "welcome_delay_seconds",
        "clean_service", "welcome_card", "welcome_theme",
    ]
    return dict(zip(keys, row))


async def set_enabled(chat_id: int, enabled: bool):
    db = get_db()
    await db.execute(
        "UPDATE welcome_settings SET enabled = ? WHERE chat_id = ?", (1 if enabled else 0, chat_id)
    )
    await db.commit()


async def set_welcome_text(chat_id: int, text: str, buttons_json: str | None):
    db = get_db()
    await db.execute(
        "UPDATE welcome_settings SET text = ?, buttons = ?, media_file_id = NULL, media_type = NULL, "
        "album_json = NULL WHERE chat_id = ?",
        (text, buttons_json, chat_id),
    )
    await db.commit()


async def set_welcome_media(chat_id: int, text: str, buttons_json: str | None, file_id: str, media_type: str):
    db = get_db()
    await db.execute(
        "UPDATE welcome_settings SET text = ?, buttons = ?, media_file_id = ?, media_type = ?, "
        "album_json = NULL WHERE chat_id = ?",
        (text, buttons_json, file_id, media_type, chat_id),
    )
    await db.commit()


async def reset_welcome(chat_id: int):
    db = get_db()
    await db.execute(
        "UPDATE welcome_settings SET text = ?, media_file_id = NULL, media_type = NULL, buttons = NULL, "
        "album_json = NULL WHERE chat_id = ?",
        (DEFAULT_TEXT, chat_id),
    )
    await db.commit()


async def set_welcome_album(chat_id: int, album_json: str, text: str, buttons_json: str | None):
    """Album save karta hai aur single-media fields clear karta hai (dono ek sath nahi chalte)."""
    db = get_db()
    await db.execute(
        "UPDATE welcome_settings SET album_json = ?, text = ?, buttons = ?, media_file_id = NULL, media_type = NULL "
        "WHERE chat_id = ?",
        (album_json, text, buttons_json, chat_id),
    )
    await db.commit()


async def clear_album(chat_id: int):
    db = get_db()
    await db.execute("UPDATE welcome_settings SET album_json = NULL WHERE chat_id = ?", (chat_id,))
    await db.commit()


async def get_member_count_placeholder(bot, chat_id: int) -> int:
    try:
        return await bot.get_chat_member_count(chat_id)
    except Exception:
        return 0


# ---------- Owner Panel helpers ----------

async def get_all_groups() -> list[dict]:
    db = get_db()
    cursor = await db.execute("SELECT chat_id, chat_name, added_at FROM known_groups ORDER BY added_at DESC")
    rows = await cursor.fetchall()
    return [{"chat_id": r[0], "chat_name": r[1], "added_at": r[2]} for r in rows]


async def get_recent_groups(limit: int = 10) -> list[dict]:
    groups = await get_all_groups()
    return groups[:limit]


async def get_group_count() -> int:
    db = get_db()
    cursor = await db.execute("SELECT COUNT(*) FROM known_groups")
    row = await cursor.fetchone()
    return row[0] if row else 0


async def remove_group(chat_id: int):
    """Bot ko kick karne par ya broadcast fail hone par group remove karta hai."""
    db = get_db()
    await db.execute("DELETE FROM known_groups WHERE chat_id = ?", (chat_id,))
    await db.commit()


async def log_sent_message(chat_id: int, message_id: int, kind: str = "broadcast"):
    db = get_db()
    await db.execute(
        "INSERT INTO sent_messages (chat_id, message_id, kind) VALUES (?, ?, ?)",
        (chat_id, message_id, kind),
    )
    await db.commit()


async def get_sent_messages_last_hours(chat_id: int, hours: int = 48) -> list[dict]:
    db = get_db()
    cursor = await db.execute(
        "SELECT id, message_id FROM sent_messages "
        "WHERE chat_id = ? AND sent_at >= datetime('now', ?)",
        (chat_id, f"-{hours} hours"),
    )
    rows = await cursor.fetchall()
    return [{"id": r[0], "message_id": r[1]} for r in rows]


async def delete_sent_message_record(record_id: int):
    db = get_db()
    await db.execute("DELETE FROM sent_messages WHERE id = ?", (record_id,))
    await db.commit()


async def log_broadcast(total: int, success: int, fail: int, had_link: bool):
    db = get_db()
    await db.execute(
        "INSERT INTO broadcast_log (total_groups, success_count, fail_count, had_link) VALUES (?, ?, ?, ?)",
        (total, success, fail, 1 if had_link else 0),
    )
    await db.commit()


async def get_broadcast_history(limit: int = 5) -> list[dict]:
    db = get_db()
    cursor = await db.execute(
        "SELECT total_groups, success_count, fail_count, had_link, started_at "
        "FROM broadcast_log ORDER BY started_at DESC LIMIT ?",
        (limit,),
    )
    rows = await cursor.fetchall()
    return [
        {"total": r[0], "success": r[1], "fail": r[2], "had_link": bool(r[3]), "started_at": r[4]}
        for r in rows
    ]


# ---------- Templates ----------

async def save_template(chat_id: int, name: str):
    """Current welcome config ko naam se template ki tarah save karta hai (overwrite agar same naam hai)."""
    db = get_db()
    settings = await get_settings(chat_id)
    await db.execute(
        "INSERT INTO templates (chat_id, name, text, media_type, media_file_id, album_json, buttons) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(chat_id, name) DO UPDATE SET "
        "text=excluded.text, media_type=excluded.media_type, media_file_id=excluded.media_file_id, "
        "album_json=excluded.album_json, buttons=excluded.buttons",
        (chat_id, name, settings["text"], settings["media_type"], settings["media_file_id"],
         settings["album_json"], settings["buttons"]),
    )
    await db.commit()


async def list_templates(chat_id: int) -> list[dict]:
    db = get_db()
    cursor = await db.execute(
        "SELECT name, created_at FROM templates WHERE chat_id = ? ORDER BY created_at DESC", (chat_id,)
    )
    rows = await cursor.fetchall()
    return [{"name": r[0], "created_at": r[1]} for r in rows]


async def get_template(chat_id: int, name: str) -> dict | None:
    db = get_db()
    cursor = await db.execute(
        "SELECT text, media_type, media_file_id, album_json, buttons FROM templates "
        "WHERE chat_id = ? AND name = ?",
        (chat_id, name),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return {"text": row[0], "media_type": row[1], "media_file_id": row[2], "album_json": row[3], "buttons": row[4]}


async def load_template(chat_id: int, name: str) -> bool:
    """Template ko active welcome bana deta hai. Returns False agar template nahi mila."""
    tpl = await get_template(chat_id, name)
    if tpl is None:
        return False
    db = get_db()
    await db.execute(
        "UPDATE welcome_settings SET text=?, media_type=?, media_file_id=?, album_json=?, buttons=? "
        "WHERE chat_id=?",
        (tpl["text"], tpl["media_type"], tpl["media_file_id"], tpl["album_json"], tpl["buttons"], chat_id),
    )
    await db.commit()
    return True


async def delete_template(chat_id: int, name: str) -> bool:
    db = get_db()
    cursor = await db.execute("DELETE FROM templates WHERE chat_id = ? AND name = ?", (chat_id, name))
    await db.commit()
    return cursor.rowcount > 0


async def get_random_template(chat_id: int) -> dict | None:
    db = get_db()
    cursor = await db.execute(
        "SELECT text, media_type, media_file_id, album_json, buttons FROM templates "
        "WHERE chat_id = ? ORDER BY RANDOM() LIMIT 1",
        (chat_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return {"text": row[0], "media_type": row[1], "media_file_id": row[2], "album_json": row[3], "buttons": row[4]}


async def set_random_mode(chat_id: int, enabled: bool):
    db = get_db()
    await db.execute("UPDATE welcome_settings SET random_welcome = ? WHERE chat_id = ?", (1 if enabled else 0, chat_id))
    await db.commit()


# ---------- Auto-delete / Delay ----------

async def set_auto_delete(chat_id: int, seconds: int):
    db = get_db()
    await db.execute("UPDATE welcome_settings SET auto_delete_seconds = ? WHERE chat_id = ?", (seconds, chat_id))
    await db.commit()


async def set_welcome_delay(chat_id: int, seconds: int):
    db = get_db()
    await db.execute("UPDATE welcome_settings SET welcome_delay_seconds = ? WHERE chat_id = ?", (seconds, chat_id))
    await db.commit()


# ---------- Media / Button editor ----------

async def update_album_json(chat_id: int, album_json: str | None):
    db = get_db()
    await db.execute("UPDATE welcome_settings SET album_json = ? WHERE chat_id = ?", (album_json, chat_id))
    await db.commit()


async def update_buttons_json(chat_id: int, buttons_json: str | None):
    db = get_db()
    await db.execute("UPDATE welcome_settings SET buttons = ? WHERE chat_id = ?", (buttons_json, chat_id))
    await db.commit()


# ---------- Goodbye System ----------

DEFAULT_GOODBYE = "Goodbye {first}, we will miss you! 👋"


async def ensure_goodbye_row(chat_id: int):
    db = get_db()
    await db.execute("INSERT OR IGNORE INTO goodbye_settings (chat_id) VALUES (?)", (chat_id,))
    await db.commit()


async def get_goodbye_settings(chat_id: int) -> dict:
    db = get_db()
    cursor = await db.execute(
        "SELECT enabled, text, media_file_id, media_type, buttons FROM goodbye_settings WHERE chat_id = ?",
        (chat_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return {"enabled": 0, "text": DEFAULT_GOODBYE, "media_file_id": None, "media_type": None, "buttons": None}
    keys = ["enabled", "text", "media_file_id", "media_type", "buttons"]
    return dict(zip(keys, row))


async def set_goodbye_enabled(chat_id: int, enabled: bool):
    await ensure_goodbye_row(chat_id)
    db = get_db()
    await db.execute("UPDATE goodbye_settings SET enabled = ? WHERE chat_id = ?", (1 if enabled else 0, chat_id))
    await db.commit()


async def set_goodbye_text(chat_id: int, text: str, buttons_json: str | None):
    await ensure_goodbye_row(chat_id)
    db = get_db()
    await db.execute(
        "UPDATE goodbye_settings SET text = ?, buttons = ?, media_file_id = NULL, media_type = NULL WHERE chat_id = ?",
        (text, buttons_json, chat_id),
    )
    await db.commit()


async def set_goodbye_media(chat_id: int, text: str, buttons_json: str | None, file_id: str, media_type: str):
    await ensure_goodbye_row(chat_id)
    db = get_db()
    await db.execute(
        "UPDATE goodbye_settings SET text = ?, buttons = ?, media_file_id = ?, media_type = ? WHERE chat_id = ?",
        (text, buttons_json, file_id, media_type, chat_id),
    )
    await db.commit()


# ---------- Clean service messages / Welcome Card / Theme ----------

async def set_clean_service(chat_id: int, enabled: bool):
    db = get_db()
    await db.execute("UPDATE welcome_settings SET clean_service = ? WHERE chat_id = ?", (1 if enabled else 0, chat_id))
    await db.commit()


async def set_welcome_card(chat_id: int, enabled: bool):
    db = get_db()
    await db.execute("UPDATE welcome_settings SET welcome_card = ? WHERE chat_id = ?", (1 if enabled else 0, chat_id))
    await db.commit()


async def set_welcome_theme(chat_id: int, theme: str):
    db = get_db()
    await db.execute("UPDATE welcome_settings SET welcome_theme = ? WHERE chat_id = ?", (theme, chat_id))
    await db.commit()


# ---------- Multi-owner support ----------

async def is_owner(user_id: int) -> bool:
    db = get_db()
    cursor = await db.execute("SELECT 1 FROM owners WHERE user_id = ?", (user_id,))
    return (await cursor.fetchone()) is not None


async def add_owner(user_id: int, added_by: int):
    db = get_db()
    await db.execute("INSERT OR IGNORE INTO owners (user_id, added_by) VALUES (?, ?)", (user_id, added_by))
    await db.commit()


async def remove_owner(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return False  # super-owner kabhi remove nahi ho sakta
    db = get_db()
    cursor = await db.execute("DELETE FROM owners WHERE user_id = ?", (user_id,))
    await db.commit()
    return cursor.rowcount > 0


async def list_owners() -> list[int]:
    db = get_db()
    cursor = await db.execute("SELECT user_id FROM owners ORDER BY added_at")
    rows = await cursor.fetchall()
    return [r[0] for r in rows]


# ---------- Owner action logs ----------

async def log_owner_action(user_id: int, action: str, details: str = ""):
    db = get_db()
    await db.execute(
        "INSERT INTO owner_logs (user_id, action, details) VALUES (?, ?, ?)", (user_id, action, details)
    )
    await db.commit()


async def get_owner_logs(limit: int = 15) -> list[dict]:
    db = get_db()
    cursor = await db.execute(
        "SELECT user_id, action, details, created_at FROM owner_logs ORDER BY created_at DESC LIMIT ?", (limit,)
    )
    rows = await cursor.fetchall()
    return [{"user_id": r[0], "action": r[1], "details": r[2], "created_at": r[3]} for r in rows]


# ---------- Backup / Restore / Clone ----------

async def export_chat_config(chat_id: int) -> dict:
    """Ek group ki poori welcome+goodbye+templates config JSON-safe dict mein deta hai."""
    welcome = await get_settings(chat_id)
    goodbye = await get_goodbye_settings(chat_id)
    templates = []
    for t in await list_templates(chat_id):
        tpl = await get_template(chat_id, t["name"])
        templates.append({"name": t["name"], **tpl})

    return {
        "welcome": {k: v for k, v in welcome.items() if k not in ("chat_id", "chat_name")},
        "goodbye": goodbye,
        "templates": templates,
    }


async def import_chat_config(chat_id: int, data: dict):
    """export_chat_config se aayi dict ko wapas DB mein restore karta hai."""
    db = get_db()
    w = data.get("welcome", {})
    await db.execute(
        "UPDATE welcome_settings SET text=?, media_file_id=?, media_type=?, buttons=?, album_json=?, "
        "enabled=?, random_welcome=?, auto_delete_seconds=?, welcome_delay_seconds=?, clean_service=?, "
        "welcome_card=?, welcome_theme=? WHERE chat_id=?",
        (
            w.get("text", DEFAULT_TEXT), w.get("media_file_id"), w.get("media_type"), w.get("buttons"),
            w.get("album_json"), w.get("enabled", 1), w.get("random_welcome", 0),
            w.get("auto_delete_seconds", 0), w.get("welcome_delay_seconds", 0),
            w.get("clean_service", 0), w.get("welcome_card", 0), w.get("welcome_theme", "blue"),
            chat_id,
        ),
    )
    g = data.get("goodbye", {})
    if g:
        await ensure_goodbye_row(chat_id)
        await db.execute(
            "UPDATE goodbye_settings SET enabled=?, text=?, media_file_id=?, media_type=?, buttons=? WHERE chat_id=?",
            (g.get("enabled", 0), g.get("text", DEFAULT_GOODBYE), g.get("media_file_id"),
             g.get("media_type"), g.get("buttons"), chat_id),
        )
    await db.commit()

    for tpl in data.get("templates", []):
        name = tpl.get("name")
        if not name:
            continue
        await db.execute(
            "INSERT INTO templates (chat_id, name, text, media_type, media_file_id, album_json, buttons) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(chat_id, name) DO UPDATE SET "
            "text=excluded.text, media_type=excluded.media_type, media_file_id=excluded.media_file_id, "
            "album_json=excluded.album_json, buttons=excluded.buttons",
            (chat_id, name, tpl.get("text"), tpl.get("media_type"), tpl.get("media_file_id"),
             tpl.get("album_json"), tpl.get("buttons")),
        )
    await db.commit()


async def export_all_config() -> dict:
    """Owner ke liye: saare groups ka poora backup."""
    groups = await get_all_groups()
    data = {"groups": []}
    for g in groups:
        cfg = await export_chat_config(g["chat_id"])
        data["groups"].append({"chat_id": g["chat_id"], "chat_name": g["chat_name"], **cfg})
    return data


async def import_all_config(data: dict):
    for g in data.get("groups", []):
        chat_id = g.get("chat_id")
        if chat_id is None:
            continue
        await ensure_chat_row(chat_id, g.get("chat_name", ""))
        await import_chat_config(chat_id, g)


# ---------- Broadcast Scheduler ----------

async def add_scheduled_broadcast(source_chat_id: int, source_message_id: int, run_at_iso: str, created_by: int):
    db = get_db()
    await db.execute(
        "INSERT INTO scheduled_broadcasts (source_chat_id, source_message_id, run_at, created_by) "
        "VALUES (?, ?, ?, ?)",
        (source_chat_id, source_message_id, run_at_iso, created_by),
    )
    await db.commit()


async def get_due_broadcasts(now_iso: str) -> list[dict]:
    db = get_db()
    cursor = await db.execute(
        "SELECT id, source_chat_id, source_message_id, created_by FROM scheduled_broadcasts "
        "WHERE status = 'pending' AND run_at <= ?",
        (now_iso,),
    )
    rows = await cursor.fetchall()
    return [{"id": r[0], "source_chat_id": r[1], "source_message_id": r[2], "created_by": r[3]} for r in rows]


async def mark_broadcast_done(job_id: int):
    db = get_db()
    await db.execute("UPDATE scheduled_broadcasts SET status = 'done' WHERE id = ?", (job_id,))
    await db.commit()


async def list_pending_broadcasts() -> list[dict]:
    db = get_db()
    cursor = await db.execute(
        "SELECT id, run_at, created_by FROM scheduled_broadcasts WHERE status = 'pending' ORDER BY run_at"
    )
    rows = await cursor.fetchall()
    return [{"id": r[0], "run_at": r[1], "created_by": r[2]} for r in rows]


async def cancel_scheduled_broadcast(job_id: int) -> bool:
    db = get_db()
    cursor = await db.execute(
        "UPDATE scheduled_broadcasts SET status = 'cancelled' WHERE id = ? AND status = 'pending'", (job_id,)
    )
    await db.commit()
    return cursor.rowcount > 0


# ---------- Scheduled Welcome Templates ----------

async def add_template_schedule(chat_id: int, template_name: str, start_at_iso: str, end_at_iso: str):
    db = get_db()
    await db.execute(
        "INSERT INTO template_schedules (chat_id, template_name, start_at, end_at) VALUES (?, ?, ?, ?)",
        (chat_id, template_name, start_at_iso, end_at_iso),
    )
    await db.commit()


async def get_due_template_starts(now_iso: str) -> list[dict]:
    db = get_db()
    cursor = await db.execute(
        "SELECT id, chat_id, template_name FROM template_schedules "
        "WHERE applied = 0 AND start_at <= ? AND end_at > ?",
        (now_iso, now_iso),
    )
    rows = await cursor.fetchall()
    return [{"id": r[0], "chat_id": r[1], "template_name": r[2]} for r in rows]


async def get_due_template_ends(now_iso: str) -> list[dict]:
    db = get_db()
    cursor = await db.execute(
        "SELECT id, chat_id, template_name FROM template_schedules "
        "WHERE applied = 1 AND reverted = 0 AND end_at <= ?",
        (now_iso,),
    )
    rows = await cursor.fetchall()
    return [{"id": r[0], "chat_id": r[1], "template_name": r[2]} for r in rows]


async def mark_schedule_applied(schedule_id: int):
    db = get_db()
    await db.execute("UPDATE template_schedules SET applied = 1 WHERE id = ?", (schedule_id,))
    await db.commit()


async def mark_schedule_reverted(schedule_id: int):
    db = get_db()
    await db.execute("UPDATE template_schedules SET reverted = 1 WHERE id = ?", (schedule_id,))
    await db.commit()


async def list_template_schedules(chat_id: int) -> list[dict]:
    db = get_db()
    cursor = await db.execute(
        "SELECT template_name, start_at, end_at, applied FROM template_schedules "
        "WHERE chat_id = ? ORDER BY start_at",
        (chat_id,),
    )
    rows = await cursor.fetchall()
    return [{"template_name": r[0], "start_at": r[1], "end_at": r[2], "applied": r[3]} for r in rows]
