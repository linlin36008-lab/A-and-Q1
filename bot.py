import os
import sqlite3
import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB = "users.db"

logging.basicConfig(level=logging.INFO)

def db():
    return sqlite3.connect(DB)

def init_db():
    con = db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT
        )
    """)
    con.commit()
    con.close()

def save_user(user):
    con = db()
    con.execute(
        "INSERT OR REPLACE INTO users(user_id, username, first_name) VALUES(?,?,?)",
        (user.id, user.username or "", user.first_name or "")
    )
    con.commit()
    con.close()

def get_users():
    con = db()
    rows = con.execute("SELECT user_id FROM users").fetchall()
    con.close()
    return [r[0] for r in rows]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user)
    await update.message.reply_text(
        "👋 Welcome!\n\n"
        "မေးချင်တာရှိရင် ဒီမှာ တိုက်ရိုက်ပို့ပါ။\n"
        "Admin ဆီကို မေးခွန်းပို့ပေးပါမယ်။"
    )

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text(
            "အသုံးပြုပုံ:\n/broadcast မင်းပို့ချင်တဲ့စာ"
        )
        return

    text = " ".join(context.args)
    users = get_users()
    success = 0
    failed = 0

    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=text)
            success += 1
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"📢 Broadcast ပြီးပါပြီ\n\n"
        f"✅ Sent: {success}\n"
        f"❌ Failed: {failed}"
    )

async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(f"👥 Users: {len(get_users())}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return

    save_user(update.effective_user)

    # Admin replies to a forwarded user message
    if (
        update.effective_user.id == ADMIN_ID
        and update.message.reply_to_message
        and update.message.reply_to_message.forward_origin
    ):
        origin = update.message.reply_to_message.forward_origin
        user_id = getattr(origin, "sender_user", None)
        if user_id:
            try:
                await context.bot.copy_message(
                    chat_id=user_id.id,
                    from_chat_id=update.effective_chat.id,
                    message_id=update.message.message_id
                )
                await update.message.reply_text("✅ User ဆီ ပို့ပြီးပါပြီ။")
            except Exception as e:
                await update.message.reply_text(f"❌ ပို့မရပါ: {e}")
        return

    # Forward user's question to admin
    if update.effective_user.id != ADMIN_ID:
        try:
            await context.bot.forward_message(
                chat_id=ADMIN_ID,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id
            )
            await update.message.reply_text("✅ မေးခွန်းကို Admin ဆီ ပို့ပြီးပါပြီ။")
        except Exception:
            await update.message.reply_text("❌ မေးခွန်းပို့ရာမှာ အဆင်မပြေပါ။")

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable မရှိပါ။")
    if not ADMIN_ID:
        raise RuntimeError("ADMIN_ID environment variable မရှိပါ။")

    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("users", users_cmd))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
