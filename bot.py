import os
import sqlite3
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB = "chats.db"

logging.basicConfig(level=logging.INFO)


def db():
    return sqlite3.connect(DB)


def init_db():
    con = db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id INTEGER PRIMARY KEY,
            chat_type TEXT,
            title TEXT,
            username TEXT
        )
    """)
    con.commit()
    con.close()


def save_chat(chat):
    title = chat.title or chat.first_name or ""
    username = chat.username or ""

    con = db()
    con.execute(
        "INSERT OR REPLACE INTO chats(chat_id, chat_type, title, username) VALUES(?,?,?,?)",
        (chat.id, chat.type, title, username)
    )
    con.commit()
    con.close()


def get_chats():
    con = db()
    rows = con.execute("SELECT chat_id FROM chats").fetchall()
    con.close()
    return [row[0] for row in rows]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat(update.effective_chat)

    if update.effective_chat.type == "private":
        await update.message.reply_text(
            "👋 Welcome!\n\n"
            "မေးချင်တာရှိရင် ဒီမှာ ပို့ပါ။\n"
            "Admin ဆီကို မေးခွန်းပို့ပေးပါမယ်။"
        )
    else:
        await update.message.reply_text(
            "✅ ဒီ Group ကို Broadcast List ထဲ ထည့်ပြီးပါပြီ။"
        )


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    replied = update.message.reply_to_message

    if not replied:
        await update.message.reply_text(
            "❌ Broadcast လုပ်မယ့် Message ကို အရင်ပို့ပြီး\n"
            "အဲ့ဒီ Message ကို Reply ထောက်ကာ /broadcast ရိုက်ပါ။"
        )
        return

    chats = get_chats()
    success = 0
    failed = 0

    for chat_id in chats:
        try:
            await context.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=update.effective_chat.id,
                message_id=replied.message_id
            )
            success += 1
        except Exception as e:
            logging.warning("Broadcast failed for %s: %s", chat_id, e)
            failed += 1

    await update.message.reply_text(
        f"📢 Broadcast ပြီးပါပြီ\n\n"
        f"📨 Sent: {success}\n"
        f"❌ Failed: {failed}"
    )


async def chats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    con = db()
    rows = con.execute(
        "SELECT chat_type, COUNT(*) FROM chats GROUP BY chat_type"
    ).fetchall()
    con.close()

    counts = dict(rows)

    await update.message.reply_text(
        "📊 Broadcast Chats\n\n"
        f"👤 Private: {counts.get('private', 0)}\n"
        f"👥 Group: {counts.get('group', 0)}\n"
        f"👥 Supergroup: {counts.get('supergroup', 0)}"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return

    chat = update.effective_chat

    # Save both private users and groups whenever the bot receives a message.
    save_chat(chat)

    # Forward private user's question to Admin.
    if chat.type == "private" and update.effective_user.id != ADMIN_ID:
        try:
            await context.bot.forward_message(
                chat_id=ADMIN_ID,
                from_chat_id=chat.id,
                message_id=update.message.message_id
            )
            await update.message.reply_text(
                "✅ မေးခွန်းကို Admin ဆီ ပို့ပြီးပါပြီ။"
            )
        except Exception as e:
            logging.warning("Forward failed: %s", e)
            await update.message.reply_text(
                "❌ မေးခွန်းပို့ရာမှာ အဆင်မပြေပါ။"
            )


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN မရှိပါ။")
    if not ADMIN_ID:
        raise RuntimeError("ADMIN_ID မရှိပါ။")

    init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("chats", chats_cmd))

    # Commands are handled above; all other messages register the chat.
    app.add_handler(
        MessageHandler(filters.ALL & ~filters.COMMAND, handle_message)
    )

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
