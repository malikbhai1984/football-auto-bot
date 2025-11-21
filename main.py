import os
import requests
import pandas as pd
import numpy as np
import telebot
from dotenv import load_dotenv
from sklearn.linear_model import LogisticRegression
import time

# -------------------------------
# Load environment variables
# -------------------------------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = int(os.getenv("OWNER_CHAT_ID"))
SPORTMONKS_API = os.getenv("SPORTMONKS_API")

bot = telebot.TeleBot(BOT_TOKEN)

# -------------------------------
# ML Model (Dummy LogisticRegression)
# -------------------------------
ml_model = LogisticRegression()
# Dummy training for now
X_dummy = np.random.rand(50, 3)
y_dummy = np.random.randint(0, 2, 50)
ml_model.fit(X_dummy, y_dummy)

# -------------------------------
# Leagues IDs
# -------------------------------
TOP_LEAGUES_IDS = [39, 140, 78, 61, 135, 2, 3, 8]  # Example: Premier, LaLiga, SerieA etc
WC_QUALIFIERS_IDS = [159, 160, 161]  # Example: World Cup qualifiers
LEAGUES_IDS = TOP_LEAGUES_IDS + WC_QUALIFIERS_IDS

# -------------------------------
# Telegram Goal Alert
# -------------------------------
def send_goal_alert(home, away, league, chance):
    message = f"🔥 GOAL ALERT 🔥\nLeague: {league}\nMatch: {home} vs {away}\nChance: {chance}%"
    bot.send_message(OWNER_CHAT_ID, message)

# -------------------------------
# Fetch live matches from Sportmonks
# -------------------------------
def fetch_live_matches():
    url = f"https://api.sportmonks.com/v3/football/livescores?api_token={SPORTMONKS_API}"
    response = requests.get(url).json()
    matches = []

    for match in response.get("data", []):
        league_id = match.get("league_id")
        if league_id in LEAGUES_IDS:
            home_team = match.get("home_team", {}).get("name", "Unknown Home")
            away_team = match.get("away_team", {}).get("name", "Unknown Away")
            league_name = match.get("league", {}).get("name", "Unknown League")
            
            matches.append({
                "home": home_team,
                "away": away_team,
                "league": league_name,
                "stats": {
                    "last_3_min_goals": np.random.randint(0, 2),
                    "shots_on_target": np.random.randint(0, 5),
                    "possession": np.random.randint(40, 60)
                }
            })
    return matches

# -------------------------------
# Main polling loop
# -------------------------------
def main():
    print("Bot started... Fetching live matches every 60 seconds")
    while True:
        try:
            live_matches = fetch_live_matches()
            for m in live_matches:
                stats = m["stats"]
                X = np.array([[stats["last_3_min_goals"], stats["shots_on_target"], stats["possession"]]])
                chance = ml_model.predict_proba(X)[0][1] * 100

                if chance >= 80:
                    send_goal_alert(m["home"], m["away"], m["league"], round(chance, 2))
            time.sleep(60)  # check every minute
        except Exception as e:
            print("Error:", e)
            time.sleep(60)

if __name__ == "__main__":
    main()
