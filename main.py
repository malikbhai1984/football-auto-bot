import os
import requests
import time
from datetime import datetime
from dotenv import load_dotenv
import telebot

# -----------------------
# Load Environment Variables
# -----------------------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API1_KEY = os.getenv("API1_KEY")       # Apifootball
API2_KEY = os.getenv("API2_KEY")       # Football-Data.org
API3_KEY = os.getenv("API3_KEY")       # SportMonks
CHAT_ID = os.getenv("CHAT_ID")

bot = telebot.TeleBot(BOT_TOKEN)

# ---------------------------------------------------
#  FETCH LIVE MATCHES FROM MULTIPLE APIs (fallback)
# ---------------------------------------------------
def fetch_live_matches():

    # -------------------- PRIMARY API (APIFOOTBALL) --------------------
    try:
        url1 = f"https://apiv3.apifootball.com/?action=get_events&match_live=1&APIkey={API1_KEY}"
        r1 = requests.get(url1, timeout=10)
        if r1.ok and isinstance(r1.json(), list):
            print("Primary API working (Apifootball)")
            return r1.json()
    except:
        pass

    # -------------------- SECOND API (FOOTBALL-DATA) --------------------
    try:
        url2 = "https://api.football-data.org/v4/matches?status=LIVE"
        headers = {"X-Auth-Token": API2_KEY}
        r2 = requests.get(url2, headers=headers, timeout=10)
        if r2.ok:
            print("Fallback API working (Football-Data)")
            matches = r2.json().get("matches", [])
            # Convert them to similar format
            converted = []
            for m in matches:
                converted.append({
                    "match_hometeam_name": m["homeTeam"]["name"],
                    "match_awayteam_name": m["awayTeam"]["name"],
                    "match_hometeam_score": m["score"]["fullTime"]["home"],
                    "match_awayteam_score": m["score"]["fullTime"]["away"],
                    "match_status": m["status"],
                })
            return converted
    except:
        pass

    # -------------------- THIRD API (SPORTMONKS) --------------------
    try:
        url3 = f"https://api.sportmonks.com/v3/football/livescores?api_token={API3_KEY}"
        r3 = requests.get(url3, timeout=10)
        if r3.ok:
            print("Fallback API working (SportMonks)")
            data = r3.json().get("data", [])
            converted = []
            for m in data:
                converted.append({
                    "match_hometeam_name": m["homeTeam"]["name"],
                    "match_awayteam_name": m["awayTeam"]["name"],
                    "match_hometeam_score": m["scores"]["home_score"],
                    "match_awayteam_score": m["scores"]["away_score"],
                    "match_status": "LIVE"
                })
            return converted
    except:
        pass

    return []


# ---------------------------------------------------
# SEND AUTO MESSAGE TO TELEGRAM
# ---------------------------------------------------
def send_update():
    try:
        matches = fetch_live_matches()

        if not matches:
            bot.send_message(CHAT_ID, "❌ No live matches found right now.")
            return

        msg = "⚽ **LIVE MATCHES UPDATE**\n\n"
        for m in matches:
            msg += (
                f"🏟 *{m['match_hometeam_name']}* vs *{m['match_awayteam_name']}*\n"
                f"🔢 Score: {m['match_hometeam_score']} - {m['match_awayteam_score']}\n"
                f"⏱ Status: {m['match_status']}\n\n"
            )

        bot.send_message(CHAT_ID, msg, parse_mode="Markdown")

    except Exception as e:
        bot.send_message(CHAT_ID, f"⚠ ERROR: {str(e)}")


# ---------------------------------------------------
# AUTO LOOP (Every 7 minutes)
# ---------------------------------------------------
if __name__ == "__main__":
    bot.send_message(CHAT_ID, "🤖 Bot started successfully!")

    while True:
        send_update()
        time.sleep(420)  # 7 minutes (7 × 60)
