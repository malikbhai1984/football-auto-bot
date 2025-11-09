import requests
import time
import threading
from datetime import datetime

# ===============================
# CONFIGURATION
# ===============================
API_TOKEN = "YOUR_SPORTMONKS_API_TOKEN"  # 🔑 Replace with your SportMonks token
BOT_TOKEN = "8336882129:AAFZ4oVAY_cEyy_JTi5A0fo12TnTXSEI8as"
CHAT_ID = "7742985526"  # ✅ Your Telegram chat ID
REFRESH_INTERVAL = 420  # seconds (7 minutes)

# ===============================
# CORE FUNCTIONS
# ===============================
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("⚠️ Telegram send error:", e)

def fetch_live_matches():
    url = f"https://api.sportmonks.com/v3/football/livescores/inplay?api_token={API_TOKEN}"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        matches = data.get("data", [])
        return matches
    except Exception as e:
        print("⚠️ Error fetching live matches:", e)
        return []

def format_match(match):
    try:
        home = match["home_team"]["data"]["name"]
        away = match["away_team"]["data"]["name"]
        score_home = match["scores"]["localteam_score"]
        score_away = match["scores"]["visitorteam_score"]
        minute = match["time"]["minute"]
        status = match["time"]["status"]
        return f"⚽ *{home}* vs *{away}*\nScore: {score_home}-{score_away}\nStatus: {status} ({minute}')"
    except:
        return "⚠️ Match data incomplete"

def alert_loop():
    while True:
        print(f"🔄 Checking live matches... {datetime.now().strftime('%H:%M:%S')}")
        matches = fetch_live_matches()
        if not matches:
            print("⏳ No live matches at the moment.")
        else:
            for m in matches[:5]:  # limit to first 5 matches
                msg = format_match(m)
                print("Sending:", msg)
                send_telegram_message(msg)
        print(f"⏳ Waiting {REFRESH_INTERVAL//60} minutes before next update...\n")
        time.sleep(REFRESH_INTERVAL)

# ===============================
# START BOT
# ===============================
if __name__ == "__main__":
    print("🤖 MyBetAlert_Bot (SportMonks) Started Successfully!")
    alert_thread = threading.Thread(target=alert_loop)
    alert_thread.start()
