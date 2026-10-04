import os
import json
import asyncio
from datetime import date

from telegram import Update
from telegram.error import RetryAfter, TelegramError
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

DATA_FILE = "broadcast_data.json"
MAX_BROADCASTS_PER_DAY = 10
DELAY_BETWEEN_GROUPS = 1.0

data = {
    "groups": {},
    "daily": {"date": "", "count": 0},
    "pending": []
}


def load_data():
    global data
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        save_data()


def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def reset_daily_if_needed():
    today = date.today().isoformat()
    if data.get("daily", {}).get("date") != today:
        data["daily"] = {"date": today, "count": 0}
        save_data()


def is_admin(update: Update) -> bool:
    if not ADMIN_ID:
        return False
    return str(update.effective_user.id) == str(ADMIN_ID)


def group_chat(update: Update):
    chat = update.effective_chat
    if chat and chat.type in ("group", "supergroup"):
        data["groups"][str(chat.id)] = {
            "id": chat.id,
            "title": chat.title or "Unknown Group"
        }
        save_data()


async def track_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group_chat(update)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Novel A&Q Broadcast Bot\n\n"
        "Message ကို Reply လုပ်ပြီး /broadcast — Group အားလုံးကို ပို့ရန်\n"
        "/retry — မပို့ရသေးတဲ့ Group များကို ပြန်ပို့ရန်\n"
        "/chats — မှတ်ထားတဲ့ Group အရေအတွက်ကြည့်ရန်"
    )


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ ဒီ Command ကို အသုံးပြုခွင့်မရှိပါ။")
        return

    reset_daily_if_needed()

    if data["daily"]["count"] >= MAX_BROADCASTS_PER_DAY:
        await update.message.reply_text(
            "⛔ ဒီနေ့ Broadcast 10 ကြိမ် ပြည့်သွားပါပြီ။\n"
            "မနက်ဖြန်မှ ပြန်သုံးနိုင်ပါတယ်။"
        )
        return

    source = update.message.reply_to_message
    if not source:
        await update.message.reply_text(
            "အသုံးပြုပုံ: ပို့ချင်တဲ့ Message ကို Reply လုပ်ပြီး /broadcast ပို့ပါ။"
        )
        return

    groups = list(data["groups"].values())
    if not groups:
        await update.message.reply_text(
            "❌ မှတ်ထားတဲ့ Group မရှိသေးပါ။\n"
            "Bot ကို Group တွေထဲထည့်ပြီး message တစ်ခုရအောင် လုပ်ပါ။"
        )
        return

    data["daily"]["count"] += 1
    save_data()

    pending = []
    sent = 0

    for group in groups:
        chat_id = group["id"]
        try:
            await context.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=source.chat_id,
                message_id=source.message_id
            )
            sent += 1
            await asyncio.sleep(DELAY_BETWEEN_GROUPS)

        except RetryAfter as e:
            await asyncio.sleep(int(e.retry_after) + 1)
            try:
                await context.bot.copy_message(
                    chat_id=chat_id,
                    from_chat_id=source.chat_id,
                    message_id=source.message_id
                )
                sent += 1
                await asyncio.sleep(DELAY_BETWEEN_GROUPS)
            except Exception:
                pending.append({
                    "chat_id": chat_id,
                    "title": group["title"],
                    "source_chat_id": source.chat_id,
                    "source_message_id": source.message_id
                })

        except TelegramError:
            pending.append({
                "chat_id": chat_id,
                "title": group["title"],
                "source_chat_id": source.chat_id,
                "source_message_id": source.message_id
            })

        except Exception:
            pending.append({
                "chat_id": chat_id,
                "title": group["title"],
                "source_chat_id": source.chat_id,
                "source_message_id": source.message_id
            })

    data["pending"] = pending
    save_data()

    await update.message.reply_text(
        f"✅ Broadcast ပြီးပါပြီ။\n\n"
        f"📤 ပို့ပြီး: {sent}\n"
        f"⏳ မပို့ရသေး: {len(pending)}\n"
        f"🔢 ဒီနေ့အသုံးပြု: {data['daily']['count']}/{MAX_BROADCASTS_PER_DAY}\n\n"
        f"မပို့ရသေးတာရှိရင် /retry သုံးပါ။"
    )


async def retry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ ဒီ Command ကို အသုံးပြုခွင့်မရှိပါ။")
        return

    if not data.get("pending"):
        await update.message.reply_text("✅ ပြန်ပို့စရာ မရှိပါ။")
        return

    pending_old = list(data["pending"])
    data["pending"] = []
    save_data()

    sent = 0
    still_pending = []

    for item in pending_old:
        try:
            await context.bot.copy_message(
                chat_id=item["chat_id"],
                from_chat_id=item["source_chat_id"],
                message_id=item["source_message_id"]
            )
            sent += 1
            await asyncio.sleep(DELAY_BETWEEN_GROUPS)

        except RetryAfter as e:
            await asyncio.sleep(int(e.retry_after) + 1)
            try:
                await context.bot.copy_message(
                    chat_id=item["chat_id"],
                    from_chat_id=item["source_chat_id"],
                    message_id=item["source_message_id"]
                )
                sent += 1
            except Exception:
                still_pending.append(item)

        except Exception:
            still_pending.append(item)

    data["pending"] = still_pending
    save_data()

    await update.message.reply_text(
        f"🔄 Retry ပြီးပါပြီ။\n\n"
        f"📤 ပြန်ပို့ပြီး: {sent}\n"
        f"⏳ ကျန်နေသေး: {len(still_pending)}"
    )


async def chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ ဒီ Command ကို အသုံးပြုခွင့်မရှိပါ။")
        return

    reset_daily_if_needed()
    await update.message.reply_text(
        f"👥 မှတ်ထားတဲ့ Group: {len(data['groups'])}\n"
        f"📢 ဒီနေ့ Broadcast: {data['daily']['count']}/{MAX_BROADCASTS_PER_DAY}\n"
        f"⏳ Pending: {len(data.get('pending', []))}"
    )


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN Variable မတွေ့ပါ။")
    if not ADMIN_ID:
        raise RuntimeError("ADMIN_ID Variable မတွေ့ပါ။")

    load_data()
    reset_daily_if_needed()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("retry", retry))
    app.add_handler(CommandHandler("chats", chats))

    # Automatically remember every group where the bot receives an update.
    app.add_handler(
        MessageHandler(filters.ChatType.GROUPS, track_group),
        group=-1
    )

    print("Novel A&Q Broadcast Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
