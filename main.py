import requests
import time
import threading
from datetime import datetime
import os

# ===============================
# 🔑 CONFIGURATION SECTION
# ===============================
API_KEY = "839f1988ceeaafddf8480de33d821556e29d8204b4ebdca13cb69c7a9bdcd325"  # ✅ Your API key
BOT_TOKEN = "8336882129:AAFZ4oVAY_cEyy_JTi5A0fo12TnTXSEI8as"  # ✅ Your Telegram bot token
CHAT_ID = "7742985526" # ⚠️ Replace this with your Telegram user ID (see below)
REFRESH_INTERVAL = 420  # seconds (7 minutes)

# ===============================
# ⚙️ CORE BOT FUNCTION
# ===============================

def send_telegram_message(text):
    """Send alert message to Telegram"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
        requests.post(url, json=payload)
    except Exception as e:
        print("⚠️ Telegram send error:", e)

def get_live_matches():
    """Fetch live football matches using your API key"""
    try:
        url = "https://api.sportmonks.com/v3/football/livescores"
        headers = {"Authorization": f"Bearer {API_KEY}"}
        response = requests.get(url, headers=headers)
        data = response.json()
        matches = data.get("data", [])
        return matches
    except Exception as e:
        print("⚠️ API error:", e)
        return []

def format_match(match):
    """Format match info for Telegram message"""
    try:
        home = match["home_team"]["name"]
        away = match["away_team"]["name"]
        score = f"{match['scores']['home_score']} - {match['scores']['away_score']}"
        status = match["time"]["status"]
        minute = match["time"].get("minute", "")
        return f"⚽ *{home}* vs *{away}*\nScore: {score}\nStatus: {status} {minute}'"
    except:
        return "⚠️ Match data incomplete"

def alert_loop():
    """Loop that fetches data and sends Telegram alerts"""
    while True:
        print(f"🔄 Checking live matches... {datetime.now().strftime('%H:%M:%S')}")
        matches = get_live_matches()
        if not matches:
            print("❌ No live matches found.")
        else:
            for m in matches[:5]:  # limit to first 5 matches
                msg = format_match(m)
                print("Sending:", msg)
                send_telegram_message(msg)
        print(f"⏳ Waiting {REFRESH_INTERVAL//60} minutes before next update...\n")
        time.sleep(REFRESH_INTERVAL)

# ===============================
# 🚀 START BOT
# ===============================
if __name__ == "__main__":
    print("🤖 MyBetAlert_Bot Started Successfully!")
    print("🔔 Live match alerts will auto-send every 7 minutes.")
    alert_thread = threading.Thread(target=alert_loop)
    alert_thread.start()
