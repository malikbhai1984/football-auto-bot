import os
import requests
import telebot
from dotenv import load_dotenv
from datetime import datetime

# ----------------------
# Load environment variables
# ----------------------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = int(os.getenv("OWNER_CHAT_ID"))
SPORTMONKS_API = os.getenv("SPORTMONKS_API")
APIFOOTBALL_API = os.getenv("API_KEY")  # optional second API
BOT_NAME = os.getenv("BOT_NAME")
DOMAIN = os.getenv("DOMAIN")
PORT = int(os.getenv("PORT", 8080))

if not all([BOT_TOKEN, OWNER_CHAT_ID, SPORTMONKS_API, DOMAIN]):
    raise ValueError("❌ BOT_TOKEN, OWNER_CHAT_ID, SPORTMONKS_API, APIFOOTBALL_API, or DOMAIN missing!")

bot = telebot.TeleBot(BOT_TOKEN)

# ----------------------
# Top Leagues & Qualifiers
# ----------------------
TOP_LEAGUES = {
    "Premier League": 39,
    "La Liga": 140,
    "Serie A": 135,
    "Bundesliga": 78,
    "Ligue 1": 61,
    "Eredivisie": 88,
    "Primeira Liga": 94,
    "Russian Premier League": 293
}

QUALIFIERS = {
    "World Cup Qualifiers": 73,
    "Euro Qualifiers": 74
}

# ----------------------
# Fetch Live Matches
# ----------------------
def fetch_live_matches():
    url = f"https://soccer.sportmonks.com/api/v2.0/fixtures/live?api_token={SPORTMONKS_API}&include=localTeam,visitorTeam,league"
    res = requests.get(url).json()
    all_matches = res.get("data", [])
    
    filtered_matches = []
    for m in all_matches:
        league_id = m.get("league", {}).get("data", {}).get("id")
        if league_id in list(TOP_LEAGUES.values()) + list(QUALIFIERS.values()):
            filtered_matches.append({
                "match_id": m["id"],
                "home": m.get("localTeam", {}).get("data", {}).get("name", "Home"),
                "away": m.get("visitorTeam", {}).get("data", {}).get("name", "Away"),
                "league": m.get("league", {}).get("data", {}).get("name", "League"),
                "minute": m.get("time", {}).get("minute", 0),
                "score": f"{m.get('scores', {}).get('localteam_score', 0)} - {m.get('scores', {}).get('visitorteam_score', 0)}"
            })
    return filtered_matches

# ----------------------
# Simple ML/AI Prediction Stub
# Replace this with your real model
# ----------------------
def predict_goal_chance(match):
    """
    Return probability of goal in last 10 minutes.
    Currently random stub, replace with your ML/AI logic.
    """
    import random
    return random.randint(50, 100)

# ----------------------
# Send Telegram Alert
# ----------------------
def send_alert(match, prob):
    if prob >= 80:  # threshold
        message = (
            f"🔥 GOAL ALERT 🔥\n"
            f"League: {match['league']}\n"
            f"Match: {match['home']} vs {match['away']}\n"
            f"Score: {match['score']}\n"
            f"Minute: {match['minute']}'\n"
            f"Goal Chance: {prob}%"
        )
        bot.send_message(OWNER_CHAT_ID, message)

# ----------------------
# Main Loop
# ----------------------
def main():
    while True:
        try:
            live_matches = fetch_live_matches()
            for match in live_matches:
                prob = predict_goal_chance(match)
                send_alert(match, prob)
        except Exception as e:
            print("Error:", e)
        import time
        time.sleep(60)  # check every 60 seconds

# ----------------------
# Run bot
# ----------------------
if __name__ == "__main__":
    print("✅ Bot started. Fetching live matches...")
    main()
