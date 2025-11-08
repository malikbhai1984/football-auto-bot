import os
from dotenv import load_dotenv
load_dotenv()

import telebot
import time
from datetime import datetime
import requests






import os
from dotenv import load_dotenv
load_dotenv()
import telebot
import requests
import threading
import time

# Load env
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
API_KEY = os.getenv("API_KEY")
GROK_API = "https://api.x.ai/v1/chat/completions"  # Add your xAI API key in .env as XAI_KEY
XAI_KEY = os.getenv("XAI_KEY")
BOT_NAME = os.getenv("BOT_NAME", "Malik Bhai Intelligent Bot")

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
API_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# ------------------------- #
# Intelligent Reply via xAI #
# ------------------------- #
def get_intelligent_reply(user_msg, context=""):
    prompt = f"""You are Malik Bhai Intelligent Bot. Reply briefly, smartly, and confidently like a pro tipster.
    User: {user_msg}
    Context: {context}
    Respond in 1-2 lines max. Use emojis. Be direct."""
    
    try:
        resp = requests.post(
            GROK_API,
            headers={"Authorization": f"Bearer {XAI_KEY}"},
            json={
                "model": "grok-beta",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 100
            },
            timeout=10
        ).json()
        return resp["choices"][0]["message"]["content"].strip()
    except:
        return "🤖 Smart reply loading... try again!"

# ------------------------- #
# Smart Reply Handler (AI-Powered) #
# ------------------------- #
@bot.message_handler(func=lambda m: True)
def smart_reply(message):
    user_text = message.text.strip()
    
    # Match keywords → give prediction
    if any(k in user_text.lower() for k in ["live", "update", "over", "btts", "score", "win"]):
        matches = requests.get(f"{API_URL}/fixtures?live=all", headers=HEADERS).json().get("response", [])
        if matches:
            match = matches[0]
            home, away = match["teams"]["home"]["name"], match["teams"]["away"]["name"]
            analysis = "Over 2.5 likely (85%+)"  # reuse your logic if needed
            context = f"Live: {home} vs {away} → {analysis}"
        else:
            context = "No live matches."
    else:
        context = ""

    # Get AI reply
    ai_reply = get_intelligent_reply(user_text, context)
    bot.reply_to(message, ai_reply)

# ------------------------- #
# Flask Webhook (unchanged) #
# ------------------------- #
from flask import Flask, request
app = Flask(__name__)

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.data.decode('utf-8'))
    bot.process_new_updates([update])
    return 'OK', 200

@app.route('/')
def home():
    return f"{BOT_NAME} running!"

if __name__ == "__main__":
    domain = "YOUR_RAILWAY_DOMAIN"  # Update
    bot.remove_webhook()
    bot.set_webhook(url=f"{domain}/{BOT_TOKEN}")
    threading.Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': 8080}).start()







