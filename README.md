# 🎵 BAD MUSIC — Telegram Mini App

Real-time music room with chat, profile & play history.

---

## STRUCTURE

```
main.py          ← FastAPI server (WebSocket + REST)
bot.py           ← Telegram bot (python-telegram-bot)
downloader.py    ← YouTube audio downloader
static/
  index.html     ← Single-file frontend (Player + Chat + Profile)
requirements.txt
render.yaml      ← Render.com deploy config
Procfile         ← Heroku/Render process
```

---

## DEPLOY ON RENDER (Recommended for web)

1. Push this folder to a GitHub repo
2. Go to https://render.com → New Web Service → Connect your repo
3. Settings auto-detected from render.yaml
4. In **Environment** tab add:
   - `BOT_TOKEN` = your Telegram bot token
   - `WEBAPP_URL` = your Render URL (e.g. https://bad-music.onrender.com)
5. Deploy → done!

> Note: Render free tier sleeps after 15 min inactivity. Upgrade to keep it always on.

---

## RUN BOT ON VPS (Recommended)

The bot.py and main.py run together — bot starts inside FastAPI lifespan.

```bash
# 1. Clone / upload files to VPS
# 2. Install dependencies
pip install -r requirements.txt

# 3. Set env vars
export BOT_TOKEN="your_token_here"
export WEBAPP_URL="https://your-render-url.onrender.com"

# 4. Run with uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000

# OR with PM2 (keeps running after logout)
pm2 start "uvicorn main:app --host 0.0.0.0 --port 8000" --name bad-music
```

---

## FEATURES

- 🎵 **Real-time music room** — everyone hears the same song in sync
- 💬 **Live chat** — Socket-based chat with Telegram profile pics
- 👤 **Profile** — Shows your Telegram name/photo, play count, history
- 🎧 **Join screen** — Shows your Telegram card before joining
- 📱 **Telegram Mini App** — Works as WebApp inside Telegram bot

---

## BOT COMMANDS

- `/start` — Opens the Mini App with Join + Profile buttons  
- `/play <youtube_link>` — Loads song into the room for everyone
