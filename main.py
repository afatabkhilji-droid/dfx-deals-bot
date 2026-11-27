import os
import re
import html
import sqlite3
import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, ContextTypes
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()
ADMIN_IDS = {
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}
POST_INTERVAL_HOURS = max(1, int(os.getenv("POST_INTERVAL_HOURS", "3")))
DB_PATH = os.getenv("DB_PATH", "deals.db")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)
log = logging.getLogger("dfx-deals")

DISCLOSURE = "As an Amazon Associate I earn from qualifying purchases."
AMAZON_HOSTS = (
    "amazon.in", "www.amazon.in", "amzn.to", "link.amazon"
)

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                url TEXT NOT NULL,
                note TEXT DEFAULT '',
                active INTEGER DEFAULT 1,
                posted INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        con.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES('paused','0')"
        )

def is_admin(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id in ADMIN_IDS)

def valid_amazon_url(url: str) -> bool:
    # Allow only HTTPS Amazon affiliate destinations/short links.
    m = re.match(r"^https://([^/]+)", url.strip(), re.I)
    return bool(m and any(
        m.group(1).lower() == host or m.group(1).lower().endswith("." + host)
        for host in AMAZON_HOSTS
    ))

def get_setting(key):
    with db() as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

def set_setting(key, value):
    with db() as con:
        con.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value))
        )

def next_deal():
    with db() as con:
        return con.execute(
            "SELECT * FROM deals WHERE active=1 AND posted=0 ORDER BY id LIMIT 1"
        ).fetchone()

def deal_message(deal):
    title = html.escape(deal["title"])
    category = html.escape(deal["category"])
    note = html.escape(deal["note"] or "Check the product page for current details.")
    url = html.escape(deal["url"], quote=True)
    return (
        f"🔥 <b>DFX DEAL ALERT</b>\n\n"
        f"🛍️ <b>{title}</b>\n"
        f"🏷️ Category: {category}\n"
        f"ℹ️ {note}\n\n"
        f'👉 <a href="{url}">CHECK DEAL ON AMAZON</a>\n\n'
        f"<i>{DISCLOSURE}</i>\n"
        f"<i>Price and availability may change. Please verify on Amazon before purchase.</i>"
    )

async def publish_next(context: ContextTypes.DEFAULT_TYPE):
    if not CHANNEL_ID or get_setting("paused") == "1":
        return
    deal = next_deal()
    if not deal:
        log.info("No queued deals.")
        return
    try:
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=deal_message(deal),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False
        )
        with db() as con:
            con.execute("UPDATE deals SET posted=1 WHERE id=?", (deal["id"],))
        log.info("Published deal ID %s", deal["id"])
    except Exception:
        log.exception("Publishing failed; deal remains queued.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to DFX Deals Bot! 🛍️\n\n"
        "I publish curated Amazon deals to the DFX Deals channel.\n"
        "Use /help to see available commands."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 <b>DFX Deals Bot Help</b>\n\n"
        "/start – Start bot\n"
        "/help – Show help\n"
        "/status – Queue and bot status\n\n"
        "<b>Admin commands</b>\n"
        "/adddeal Title | Category | Amazon affiliate URL | Note\n"
        "/postnow – Publish next queued deal\n"
        "/list – Show queued deals\n"
        "/pause – Pause scheduled publishing\n"
        "/resume – Resume scheduled publishing\n"
        "/test – Send a test message to the channel\n\n"
        "Only HTTPS Amazon.in / amzn.to / link.amazon links are accepted."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as con:
        queued = con.execute(
            "SELECT COUNT(*) n FROM deals WHERE active=1 AND posted=0"
        ).fetchone()["n"]
        posted = con.execute(
            "SELECT COUNT(*) n FROM deals WHERE posted=1"
        ).fetchone()["n"]
    await update.message.reply_text(
        f"DFX Deals status\nQueued: {queued}\nPublished: {posted}\n"
        f"Scheduler: {'PAUSED' if get_setting('paused') == '1' else 'ACTIVE'}\n"
        f"Interval: every {POST_INTERVAL_HOURS} hour(s)"
    )

async def adddeal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await update.message.reply_text("Admin only.")
    raw = update.message.text.partition(" ")[2]
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) < 3 or not all(parts[:3]):
        return await update.message.reply_text(
            "Format:\n/adddeal Product name | Category | Amazon affiliate URL | Note"
        )
    title, category, url = parts[:3]
    note = parts[3] if len(parts) > 3 else ""
    if len(title) > 180 or len(category) > 60 or len(note) > 300:
        return await update.message.reply_text("Please shorten the deal details.")
    if not valid_amazon_url(url):
        return await update.message.reply_text(
            "Link rejected. Use an HTTPS Amazon.in, amzn.to or link.amazon URL."
        )
    with db() as con:
        cur = con.execute(
            "INSERT INTO deals(title,category,url,note,created_at) VALUES(?,?,?,?,?)",
            (title, category, url, note, datetime.now(timezone.utc).isoformat())
        )
        deal_id = cur.lastrowid
    await update.message.reply_text(f"Deal #{deal_id} added to the posting queue.")

async def postnow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await update.message.reply_text("Admin only.")
    await publish_next(context)
    await update.message.reply_text("Publish attempt completed. Check the channel.")

async def list_deals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await update.message.reply_text("Admin only.")
    with db() as con:
        rows = con.execute(
            "SELECT id,title,posted FROM deals WHERE active=1 ORDER BY id DESC LIMIT 15"
        ).fetchall()
    if not rows:
        return await update.message.reply_text("No deals in the database.")
    lines = [
        f"#{r['id']} {'✅ posted' if r['posted'] else '🕒 queued'} — {r['title']}"
        for r in rows
    ]
    await update.message.reply_text("\n".join(lines))

async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await update.message.reply_text("Admin only.")
    set_setting("paused", "1")
    await update.message.reply_text("Scheduled publishing paused.")

async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await update.message.reply_text("Admin only.")
    set_setting("paused", "0")
    await update.message.reply_text("Scheduled publishing resumed.")

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await update.message.reply_text("Admin only.")
    if not CHANNEL_ID:
        return await update.message.reply_text("CHANNEL_ID is not configured.")
    await context.bot.send_message(
        chat_id=CHANNEL_ID,
        text=f"✅ DFX Deals Bot connection test.\n\n{DISCLOSURE}"
    )
    await update.message.reply_text("Test message sent to channel.")

def main():
    if not BOT_TOKEN:
        raise SystemExit("Missing BOT_TOKEN. Copy .env.example to .env and configure it.")
    if not ADMIN_IDS:
        raise SystemExit("Missing ADMIN_IDS. Add your numeric Telegram user ID.")
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("adddeal", adddeal))
    app.add_handler(CommandHandler("postnow", postnow))
    app.add_handler(CommandHandler("list", list_deals))
    app.add_handler(CommandHandler("pause", pause))
    app.add_handler(CommandHandler("resume", resume))
    app.add_handler(CommandHandler("test", test))
    if app.job_queue:
        app.job_queue.run_repeating(
            publish_next,
            interval=POST_INTERVAL_HOURS * 3600,
            first=20,
            name="scheduled-deal-publisher"
        )
    else:
        raise SystemExit('Install with: pip install "python-telegram-bot[job-queue]"')
    log.info("DFX Deals Bot is starting.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
