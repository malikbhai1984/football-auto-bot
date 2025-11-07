import os
from dotenv import load_dotenv
load_dotenv()

import telebot
import time
from datetime import datetime
import requests







import os
import telebot
from flask import Flask, request

# ---------------------
# Load environment variables
# ---------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
BOT_NAME = os.environ.get("BOT_NAME", "Football Auto Bot")

if not BOT_TOKEN or not OWNER_CHAT_ID:
    raise ValueError("❌ BOT_TOKEN or OWNER_CHAT_ID missing in Railway variables!")

# ---------------------
# Initialize Flask + Bot
# ---------------------
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

# ---------------------
# Telegram basic commands
# ---------------------
@bot.message_handler(commands=['start', 'hello'])
def welcome(message):
    bot.reply_to(message, f"⚽ {BOT_NAME} is live!\nWelcome, {message.from_user.first_name}!")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    text = message.text.lower().strip()
    print(f"📩 Received: {text}")
    if "hello" in text or "hi" in text:
        bot.reply_to(message, "👋 Hello Malik Bhai! Bot is working perfectly ✅")
    elif "update" in text:
        bot.reply_to(message, "📊 No live matches now. Will auto-update when matches are on.")
    else:
        bot.reply_to(message, "🤖 Malik Bhai Football Bot is online and ready!")

# ---------------------
# Flask route for webhook
# ---------------------
@app.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'OK', 200

@app.route('/')
def webhook_setup():
    return "⚽ Malik Bhai Football Bot is running!", 200

# ---------------------
# Start Flask server
# ---------------------
if __name__ == "__main__":
    print("🏁 Setting up webhook for Telegram...")
    domain = "https://football-auto-bot-production.up.railway.app"
    webhook_url = f"{domain}/{BOT_TOKEN}"
    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)
    print(f"✅ Webhook set: {webhook_url}")
    app.run(host="0.0.0.0", port=8080)

