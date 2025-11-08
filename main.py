import os
from dotenv import load_dotenv
load_dotenv()

import telebot
import time
from datetime import datetime
import requests








import os
from flask import Flask, request
import telebot

# -------------------------
# Load environment variables
# -------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
BOT_NAME = os.environ.get("BOT_NAME", "Football Auto Bot")

if not BOT_TOKEN or not OWNER_CHAT_ID:
    raise ValueError("❌ BOT_TOKEN or OWNER_CHAT_ID missing in Railway variables!")

# -------------------------
# Initialize Flask first!
# -------------------------
app = Flask(__name__)

# -------------------------
# Then initialize the bot
# -------------------------
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# -------------------------
# Webhook route (MUST come after app is defined)
# -------------------------
@app.route('/' + BOT_TOKEN, methods=['POST'])
def receive_update():
    try:
        update = telebot.types.Update.de_json(request.data.decode('utf-8'))
        bot.process_new_updates([update])
    except Exception as e:
        print(f"⚠️ Error processing update: {e}")
    return 'OK', 200

@app.route('/')
def home():
    return "⚽ Malik Bhai Football Bot is running perfectly on Railway!", 200

# -------------------------
# Telegram message handlers
# -------------------------
@bot.message_handler(commands=['start', 'hello'])
def handle_start(message):
    bot.reply_to(message, f"⚽ {BOT_NAME} is live!\nWelcome, {message.from_user.first_name}! ✅")

@bot.message_handler(func=lambda msg: True)
def handle_message(message):
    text = message.text.lower().strip()
    print(f"📩 Received: {text}")

    if "hello" in text or "hi" in text:
        bot.reply_to(message, "👋 Hello Malik Bhai! Bot is working perfectly ✅")
    elif "update" in text:
        bot.reply_to(message, "📊 No live matches now. The bot will auto-update soon!")
    else:
        bot.reply_to(message, "🤖 Malik Bhai Football Bot is online and ready!")

# -------------------------
# Start the Flask + set webhook
# -------------------------
if __name__ == '__main__':
    print("🏁 Setting up webhook for Telegram...")
    domain = "https://football-auto-bot-production.up.railway.app"
    webhook_url = f"{domain}/{BOT_TOKEN}"

    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)
    print(f"✅ Webhook set successfully: {webhook_url}")

    app.run(host='0.0.0.0', port=8080)






