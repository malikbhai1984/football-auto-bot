import os
from dotenv import load_dotenv
load_dotenv()

import telebot
import time
from datetime import datetime
import requests







import os
import telebot
import time
from datetime import datetime
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
API_KEY = os.getenv("API_KEY")
BOT_NAME = os.getenv("BOT_NAME", "Football Auto Bot")

if not BOT_TOKEN or not OWNER_CHAT_ID:
    print("DEBUG:", BOT_TOKEN, OWNER_CHAT_ID, API_KEY)
    raise ValueError("❌ BOT_TOKEN or OWNER_CHAT_ID missing in Railway variables!")

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start', 'hello'])
def send_welcome(message):
    bot.reply_to(message, f"👋 {BOT_NAME} is live and checking live matches every 7 minutes!")

LEAGUE_IDS = ["39", "140", "135", "78", "61", "2"]

def fetch_live_matches():
    headers = {"x-apisports-key": API_KEY}
    url = f"https://v3.football.api-sports.io/fixtures?live=all"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json().get("response", [])
        return []
    except Exception as e:
        print("⚠️ Error fetching live:", e)
        return []

def make_summary(match):
    league = match["league"]["name"]
    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]
    gh = match["goals"]["home"]
    ga = match["goals"]["away"]
    minute = match["fixture"]["status"].get("elapsed", 0)
    status = match["fixture"]["status"]["long"]
    return f"🏆 {league}\n⚽ {home} {gh}-{ga} {away}\n⏱ {status} ({minute}′)"

def send_updates():
    live = fetch_live_matches()
    if not live:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] No live matches found.")
        return
    for m in live:
        try:
            msg = make_summary(m)
            bot.send_message(OWNER_CHAT_ID, msg)
        except Exception as e:
            print("⚠️ Send failed:", e)

print(f"🏁 {BOT_NAME} started! Sending updates every 7 minutes.")
while True:
    try:
        send_updates()
    except Exception as e:
        print("⚠️ Loop error:", e)
    time.sleep(420)
