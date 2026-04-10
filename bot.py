import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from dotenv import load_dotenv

load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-domain.com")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Open Music App", web_app=WebAppInfo(url=WEBAPP_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome to the Music Bot! Click the button below to join the music room.",
        reply_markup=reply_markup
    )

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide a song link. Example: /play https://youtube.com/watch?v=...")
        return

    link = context.args[0]
    # In a real scenario, we'd notify the backend to start downloading
    # For now, we'll just provide the WebApp link

    keyboard = [
        [InlineKeyboardButton("Join & Listen", web_app=WebAppInfo(url=f"{WEBAPP_URL}?play={link}"))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Song requested! Join the room to listen.",
        reply_markup=reply_markup
    )

async def run_bot():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("BOT_TOKEN not set, bot will not start.")
        return

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    start_handler = CommandHandler('start', start)
    play_handler = CommandHandler('play', play)

    application.add_handler(start_handler)
    application.add_handler(play_handler)

    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    print("Bot started...")

if __name__ == '__main__':
    asyncio.run(run_bot())
