# Novel Invitation Letter Bot

Telegram bot that forwards a replied-to source message to registered groups and channels. Commands are restricted to the configured owner ID.

## Railway setup (phone-friendly)
1. Create a Telegram bot with `@BotFather` and copy its token.
2. Find your numeric Telegram user ID using a trusted ID bot or your existing bot tooling.
3. Upload this folder to a GitHub repository from your phone.
4. In Railway, create a project from that GitHub repository.
5. In Railway service Variables, add:
   - `BOT_TOKEN` = your BotFather token
   - `OWNER_ID` = your numeric Telegram user ID
6. Deploy. Do not publish the token or commit it into GitHub.
7. Add the bot to target groups as an administrator with **Delete Messages** permission to remove forwarded messages sent by regular members. Group admins/creator and the configured owner are exempt. Add it to each target channel as an administrator with permission to post messages. It registers groups when it sees group messages and registers chats when Telegram sends a bot-membership update.
8. In private chat with the bot, send `/start`. To broadcast, send or forward the source message/album to the bot, reply to any part of it with `/broadcast`. Media albums are forwarded as a group, preserving all photos/videos in the album instead of forwarding only one item.

## Commands
- `/broadcast` — reply to a source message to forward it to registered chats.
- `/skip` — skip the remaining destinations in the current broadcast.
- `/status` — count registered groups/channels and show broadcast status.
- `/schedule YYYY-MM-DD HH:MM` — reply to a source message; schedules a one-time forward. Time is UTC.
- `/schedules` — list pending schedules.
- `/cancel_schedule ID` — cancel a scheduled job.
- `/help` — help.

## Persistence note
Chat and schedule data are saved as JSON in `DATA_DIR`. Railway's local filesystem may be ephemeral unless a Volume is attached. For persistence across redeploys, attach a Railway Volume and set `DATA_DIR` to its mount path (for example `/data`).

## Notes
- The bot can only send to chats it can access. It must be an admin in channels to post there.
- Forward cleanup only works in groups where the bot has Delete Messages permission. It targets forwarded messages from ordinary members, not admins/creator or the configured owner.
- Album forwarding uses the recorded message IDs of album parts delivered to the bot; keep all album parts together when sending the source album to the bot.
- Telegram may reject forwarding protected-content messages or content from chats that disallow forwarding.
- Schedule times use UTC; Myanmar time is UTC+06:30.


## Telegram display name
To change the actual Telegram bot display name, open @BotFather, use `/setname`, select your bot, and set the name to `Novel Invitation Letter Bot`. The project welcome text and status/help headings already use this name.


## Group Welcome / Goodbye / Filters

Run these commands in a group (only the configured `OWNER_ID` can change settings):

- `/setwelcome Welcome {first}! Welcome to {chat}.` — welcome new members. Use `/setwelcome off` to disable.
- `/setgoodbye Goodbye {first}!` — send a goodbye when a member leaves. Use `/setgoodbye off` to disable.
- `/addfilter keyword | response text` — automatically reply when a group message contains the keyword (case-insensitive).
- `/removefilter keyword` — remove a saved filter.

Available welcome/goodbye placeholders: `{first}`, `{last}`, `{username}`, `{chat}`, `{id}`.
Settings are saved in `group_settings.json` under `DATA_DIR`; configure a persistent Railway Volume if you want them to survive redeploys.
