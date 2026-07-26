"""
Persistent storage for the bot, backed by SQLite (via aiosqlite).
One file, zero external services - good enough until you outgrow it,
at which point the same function signatures can move to Postgres.
"""

import aiosqlite
from datetime import datetime, timezone

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    balance INTEGER DEFAULT 100,
    bank INTEGER DEFAULT 0,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    hunter_rank TEXT DEFAULT 'E',
    awakened INTEGER DEFAULT 0,
    stat_points INTEGER DEFAULT 0,
    strength INTEGER DEFAULT 10,
    agility INTEGER DEFAULT 10,
    last_daily TEXT,
    last_work TEXT,
    last_hunt TEXT,
    premium INTEGER DEFAULT 0,
    premium_until TEXT,
    last_message_at TEXT,
    bio TEXT,
    married_to INTEGER,
    reputation INTEGER DEFAULT 0,
    last_rep TEXT,
    PRIMARY KEY (user_id, guild_id)
);

CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    moderator_id INTEGER NOT NULL,
    reason TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS guild_config (
    guild_id INTEGER PRIMARY KEY,
    prefix TEXT,
    log_channel_id INTEGER,
    welcome_channel_id INTEGER,
    welcome_message TEXT,
    goodbye_channel_id INTEGER,
    goodbye_message TEXT,
    autorole_id INTEGER,
    xp_min INTEGER DEFAULT 5,
    xp_max INTEGER DEFAULT 15,
    starboard_channel_id INTEGER,
    starboard_threshold INTEGER DEFAULT 3,
    verification_enabled INTEGER DEFAULT 0,
    unverified_role_id INTEGER,
    verified_role_id INTEGER,
    raid_mode INTEGER DEFAULT 0,
    confess_channel_id INTEGER,
    antilink INTEGER DEFAULT 0,
    anticaps INTEGER DEFAULT 0,
    antiinvite INTEGER DEFAULT 0,
    antimention_limit INTEGER DEFAULT 0,
    ticket_category_id INTEGER,
    support_role_id INTEGER,
    suggestions_channel_id INTEGER
);

CREATE TABLE IF NOT EXISTS wallets (
    user_id INTEGER NOT NULL,
    coin TEXT NOT NULL,
    address TEXT NOT NULL,
    PRIMARY KEY (user_id, coin)
);

CREATE TABLE IF NOT EXISTS level_roles (
    guild_id INTEGER NOT NULL,
    level INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    PRIMARY KEY (guild_id, level)
);

