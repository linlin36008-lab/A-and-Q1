import os
import sqlite3
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB = "users.db"

logging.basicConfig(level=logging.INFO)

def db():
    return sqlite3.connect(DB)

def init_db():
    con = db()
    con.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT
    )""")
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
    return [row[0] for row in rows]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_user)
    await update.message.reply_text(
        "👋 Welcome!\n\nမေးချင်တာရှိရင် ဒီမှာ ပို့ပါ။\nAdmin ဆီကို မေးခွန်းပို့ပေးပါမယ်။"
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

    users = get_users()
    success = 0
    failed = 0

    for user_id in users:
        try:
            await context.bot.copy_message(
                chat_id=user_id,
                from_chat_id=update.effective_chat.id,
                message_id=replied.message_id
            )
            success += 1
        except Exception as e:
            logging.warning("Broadcast failed for %s: %s", user_id, e)
            failed += 1

    await update.message.reply_text(
        f"📢 Broadcast ပြီးပါပြီ\n\n✅ Sent: {success}\n❌ Failed: {failed}"
    )

async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(f"👥 Bot Users: {len(get_users())}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return

    save_user(update.effective_user)

    if update.effective_user.id != ADMIN_ID:
        try:
            await context.bot.forward_message(
                chat_id=ADMIN_ID,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id
            )
            await update.message.reply_text("✅ မေးခွန်းကို Admin ဆီ ပို့ပြီးပါပြီ။")
        except Exception as e:
            logging.warning("Forward failed: %s", e)
            await update.message.reply_text("❌ မေးခွန်းပို့ရာမှာ အဆင်မပြေပါ။")

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN မရှိပါ။")
    if not ADMIN_ID:
        raise RuntimeError("ADMIN_ID မရှိပါ။")

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
