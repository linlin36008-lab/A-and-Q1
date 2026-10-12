import os
import json
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from telegram import Update
from telegram.constants import ChatType
from telegram.error import TelegramError, RetryAfter, Forbidden, BadRequest
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ChatMemberHandler,
    ContextTypes, filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
DATA_DIR = Path(os.getenv("DATA_DIR", "."))
DATA_DIR.mkdir(parents=True, exist_ok=True)
CHATS_FILE = DATA_DIR / "chats.json"
SCHEDULES_FILE = DATA_DIR / "schedules.json"
ALBUMS_FILE = DATA_DIR / "albums.json"
SETTINGS_FILE = DATA_DIR / "group_settings.json"
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("NovelInvitationLetterBot")

broadcast_lock = asyncio.Lock()
current_skip = asyncio.Event()
current_task_active = False


def read_json(path: Path, default):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def write_json(path: Path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def chats():
    data = read_json(CHATS_FILE, {})
    return data if isinstance(data, dict) else {}


def save_chat(chat):
    data = chats()
    data[str(chat.id)] = {
        "id": chat.id,
        "title": chat.title or chat.username or str(chat.id),
        "type": chat.type,
        "added_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(CHATS_FILE, data)


def group_settings():
    data = read_json(SETTINGS_FILE, {})
    return data if isinstance(data, dict) else {}


def save_group_settings(data):
    write_json(SETTINGS_FILE, data)


def get_group_settings(chat_id):
    return group_settings().get(str(chat_id), {"welcome": "", "goodbye": "", "filters": {}})


def set_group_setting(chat_id, key, value):
    data = group_settings()
    entry = data.setdefault(str(chat_id), {"welcome": "", "goodbye": "", "filters": {}})
    entry.setdefault("filters", {})
    entry[key] = value
    save_group_settings(data)


def render_template(template: str, user, chat) -> str:
    first = (user.first_name if user else "သူငယ်ချင်း")
    values = {
        "first": first,
        "last": (user.last_name or "") if user else "",
        "username": (f"@{user.username}" if user and user.username else first),
        "chat": (chat.title or "Group") if chat else "Group",
        "id": str(user.id) if user else "",
    }
    for key, value in values.items():
        template = template.replace("{" + key + "}", value)
    return template


def owner_only(update: Update) -> bool:
    user = update.effective_user
    return bool(user and OWNER_ID and user.id == OWNER_ID)


async def deny(update: Update):
    if update.effective_message:
        await update.effective_message.reply_text("⛔ ဒီ command ကို Group Owner/Admin သို့မဟုတ် Bot Owner သာ သုံးနိုင်ပါတယ်။")


async def can_manage_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Bot owner can manage everywhere; Telegram group admins can manage inside their group."""
    if owner_only(update):
        return True
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return False
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in ("administrator", "creator")
    except TelegramError:
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat and update.effective_chat.type in (ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL):
        save_chat(update.effective_chat)
    await update.effective_message.reply_text(
        "🤖 Novel Invitation Letter Bot\n\n"
        "Group/Channel ထဲ ထည့်ထားပြီး Channel မှာ admin permission ပေးထားပါ။\n"
        "Owner က Bot Private Chat ထဲမှာ မူရင်း message ကို reply လုပ်ပြီး /broadcast ပို့ပါ။\n\n"
        "Commands: /broadcast, /skip, /status, /schedule, /schedules, /cancel_schedule, /setwelcome, /setgoodbye, /addfilter, /removefilter, /help"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "📚 Novel Invitation Letter Bot — Help Menu\n\n"
        "👥 Group Owner/Admin သုံးနိုင်သော Commands (Group ထဲတွင်)\n"
        "• /setwelcome စာသား — Member အသစ်ဝင်လာလျှင် ကြိုဆိုစာ သတ်မှတ်ရန်; /setwelcome off ဖြင့်ပိတ်ရန်\n"
        "• /setgoodbye စာသား — Member ထွက်လျှင် နှုတ်ဆက်စာ သတ်မှတ်ရန်; /setgoodbye off ဖြင့်ပိတ်ရန်\n"
        "• /addfilter keyword | reply — Keyword ပါသောစာကို အလိုအလျောက်ပြန်ရန်\n"
        "• /removefilter keyword — Filter ဖျက်ရန်\n"
        "• /chats — Bot သိမ်းထားသော Group/Channel စာရင်းကြည့်ရန်\n"
        "• /status — Bot သိမ်းထားသော Group/Channel အရေအတွက်နှင့် အခြေအနေ\n"
        "• /schedule YYYY-MM-DD HH:MM — Reply လုပ်ထားသော message ကို အချိန်သတ်မှတ်ရန် (UTC)\n"
        "• /schedules — Schedule စာရင်းကြည့်ရန်\n"
        "• /cancel_schedule ID — Schedule ဖျက်ရန်\n"
        "• /skip — လက်ရှိ broadcast ကျန်စာရင်းကို ကျော်ရန်\n\n"
        "🔒 Bot Owner သာသုံးနိုင်သည်: /broadcast (Bot Private Chat ထဲတွင် မူရင်း message ကို reply လုပ်ပြီး ပို့ပါ)\n"
        "ℹ️ /help — ဒီ Help Menu ကို မည်သူမဆို ကြည့်နိုင်သည်။\n\n"
        "Template: {first}, {last}, {username}, {chat}, {id} ကို welcome/goodbye စာသားတွင် သုံးနိုင်သည်။"
    )


async def setwelcome_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await can_manage_group(update, context):
        return await deny(update)
    chat = update.effective_chat
    msg = update.effective_message
    if not chat or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return await msg.reply_text("ဒီ command ကို Group ထဲမှာ သုံးပါ။")
    value = " ".join(context.args).strip()
    if not value:
        return await msg.reply_text("အသုံးပြုပုံ: /setwelcome ကြိုဆိုပါတယ် {first}! {chat} မှ ကြိုဆိုပါတယ်။\nပိတ်ရန်: /setwelcome off")
    if value.lower() == "off":
        value = ""
    set_group_setting(chat.id, "welcome", value)
    await msg.reply_text("✅ Welcome message ကို " + ("ပိတ်လိုက်ပါပြီ။" if not value else "သတ်မှတ်ပြီးပါပြီ။"))


async def setgoodbye_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await can_manage_group(update, context):
        return await deny(update)
    chat = update.effective_chat
    msg = update.effective_message
    if not chat or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return await msg.reply_text("ဒီ command ကို Group ထဲမှာ သုံးပါ။")
    value = " ".join(context.args).strip()
    if not value:
        return await msg.reply_text("အသုံးပြုပုံ: /setgoodbye {first} ထွက်သွားပါပြီ။\nပိတ်ရန်: /setgoodbye off")
    if value.lower() == "off":
        value = ""
    set_group_setting(chat.id, "goodbye", value)
    await msg.reply_text("✅ Goodbye message ကို " + ("ပိတ်လိုက်ပါပြီ။" if not value else "သတ်မှတ်ပြီးပါပြီ။"))


async def addfilter_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await can_manage_group(update, context):
        return await deny(update)
    chat = update.effective_chat
    msg = update.effective_message
    if not chat or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return await msg.reply_text("ဒီ command ကို Group ထဲမှာ သုံးပါ။")
    raw = msg.text.partition(" ")[2].strip() if msg.text else ""
    if "|" not in raw:
        return await msg.reply_text("အသုံးပြုပုံ: /addfilter keyword | ပြန်ဖြေမယ့်စာ\nဥပမာ: /addfilter မင်္ဂလာပါ | မင်္ဂလာပါ 👋")
    keyword, response = [part.strip() for part in raw.split("|", 1)]
    if not keyword or not response:
        return await msg.reply_text("Keyword နဲ့ ပြန်ဖြေမယ့်စာ နှစ်ခုလုံး ထည့်ပါ။")
    data = group_settings()
    entry = data.setdefault(str(chat.id), {"welcome": "", "goodbye": "", "filters": {}})
    entry.setdefault("filters", {})[keyword.casefold()] = {"keyword": keyword, "response": response}
    save_group_settings(data)
    await msg.reply_text(f"✅ Filter ထည့်ပြီးပါပြီ။\n🔎 Keyword: {keyword}\n💬 Reply: {response}")


async def removefilter_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await can_manage_group(update, context):
        return await deny(update)
    chat = update.effective_chat
    msg = update.effective_message
    if not chat or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return await msg.reply_text("ဒီ command ကို Group ထဲမှာ သုံးပါ။")
    keyword = " ".join(context.args).strip().casefold()
    if not keyword:
        return await msg.reply_text("အသုံးပြုပုံ: /removefilter keyword")
    data = group_settings()
    entry = data.get(str(chat.id), {})
    removed = entry.get("filters", {}).pop(keyword, None)
    save_group_settings(data)
    await msg.reply_text("🗑️ Filter ဖျက်ပြီးပါပြီ။" if removed else "အဲဒီ keyword filter မတွေ့ပါ။")


async def member_status_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cm = update.chat_member
    if not cm:
        return
    chat = cm.chat
    old_status = cm.old_chat_member.status
    new_status = cm.new_chat_member.status
    was_member = old_status in ("member", "administrator", "creator", "restricted")
    is_member = new_status in ("member", "administrator", "creator", "restricted")
    user = cm.new_chat_member.user
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP) or user.is_bot:
        return
    settings = get_group_settings(chat.id)
    if not was_member and is_member and settings.get("welcome"):
        try:
            await context.bot.send_message(chat.id, render_template(settings["welcome"], user, chat))
        except TelegramError as e:
            log.warning("Could not send welcome in %s: %s", chat.id, e)
    elif was_member and not is_member and settings.get("goodbye"):
        try:
            await context.bot.send_message(chat.id, render_template(settings["goodbye"], user, chat))
        except TelegramError as e:
            log.warning("Could not send goodbye in %s: %s", chat.id, e)


async def handle_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or not chat or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP) or not msg.text or msg.text.startswith("/"):
        return
    entry = get_group_settings(chat.id)
    text_lower = msg.text.casefold()
    for key, item in entry.get("filters", {}).items():
        if key and key in text_lower:
            try:
                await msg.reply_text(item.get("response", ""))
            except TelegramError as e:
                log.warning("Could not reply to filter in %s: %s", chat.id, e)
            return


async def chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cm = update.my_chat_member
    if not cm:
        return
    chat = cm.chat
    new_status = cm.new_chat_member.status
    if new_status in ("member", "administrator") and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL):
        save_chat(chat)
        log.info("Registered chat %s (%s)", chat.id, chat.title)
    elif new_status in ("left", "kicked"):
        data = chats()
        data.pop(str(chat.id), None)
        write_json(CHATS_FILE, data)


async def observe_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Register groups, remember media albums, and remove forwards from regular members."""
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or not chat:
        return

    # Record all source album parts sent/forwarded to the bot in private chat so a
    # reply to any one part can forward the complete album later.
    if chat.type == ChatType.PRIVATE and msg.media_group_id:
        albums = read_json(ALBUMS_FILE, {})
        key = f"{chat.id}:{msg.media_group_id}"
        entry = albums.get(key, {"chat_id": chat.id, "media_group_id": msg.media_group_id, "message_ids": []})
        ids = set(entry.get("message_ids", []))
        ids.add(msg.message_id)
        entry["message_ids"] = sorted(ids)
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        albums[key] = entry
        # Keep the file bounded; old album references are no longer useful.
        if len(albums) > 500:
            ordered = sorted(albums.items(), key=lambda kv: kv[1].get("updated_at", ""), reverse=True)
            albums = dict(ordered[:400])
        write_json(ALBUMS_FILE, albums)

    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        save_chat(chat)
        # Only delete forwards sent by ordinary members. Group admins/creator and
        # the configured bot owner are exempt. Bot must be an admin with delete rights.
        if getattr(msg, "forward_origin", None) is not None and msg.from_user:
            if msg.from_user.id == OWNER_ID:
                return
            try:
                member = await context.bot.get_chat_member(chat.id, msg.from_user.id)
                if member.status in ("administrator", "creator"):
                    return
                await msg.delete()
                log.info("Deleted forwarded message from regular member %s in %s", msg.from_user.id, chat.id)
            except (Forbidden, BadRequest, TelegramError) as e:
                log.warning("Could not delete forwarded message in %s: %s", chat.id, e)


def source_message_ids(source_message):
    """Return all message IDs for a media album, or the single source message ID."""
    if not getattr(source_message, "media_group_id", None):
        return [source_message.message_id]
    albums = read_json(ALBUMS_FILE, {})
    key = f"{source_message.chat_id}:{source_message.media_group_id}"
    entry = albums.get(key, {})
    ids = entry.get("message_ids", [])
    if source_message.message_id not in ids:
        ids = list(ids) + [source_message.message_id]
    return sorted(set(int(mid) for mid in ids))


async def forward_source(context, target_chat_id: int, source_chat_id: int, message_ids):
    """Forward a single message or a full Telegram media album."""
    if len(message_ids) > 1:
        await context.bot.forward_messages(
            chat_id=target_chat_id,
            from_chat_id=source_chat_id,
            message_ids=message_ids,
        )
    else:
        await context.bot.forward_message(
            chat_id=target_chat_id,
            from_chat_id=source_chat_id,
            message_id=message_ids[0],
        )


async def broadcast_message(context: ContextTypes.DEFAULT_TYPE, source_chat_id: int, source_message_ids, reply_to=None):
    global current_task_active
    async with broadcast_lock:
        current_task_active = True
        current_skip.clear()
        targets = list(chats().values())
        sent = failed = skipped = 0
        for i, target in enumerate(targets):
            if current_skip.is_set():
                skipped = len(targets) - i
                break
            try:
                await forward_source(context, int(target["id"]), source_chat_id, source_message_ids)
                sent += 1
            except RetryAfter as e:
                wait = int(getattr(e, "retry_after", 1)) + 1
                await asyncio.sleep(min(wait, 60))
                try:
                    await forward_source(context, int(target["id"]), source_chat_id, source_message_ids)
                    sent += 1
                except TelegramError:
                    failed += 1
            except (Forbidden, BadRequest, TelegramError) as e:
                failed += 1
                log.warning("Forward failed to %s: %s", target.get("title", target["id"]), e)
            await asyncio.sleep(0.08)
        current_task_active = False
        if reply_to:
            state = "⏭️ Broadcast ကို /skip နဲ့ ကျော်ပြီးပါပြီ။" if skipped else "✅ Broadcast ပြီးပါပြီ။"
            await reply_to.reply_text(f"{state}\n\n📨 အောင်မြင်: {sent}\n❌ မအောင်မြင်: {failed}\n⏭️ မပို့တော့သော: {skipped}")


async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not owner_only(update):
        return await deny(update)
    msg = update.effective_message
    if not msg.reply_to_message:
        return await msg.reply_text("Broadcast ပို့ချင်တဲ့ မူရင်း message ကို reply လုပ်ပြီး /broadcast ပို့ပါ။")
    if broadcast_lock.locked():
        return await msg.reply_text("⏳ Broadcast တစ်ခု လုပ်နေဆဲပါ။ ပြီးမှ ထပ်လုပ်ပါ။")
    src = msg.reply_to_message
    ids = source_message_ids(src)
    await msg.reply_text(f"🚀 Broadcast စတင်ပါပြီ…\n📎 Message အရေအတွက်: {len(ids)}")
    asyncio.create_task(broadcast_message(context, src.chat_id, ids, msg))


async def skip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await can_manage_group(update, context):
        return await deny(update)
    if broadcast_lock.locked() and current_task_active:
        current_skip.set()
        await update.effective_message.reply_text("⏭️ Skip လုပ်လိုက်ပါပြီ။ လက်ရှိလုပ်ဆောင်မှုအပြီး ကျန် destination တွေကို ကျော်ပါမယ်။")
    else:
        await update.effective_message.reply_text("လက်ရှိ Broadcast မရှိပါ။")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await can_manage_group(update, context):
        return await deny(update)
    data = list(chats().values())
    groups = sum(1 for c in data if c.get("type") in (ChatType.GROUP, ChatType.SUPERGROUP))
    channels = sum(1 for c in data if c.get("type") == ChatType.CHANNEL)
    await update.effective_message.reply_text(
        f"📊 Novel Broadcast Status\n\n👥 Groups: {groups}\n📢 Channels: {channels}\n📦 Total: {len(data)}\n"
        f"🚀 Broadcast: {'လုပ်နေသည်' if broadcast_lock.locked() else 'မလုပ်နေပါ'}\n🕒 UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
    )


async def chats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await can_manage_group(update, context):
        return await deny(update)
    entries = list(chats().values())
    if not entries:
        return await update.effective_message.reply_text("📭 Bot က Group/Channel စာရင်း မသိမ်းရသေးပါ။ Bot ကို Group ထဲထည့်ပြီး /start ပို့ပါ။")
    groups = [x for x in entries if x.get("type") in (ChatType.GROUP, ChatType.SUPERGROUP)]
    channels = [x for x in entries if x.get("type") == ChatType.CHANNEL]
    lines = ["📋 Bot သိမ်းထားသော Chats", f"👥 Groups: {len(groups)} | 📢 Channels: {len(channels)}", ""]
    for item in entries[:80]:
        title = item.get("title", "Unknown")
        lines.append(f"• {title} — {item.get('type', 'unknown')} — {item.get('id', '')}")
    if len(entries) > 80:
        lines.append(f"… ကျန် {len(entries) - 80} ခုကို မပြထားပါ။")
    await update.effective_message.reply_text("\n".join(lines))


def schedules():
    data = read_json(SCHEDULES_FILE, [])
    return data if isinstance(data, list) else []


def save_schedules(items):
    write_json(SCHEDULES_FILE, items)


async def run_scheduled(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    data = next((x for x in schedules() if x.get("id") == job.data.get("id")), None)
    if not data:
        return
    ids = data.get("source_message_ids") or [int(data["source_message_id"])]
    await broadcast_message(context, int(data["source_chat_id"]), [int(x) for x in ids])
    items = [x for x in schedules() if x.get("id") != data["id"]]
    save_schedules(items)


async def schedule_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await can_manage_group(update, context):
        return await deny(update)
    msg = update.effective_message
    if not msg.reply_to_message:
        return await msg.reply_text("မူရင်း message ကို reply လုပ်ပြီး /schedule YYYY-MM-DD HH:MM လို့ရေးပါ။ အချိန်ကို UTC သုံးပါ။")
    if len(context.args) != 2:
        return await msg.reply_text("အသုံးပြုပုံ: /schedule 2026-10-15 14:30\nအချိန်ဇုန်: UTC")
    try:
        dt = datetime.strptime(" ".join(context.args), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return await msg.reply_text("ရက်စွဲ/အချိန် မမှန်ပါ။ ဥပမာ /schedule 2026-10-15 14:30")
    now = datetime.now(timezone.utc)
    if dt <= now:
        return await msg.reply_text("အနာဂတ်အချိန်ကို ထည့်ပါ။")
    items = schedules()
    sid = str(max([int(x.get("id", 0)) for x in items] + [0]) + 1)
    src = msg.reply_to_message
    item = {"id": sid, "source_chat_id": src.chat_id, "source_message_id": src.message_id, "source_message_ids": source_message_ids(src), "run_at": dt.isoformat()}
    items.append(item)
    save_schedules(items)
    context.job_queue.run_once(run_scheduled, when=dt, data={"id": sid}, name=f"schedule_{sid}")
    await msg.reply_text(f"🗓️ Schedule #{sid} သိမ်းပြီးပါပြီ။\n⏰ {dt.strftime('%Y-%m-%d %H:%M')} UTC")


async def schedules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await can_manage_group(update, context):
        return await deny(update)
    items = schedules()
    if not items:
        return await update.effective_message.reply_text("Schedule မရှိသေးပါ။")
    lines = [f"#{x['id']} — {x['run_at']}" for x in items]
    await update.effective_message.reply_text("🗓️ Schedules (UTC)\n\n" + "\n".join(lines))


async def cancel_schedule_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await can_manage_group(update, context):
        return await deny(update)
    if len(context.args) != 1:
        return await update.effective_message.reply_text("အသုံးပြုပုံ: /cancel_schedule ID")
    sid = context.args[0]
    items = schedules()
    if not any(x.get("id") == sid for x in items):
        return await update.effective_message.reply_text("အဲဒီ Schedule ID မတွေ့ပါ။")
    save_schedules([x for x in items if x.get("id") != sid])
    for job in context.job_queue.get_jobs_by_name(f"schedule_{sid}"):
        job.schedule_removal()
    await update.effective_message.reply_text(f"🗑️ Schedule #{sid} ဖျက်ပြီးပါပြီ။")


def restore_schedules(app: Application):
    now = datetime.now(timezone.utc)
    for item in schedules():
        try:
            dt = datetime.fromisoformat(item["run_at"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt <= now:
                continue
            app.job_queue.run_once(run_scheduled, when=dt, data={"id": str(item["id"])}, name=f"schedule_{item['id']}")
        except (KeyError, ValueError, TypeError):
            log.exception("Invalid schedule entry: %r", item)


def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN မသတ်မှတ်ရသေးပါ။ Railway Variables ထဲမှာ BOT_TOKEN ထည့်ပါ။")
    if not OWNER_ID:
        raise SystemExit("OWNER_ID မသတ်မှတ်ရသေးပါ။ Railway Variables ထဲမှာ Telegram numeric user ID ထည့်ပါ။")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("skip", skip_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("chats", chats_cmd))
    app.add_handler(CommandHandler("schedule", schedule_cmd))
    app.add_handler(CommandHandler("schedules", schedules_cmd))
    app.add_handler(CommandHandler("cancel_schedule", cancel_schedule_cmd))
    app.add_handler(CommandHandler("setwelcome", setwelcome_cmd))
    app.add_handler(CommandHandler("setgoodbye", setgoodbye_cmd))
    app.add_handler(CommandHandler("addfilter", addfilter_cmd))
    app.add_handler(CommandHandler("removefilter", removefilter_cmd))
    app.add_handler(ChatMemberHandler(chat_member_update, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(member_status_update, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS & ~filters.COMMAND, handle_filters), group=-1)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND & ~filters.StatusUpdate.ALL, observe_chat), group=1)
    restore_schedules(app)
    log.info("Novel Invitation Letter Bot starting")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
