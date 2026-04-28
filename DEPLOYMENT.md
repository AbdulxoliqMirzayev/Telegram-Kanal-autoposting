# Deployment Checklist

## GitHub

This folder is ready to be pushed to GitHub, but it must not include local secrets or runtime data.

Protected by `.gitignore` and `.dockerignore`:

- `.env`
- `.venv/`
- `data/`
- `logs/`
- `*.session`
- `*.sqlite3`
- `__pycache__/`

Create and push a repository:

```bash
git init
git add .
git commit -m "Prepare Telegram news bot for Railway"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

## Railway

1. Create a Railway project from the GitHub repository.
2. Railway will use `Dockerfile` automatically.
3. Add variables from `.env.example` in the Railway Variables tab.
4. Use these production path variables:

```env
DATA_DIR=/app/data
DB_PATH=/app/data/posted_news.sqlite3
TELETHON_SESSION_PATH=/app/data/session.session
USE_TELETHON=false
```

5. Create and attach a Railway Volume with mount path:

```text
/app/data
```

6. Deploy.

## Telegram Setup

Add the bot to your Telegram channel as an admin and enable `Post Messages`.
For multiple target channels, set:

```env
TELEGRAM_CHANNEL_IDS=@channel_one,@channel_two,@channel_three
```

If the bot is removed as admin from one channel, that channel is skipped and the bot continues posting to the remaining channels.

Admin commands:

```text
/start
/menu
/status
/schedule
/session
/test web
/test telegram
```

## Security

Never commit real values for:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_API_HASH`
- `TELEGRAM_PHONE`
- `OPENAI_API_KEY`

If any secret was posted publicly, rotate it before production deploy.