CREATE TABLE IF NOT EXISTS giveaways (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    message_id INTEGER,
    prize TEXT,
    winner_count INTEGER DEFAULT 1,
    host_id INTEGER,
    end_time TEXT,
    ended INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS afk (
    user_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    reason TEXT,
    since TEXT,
    PRIMARY KEY (user_id, guild_id)
);

CREATE TABLE IF NOT EXISTS tags (
    guild_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    created_by INTEGER,
    created_at TEXT,
    PRIMARY KEY (guild_id, name)
);

CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    added_by INTEGER,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS starboard_posts (
    original_message_id INTEGER PRIMARY KEY,
    starboard_message_id INTEGER,
    guild_id INTEGER NOT NULL,
    author_id INTEGER,
    star_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS confessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    author_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS invite_stats (
    guild_id INTEGER NOT NULL,
    inviter_id INTEGER NOT NULL,
    uses INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, inviter_id)
);

CREATE TABLE IF NOT EXISTS filtered_words (
    guild_id INTEGER NOT NULL,
    word TEXT NOT NULL,
    PRIMARY KEY (guild_id, word)
);

CREATE TABLE IF NOT EXISTS tickets (
    channel_id INTEGER PRIMARY KEY,
    guild_id INTEGER NOT NULL,
    opener_id INTEGER NOT NULL,
    status TEXT DEFAULT 'open',
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    author_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    message_id INTEGER,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS blacklist (
    user_id INTEGER PRIMARY KEY,
    reason TEXT,
    added_at TEXT
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    guild_id INTEGER,
    coin TEXT NOT NULL,
    amount_usd REAL,
    deposit_address TEXT,
    tx_hash TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT,
    confirmed_at TEXT
);
"""


async def init_db():
    import os
    os.makedirs(config.DATA_DIR, exist_ok=True)
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


def _now():
    return datetime.now(timezone.utc).isoformat()


# ---------- users / economy / leveling ----------

async def get_user(user_id: int, guild_id: int) -> dict:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM users WHERE user_id = ? AND guild_id = ?", (user_id, guild_id)
        )
        row = await cur.fetchone()
        if row:
            return dict(row)
        await db.execute(
            "INSERT INTO users (user_id, guild_id) VALUES (?, ?)", (user_id, guild_id)
        )
        await db.commit()
        cur = await db.execute(
            "SELECT * FROM users WHERE user_id = ? AND guild_id = ?", (user_id, guild_id)
        )
        row = await cur.fetchone()
        return dict(row)


async def update_user(user_id: int, guild_id: int, **fields):
    if not fields:
        return
    await get_user(user_id, guild_id)  # ensure row exists
    cols = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [user_id, guild_id]
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            f"UPDATE users SET {cols} WHERE user_id = ? AND guild_id = ?", values
        )
        await db.commit()


async def add_balance(user_id: int, guild_id: int, amount: int):
    user = await get_user(user_id, guild_id)
    await update_user(user_id, guild_id, balance=user["balance"] + amount)
    return user["balance"] + amount


async def add_xp(user_id: int, guild_id: int, amount: int):
    user = await get_user(user_id, guild_id)
    new_xp = user["xp"] + amount
    new_level = user["level"]
    leveled_up = False
    # simple curve: next level needs level*100 xp
    while new_xp >= new_level * 100:
        new_xp -= new_level * 100
        new_level += 1
        leveled_up = True
    await update_user(user_id, guild_id, xp=new_xp, level=new_level)
    return new_level, leveled_up


async def leaderboard(guild_id: int, by: str = "balance", limit: int = 10):
    assert by in ("balance", "xp", "level", "reputation")
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            f"SELECT user_id, {by} FROM users WHERE guild_id = ? ORDER BY {by} DESC LIMIT ?",
            (guild_id, limit),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def is_user_premium(user_id: int, guild_id: int) -> bool:
    user = await get_user(user_id, guild_id)
    if not user["premium"]:
        return False
    if user["premium_until"] is None:
        return True  # lifetime
    return datetime.fromisoformat(user["premium_until"]) > datetime.now(timezone.utc)


async def grant_premium(user_id: int, guild_id: int, until: str | None = None):
    await update_user(user_id, guild_id, premium=1, premium_until=until)


# ---------- warnings ----------

async def add_warning(user_id: int, guild_id: int, moderator_id: int, reason: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO warnings (user_id, guild_id, moderator_id, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, guild_id, moderator_id, reason, _now()),
        )
        await db.commit()


async def get_warnings(user_id: int, guild_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM warnings WHERE user_id = ? AND guild_id = ? ORDER BY id",
            (user_id, guild_id),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def clear_warnings(user_id: int, guild_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "DELETE FROM warnings WHERE user_id = ? AND guild_id = ?", (user_id, guild_id)
        )
        await db.commit()


# ---------- guild config ----------

async def get_guild_config(guild_id: int) -> dict:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,))
        row = await cur.fetchone()
        if row:
            return dict(row)
        await db.execute("INSERT INTO guild_config (guild_id) VALUES (?)", (guild_id,))
        await db.commit()
        cur = await db.execute("SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,))
        row = await cur.fetchone()
        return dict(row)


async def set_guild_config(guild_id: int, **fields):
    if not fields:
        return
    await get_guild_config(guild_id)
    cols = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [guild_id]
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            f"UPDATE guild_config SET {cols} WHERE guild_id = ?", values
        )
        await db.commit()


# ---------- wallets ----------

async def link_wallet(user_id: int, coin: str, address: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO wallets (user_id, coin, address) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, coin) DO UPDATE SET address = excluded.address",
            (user_id, coin, address),
        )
        await db.commit()


async def unlink_wallet(user_id: int, coin: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "DELETE FROM wallets WHERE user_id = ? AND coin = ?", (user_id, coin)
        )
        await db.commit()


async def get_wallets(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM wallets WHERE user_id = ?", (user_id,))
        rows = await cur.fetchall()
        return {r["coin"]: r["address"] for r in rows}


# ---------- blacklist ----------

async def add_blacklist(user_id: int, reason: str = "No reason given"):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO blacklist (user_id, reason, added_at) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET reason = excluded.reason",
            (user_id, reason, _now()),
        )
        await db.commit()


async def remove_blacklist(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("DELETE FROM blacklist WHERE user_id = ?", (user_id,))
        await db.commit()


async def is_blacklisted(user_id: int) -> bool:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM blacklist WHERE user_id = ?", (user_id,))
        return await cur.fetchone() is not None


async def list_blacklist():
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM blacklist")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ---------- payments ----------

async def create_payment(user_id: int, guild_id: int, coin: str, amount_usd: float, address: str) -> int:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO payments (user_id, guild_id, coin, amount_usd, deposit_address, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'pending', ?)",
            (user_id, guild_id, coin, amount_usd, address, _now()),
        )
        await db.commit()
        return cur.lastrowid


async def confirm_payment(payment_id: int, tx_hash: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE payments SET status = 'confirmed', tx_hash = ?, confirmed_at = ? WHERE id = ?",
            (tx_hash, _now(), payment_id),
        )
        await db.commit()


async def get_pending_payments(user_id: int, coin: str | None = None):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if coin:
            cur = await db.execute(
                "SELECT * FROM payments WHERE user_id = ? AND coin = ? AND status = 'pending' "
                "ORDER BY id DESC",
                (user_id, coin),
            )
        else:
            cur = await db.execute(
                "SELECT * FROM payments WHERE user_id = ? AND status = 'pending' ORDER BY id DESC",
                (user_id,),
            )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_payment_history(user_id: int, limit: int = 10):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM payments WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ---------- level roles ----------

async def set_level_role(guild_id: int, level: int, role_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO level_roles (guild_id, level, role_id) VALUES (?, ?, ?) "
            "ON CONFLICT(guild_id, level) DO UPDATE SET role_id = excluded.role_id",
            (guild_id, level, role_id),
        )
        await db.commit()


async def remove_level_role(guild_id: int, level: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "DELETE FROM level_roles WHERE guild_id = ? AND level = ?", (guild_id, level)
        )
        await db.commit()


async def get_level_roles(guild_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM level_roles WHERE guild_id = ? ORDER BY level", (guild_id,)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_level_role_for(guild_id: int, level: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM level_roles WHERE guild_id = ? AND level = ?", (guild_id, level)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


# ---------- giveaways ----------

async def create_giveaway(guild_id: int, channel_id: int, prize: str, winner_count: int, host_id: int, end_time: str) -> int:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO giveaways (guild_id, channel_id, prize, winner_count, host_id, end_time, ended) "
            "VALUES (?, ?, ?, ?, ?, ?, 0)",
            (guild_id, channel_id, prize, winner_count, host_id, end_time),
        )
        await db.commit()
        return cur.lastrowid


async def set_giveaway_message(giveaway_id: int, message_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE giveaways SET message_id = ? WHERE id = ?", (message_id, giveaway_id)
        )
        await db.commit()


async def end_giveaway(giveaway_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("UPDATE giveaways SET ended = 1 WHERE id = ?", (giveaway_id,))
        await db.commit()


async def get_giveaway(giveaway_id: int = None, message_id: int = None):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if message_id:
            cur = await db.execute("SELECT * FROM giveaways WHERE message_id = ?", (message_id,))
        else:
            cur = await db.execute("SELECT * FROM giveaways WHERE id = ?", (giveaway_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_due_giveaways():
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM giveaways WHERE ended = 0 AND end_time <= ? AND message_id IS NOT NULL",
            (_now(),),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_active_giveaways(guild_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM giveaways WHERE guild_id = ? AND ended = 0 ORDER BY end_time", (guild_id,)
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ---------- afk / last seen ----------

async def set_afk(user_id: int, guild_id: int, reason: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO afk (user_id, guild_id, reason, since) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id, guild_id) DO UPDATE SET reason = excluded.reason, since = excluded.since",
            (user_id, guild_id, reason, _now()),
        )
        await db.commit()


async def clear_afk(user_id: int, guild_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("DELETE FROM afk WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
        await db.commit()


async def get_afk(user_id: int, guild_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM afk WHERE user_id = ? AND guild_id = ?", (user_id, guild_id)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def touch_last_seen(user_id: int, guild_id: int):
    await get_user(user_id, guild_id)
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE users SET last_message_at = ? WHERE user_id = ? AND guild_id = ?",
            (_now(), user_id, guild_id),
        )
        await db.commit()


# ---------- tags ----------

async def create_tag(guild_id: int, name: str, content: str, created_by: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO tags (guild_id, name, content, created_by, created_at) VALUES (?, ?, ?, ?, ?)",
            (guild_id, name.lower(), content, created_by, _now()),
        )
        await db.commit()


async def edit_tag(guild_id: int, name: str, content: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE tags SET content = ? WHERE guild_id = ? AND name = ?",
            (content, guild_id, name.lower()),
        )
        await db.commit()


async def delete_tag(guild_id: int, name: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "DELETE FROM tags WHERE guild_id = ? AND name = ?", (guild_id, name.lower())
        )
        await db.commit()


async def get_tag(guild_id: int, name: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM tags WHERE guild_id = ? AND name = ?", (guild_id, name.lower())
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def list_tags(guild_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT name FROM tags WHERE guild_id = ? ORDER BY name", (guild_id,))
        rows = await cur.fetchall()
        return [r["name"] for r in rows]


# ---------- quotes ----------

async def add_quote(guild_id: int, content: str, added_by: int) -> int:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO quotes (guild_id, content, added_by, created_at) VALUES (?, ?, ?, ?)",
            (guild_id, content, added_by, _now()),
        )
        await db.commit()
        return cur.lastrowid


async def delete_quote(guild_id: int, quote_id: int) -> bool:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM quotes WHERE guild_id = ? AND id = ?", (guild_id, quote_id)
        )
        await db.commit()
        return cur.rowcount > 0


async def get_quote(guild_id: int, quote_id: int = None):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if quote_id is not None:
            cur = await db.execute(
                "SELECT * FROM quotes WHERE guild_id = ? AND id = ?", (guild_id, quote_id)
            )
        else:
            cur = await db.execute(
                "SELECT * FROM quotes WHERE guild_id = ? ORDER BY RANDOM() LIMIT 1", (guild_id,)
            )
        row = await cur.fetchone()
        return dict(row) if row else None


async def count_quotes(guild_id: int) -> int:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM quotes WHERE guild_id = ?", (guild_id,))
        row = await cur.fetchone()
        return row[0] if row else 0


# ---------- starboard ----------

async def get_starboard_post(original_message_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM starboard_posts WHERE original_message_id = ?", (original_message_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def upsert_starboard_post(original_message_id: int, guild_id: int, author_id: int, star_count: int, starboard_message_id: int | None = None):
    async with aiosqlite.connect(config.DB_PATH) as db:
        existing = await get_starboard_post(original_message_id)
        if existing:
            if starboard_message_id is None:
                starboard_message_id = existing["starboard_message_id"]
            await db.execute(
                "UPDATE starboard_posts SET star_count = ?, starboard_message_id = ? WHERE original_message_id = ?",
                (star_count, starboard_message_id, original_message_id),
            )
        else:
            await db.execute(
                "INSERT INTO starboard_posts (original_message_id, starboard_message_id, guild_id, author_id, star_count) "
                "VALUES (?, ?, ?, ?, ?)",
                (original_message_id, starboard_message_id, guild_id, author_id, star_count),
            )
        await db.commit()


async def delete_starboard_post(original_message_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("DELETE FROM starboard_posts WHERE original_message_id = ?", (original_message_id,))
        await db.commit()


async def top_starred_authors(guild_id: int, limit: int = 10):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT author_id, SUM(star_count) as total_stars FROM starboard_posts "
            "WHERE guild_id = ? GROUP BY author_id ORDER BY total_stars DESC LIMIT ?",
            (guild_id, limit),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ---------- confessions ----------

async def add_confession(guild_id: int, author_id: int, content: str) -> int:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO confessions (guild_id, author_id, content, created_at) VALUES (?, ?, ?, ?)",
            (guild_id, author_id, content, _now()),
        )
        await db.commit()
        return cur.lastrowid


async def get_confession(guild_id: int, confession_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM confessions WHERE guild_id = ? AND id = ?", (guild_id, confession_id)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def count_confessions(guild_id: int) -> int:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM confessions WHERE guild_id = ?", (guild_id,))
        row = await cur.fetchone()
        return row[0] if row else 0


# ---------- invite tracking ----------

async def credit_invite(guild_id: int, inviter_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO invite_stats (guild_id, inviter_id, uses) VALUES (?, ?, 1) "
            "ON CONFLICT(guild_id, inviter_id) DO UPDATE SET uses = uses + 1",
            (guild_id, inviter_id),
        )
        await db.commit()


async def get_invite_count(guild_id: int, inviter_id: int) -> int:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "SELECT uses FROM invite_stats WHERE guild_id = ? AND inviter_id = ?", (guild_id, inviter_id)
        )
        row = await cur.fetchone()
        return row[0] if row else 0


async def invite_leaderboard(guild_id: int, limit: int = 10):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT inviter_id, uses FROM invite_stats WHERE guild_id = ? ORDER BY uses DESC LIMIT ?",
            (guild_id, limit),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ---------- word filter ----------

async def add_filtered_word(guild_id: int, word: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO filtered_words (guild_id, word) VALUES (?, ?)",
            (guild_id, word.lower()),
        )
        await db.commit()


async def remove_filtered_word(guild_id: int, word: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "DELETE FROM filtered_words WHERE guild_id = ? AND word = ?", (guild_id, word.lower())
        )
        await db.commit()


async def get_filtered_words(guild_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute("SELECT word FROM filtered_words WHERE guild_id = ?", (guild_id,))
        rows = await cur.fetchall()
        return [r[0] for r in rows]


# ---------- tickets ----------

async def create_ticket(channel_id: int, guild_id: int, opener_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO tickets (channel_id, guild_id, opener_id, status, created_at) VALUES (?, ?, ?, 'open', ?)",
            (channel_id, guild_id, opener_id, _now()),
        )
        await db.commit()


async def get_ticket(channel_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM tickets WHERE channel_id = ?", (channel_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def close_ticket(channel_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("UPDATE tickets SET status = 'closed' WHERE channel_id = ?", (channel_id,))
        await db.commit()


# ---------- suggestions ----------

async def add_suggestion(guild_id: int, author_id: int, content: str) -> int:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO suggestions (guild_id, author_id, content, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
            (guild_id, author_id, content, _now()),
        )
        await db.commit()
        return cur.lastrowid


async def set_suggestion_message(suggestion_id: int, message_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE suggestions SET message_id = ? WHERE id = ?", (message_id, suggestion_id)
        )
        await db.commit()


async def set_suggestion_status(suggestion_id: int, status: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("UPDATE suggestions SET status = ? WHERE id = ?", (status, suggestion_id))
        await db.commit()


async def get_suggestion(suggestion_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM suggestions WHERE id = ?", (suggestion_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def list_pending_suggestions(guild_id: int, limit: int = 10):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM suggestions WHERE guild_id = ? AND status = 'pending' ORDER BY id DESC LIMIT ?",
            (guild_id, limit),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ---------- social: bio, marriage, reputation ----------

async def set_bio(user_id: int, guild_id: int, bio: str):
    await update_user(user_id, guild_id, bio=bio)


async def set_marriage(user_id: int, guild_id: int, partner_id: int | None):
    await update_user(user_id, guild_id, married_to=partner_id)


async def touch_rep_cooldown(user_id: int, guild_id: int):
    await update_user(user_id, guild_id, last_rep=_now())


async def add_reputation(user_id: int, guild_id: int, amount: int = 1):
    user = await get_user(user_id, guild_id)
    await update_user(user_id, guild_id, reputation=user["reputation"] + amount)
