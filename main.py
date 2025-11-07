import os
from dotenv import load_dotenv
load_dotenv()

import telebot
import time
from datetime import datetime
import requests






import asyncio
import re
import requests

API_FOOTBALL_KEY = os.environ.get("API_KEY")

# -------------------------------
# Helper function to fetch match data
# -------------------------------
def get_fixture_stats(team1, team2):
    try:
        url = f"https://v3.football.api-sports.io/fixtures/headtohead?h2h={team1}-{team2}"
        headers = {"x-apisports-key": API_FOOTBALL_KEY}
        r = requests.get(url, headers=headers)
        data = r.json()

        if not data.get("response"):
            return None

        fixture = data["response"][0]["teams"]
        home = fixture["home"]["name"]
        away = fixture["away"]["name"]
        home_wins = fixture["home"]["winner"]
        away_wins = fixture["away"]["winner"]

        # Simplified probability calculation (demo logic)
        stats = {
            "home_prob": 50 + (5 if home_wins else -5),
            "away_prob": 50 + (5 if away_wins else -5),
            "over25_prob": 70,
            "btts_prob": 68,
        }
        return {"home": home, "away": away, "stats": stats}

    except Exception as e:
        print("⚠️ Error in get_fixture_stats:", e)
        return None

# -------------------------------
# Intelligent command handler
# -------------------------------
@bot.message_handler(func=lambda msg: True)
def handle_message(msg):
    text = msg.text.lower()

    # Find if two team names mentioned
    match = re.findall(r"([A-Za-z\s]+)\s+vs\s+([A-Za-z\s]+)", text)
    if match:
        team1, team2 = match[0]
        fixture = get_fixture_stats(team1.strip(), team2.strip())

        if fixture:
            s = fixture["stats"]
            if s["over25_prob"] >= 85:
                reply = (
                    f"🔹 Final 85%+ Confirmed Bet: Over 2.5 Goals\n"
                    f"💰 Confidence Level: {s['over25_prob']}%\n"
                    f"📊 Reasoning: {fixture['home']} scored 2+ in 4/5, {fixture['away']} conceded 2+ in 3/5.\n"
                    f"🔥 Odds Range: 1.70–1.85\n⚠️ Risk Note: Defensive fatigue possible."
                )
            elif s["btts_prob"] >= 85:
                reply = (
                    f"🔹 Final 85%+ Confirmed Bet: BTTS - Yes\n"
                    f"💰 Confidence Level: {s['btts_prob']}%\n"
                    f"📊 Reasoning: Both sides averaging 1.8+ goals recently.\n"
                    f"🔥 Odds Range: 1.80–2.00\n⚠️ Risk Note: Watch for early red cards."
                )
            else:
                reply = "❌ NO 85%+ BET FOUND"
        else:
            reply = "❌ Match not found or invalid team names."

        bot.reply_to(msg, reply)
        return

    # Fallback if user says anything else
    bot.reply_to(msg, "⚽ Send me like: 'Levante vs Celta Vigo 85%' to get the best bet analysis.")

# -------------------------------
# Auto 5-minute background job
# -------------------------------
async def poll_live():
    while True:
        try:
            url = "https://v3.football.api-sports.io/fixtures?live=all"
            headers = {"x-apisports-key": API_FOOTBALL_KEY}
            r = requests.get(url, headers=headers)
            data = r.json()

            live_matches = data.get("response", [])
            if not live_matches:
                print("[No live matches right now]")
            else:
                for match in live_matches:
                    home = match["teams"]["home"]["name"]
                    away = match["teams"]["away"]["name"]

                    # Simple random confidence example (replace with logic)
                    confidence = 85
                    message = (
                        f"⚽ 85%+ Confirmed Bet Update\n"
                        f"Match: {home} vs {away}\n"
                        f"Bet: Over 2.5 Goals\n"
                        f"Confidence: {confidence}%"
                    )
                    bot.send_message(OWNER_CHAT_ID, message)
        except Exception as e:
            print("⚠️ Error in poll_live:", e)
        await asyncio.sleep(300)  # every 5 minutes

# -------------------------------
# Run bot
# -------------------------------
async def main():
    asyncio.create_task(poll_live())  # background task
    print("🏁 Intelligent Bet Bot running with live updates...")
    bot.infinity_polling()

if __name__ == "__main__":
    asyncio.run(main())

