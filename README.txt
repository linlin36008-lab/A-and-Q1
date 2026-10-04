Novel A&Q Broadcast Bot

Railway Variables:
BOT_TOKEN=your_bot_token
ADMIN_ID=your_telegram_user_id

No GROUP_ID is required.

Commands:
 Reply to the message you want to broadcast, then send /broadcast.
    The bot copies that replied message to all remembered groups.
    Maximum 10 broadcasts per day.

 /retry
    Retries groups that failed during the last broadcast.
    It does not consume another /broadcast daily slot.

 /chats
    Shows remembered group count, today's broadcast count, and pending count.

Important:
The bot must receive at least one update/message from a group before that group can be remembered.
Telegram rate limits are handled with RetryAfter waits and a small delay between groups.


/skip
- Admin-only command to reset the bot's own daily broadcast counter.
- Does not bypass Telegram/server-side rate limits.
