Kage A&Q Broadcast Bot

Railway Variables:
BOT_TOKEN=your_bot_token
ADMIN_ID=your_telegram_user_id

No GROUP_ID is required.

Commands:
 /broadcast your message
    Sends to all groups remembered by the bot.
    Maximum 10 broadcasts per day.

 /retry
    Retries groups that failed during the last broadcast.
    It does not consume another /broadcast daily slot.

 /chats
    Shows remembered group count, today's broadcast count, and pending count.

Important:
The bot must receive at least one update/message from a group before that group can be remembered.
Telegram rate limits are handled with RetryAfter waits and a small delay between groups.
