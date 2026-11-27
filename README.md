# DFX Deals Bot (Amazon-only, zero-budget MVP)

A Python Telegram bot for scheduled publishing of curated Amazon affiliate deals.
It does not scrape Amazon, guess prices, or automatically crawl Amazon search pages.
The first MVP accepts verified affiliate links and product details from an admin.

## 1. Create the Telegram bot
1. Open Telegram and message `@BotFather`.
2. Send `/newbot`, choose a display name and username.
3. Copy the bot token. Keep it private.
4. Create your DFX Deals Telegram channel.
5. Add the bot as an administrator and allow it to post messages.
6. Get your numeric Telegram user ID using a trusted ID utility bot, then add it to `.env`.

## 2. Install on Android using Termux
Install Termux from its official F-Droid or GitHub distribution. Then run:

```bash
pkg update && pkg upgrade -y
pkg install python nano -y
mkdir -p ~/dfx-deals-bot
cd ~/dfx-deals-bot
```

Copy `main.py`, `requirements.txt`, and `.env.example` into this folder.
Then run:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
```

Fill in the bot token, channel username and your numeric Telegram user ID.
Save in nano with Ctrl+O, Enter, Ctrl+X.

Start the bot:

```bash
set -a
source .env
set +a
python main.py
```

Keep Termux running. In another Telegram chat, send `/start` to your bot.

## 3. Add a deal
As the configured admin, send this to the bot:

```text
/adddeal Noise 30W GaN Charger | Electronics | https://amzn.to/YOUR-AFFILIATE-LINK | Check current price and availability on Amazon.
```

Use your own valid affiliate link. Do not copy the example placeholder.
The bot queues the deal and publishes the next queued item on its schedule.
Use `/postnow` to publish the next queued item immediately.

## 4. Admin commands
- `/status` – counts and scheduler status
- `/adddeal Title | Category | Amazon affiliate URL | Note`
- `/list` – recent deals
- `/postnow` – publish next queued deal
- `/pause` and `/resume` – control scheduled publishing
- `/test` – test channel posting

## 5. Keep it running on Android
- Run `termux-wake-lock` in Termux before starting the bot.
- Exclude Termux from battery optimization if Android offers that setting.
- Keep the phone powered and connected to the internet.
- Android may still stop background processes. This is suitable for testing, not guaranteed 24/7 hosting.

## 6. Zero-cost production path
Start with Termux for testing. For 24/7 publishing, move the same Python project to a free background-worker or always-on VM provider if a genuinely free tier is available at deployment time. Check current quotas and card requirements first.

## 7. Amazon compliance
- Use only your own Associates tracking links.
- Add the required associate disclosure to your channel description and deal posts.
- Do not scrape Amazon pages or copy product images/content without permission.
- Do not publish unverified prices, discounts, stock or delivery claims.
- If using Amazon Creators API / PA API content, follow the current API licence, attribution, refresh and timestamp requirements.
- API access is not guaranteed; eligibility requirements apply.
- Confirm that Telegram/channel use is permitted under the current India Associates agreement and policies before using Amazon-provided Product Advertising Content in this app.

## 8. Backups
Stop the bot and copy `deals.db` somewhere safe. Never share `.env`, the bot token, or private credentials.
