# Telegram Auto-Post Bot

Production-ready async Telegram bot for Uzbek financial and economic news. It posts 8 times per day to a Telegram channel, using both web sources and public Telegram channels.

## Features

- 8 fixed daily posts in `Asia/Tashkent`: `08:08`, `10:10`, `12:12`, `13:13`, `15:15`, `17:17`, `19:19`, `21:21`
- Web scraping with `httpx` and `BeautifulSoup4`
- Public Telegram channel scraping without login code by default
- Optional Telethon session mode with `USE_TELETHON=true`
- Topic filtering before translation to reduce API usage
- SQLite deduplication with 30-day cleanup
- OpenAI translation via `gpt-4o-mini` when `OPENAI_API_KEY` is set
- Google Translate fallback via `deep-translator`
- Button menu with `/start` or `/menu`
- `/status` command for today's count and next scheduled post
- `/schedule` command for the full visual posting schedule
- `/session` command for Telegram source mode diagnostics
- `/test web` or `/test telegram` admin-only command
- Railway Docker deploy with persistent `/app/data` volume

## Environment

Copy `.env.example` to `.env` for local development and fill in real values.

```bash
cp .env.example .env
```

Required variables:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID` or `TELEGRAM_CHANNEL_IDS`
- `ADMIN_USER_IDS`

Source variables:

- `TELEGRAM_SOURCE_CHANNELS`: Telegram usernames, comma-separated. Example: `@ReutersBusiness,@Bloomberg,@investing_com`
- `WEB_SOURCE_URLS`: web pages, comma-separated. Default sources are TradingView, Webull, Yahoo Finance, and Investing.com.

Recommended variables:

- `OPENAI_API_KEY`
- `DATA_DIR=data` locally, `/app/data` on Railway
- `TELETHON_SESSION_PATH=data/session.session` locally, `/app/data/session.session` on Railway
- `USE_TELETHON=false` for login-code-free public channel scraping

## Local Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Run `python setup_session.py` only if you set `USE_TELETHON=true`.

## Railway Deploy

1. Push this project to GitHub.
2. Create a Railway project from the GitHub repository.
3. Add environment variables from `.env.example` in Railway.
4. Mount a Railway Volume at `/app/data`.
5. Set `DATA_DIR=/app/data`, `DB_PATH=/app/data/posted_news.sqlite3`, and `TELETHON_SESSION_PATH=/app/data/session.session`.
6. Deploy. Docker runs `python main.py`.

If `USE_TELETHON=true`, run `python setup_session.py` once in an interactive environment, save `/app/data/session.session`, then redeploy.

Railway uses `Dockerfile` and `railway.toml`.

Railway volume note: Railway mounts volumes at runtime. If you mount the volume to `/app/data`, SQLite state persists between deploys.
