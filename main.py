import os
import requests
import numpy as np
import telebot
from dotenv import load_dotenv
from sklearn.linear_model import LogisticRegression
import time
from flask import Flask

# -------------------------------
# Load environment variables
# -------------------------------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
SPORTMONKS_API = os.getenv("API_KEY")  # Changed to API_KEY

if not all([BOT_TOKEN, OWNER_CHAT_ID, SPORTMONKS_API]):
    raise ValueError("Missing required environment variables")

try:
    OWNER_CHAT_ID = int(OWNER_CHAT_ID)
except ValueError:
    raise ValueError("OWNER_CHAT_ID must be a valid integer")

bot = telebot.TeleBot(BOT_TOKEN)

# -------------------------------
# Optional Flask app for healthcheck
# -------------------------------
app = Flask(__name__)

@app.route("/")
def health():
    return "Bot is running!", 200

@app.route("/health")
def health_check():
    return "OK", 200

# -------------------------------
# ML Model (Dummy LogisticRegression)
# -------------------------------
print("Training ML model...")
ml_model = LogisticRegression(random_state=42)
X_dummy = np.random.rand(50, 3)
y_dummy = np.random.randint(0, 2, 50)
ml_model.fit(X_dummy, y_dummy)
print("ML model trained successfully")

# -------------------------------
# Leagues IDs
# -------------------------------
TOP_LEAGUES_IDS = [39, 140, 78, 61, 135, 2, 3, 8]  # Premier, LaLiga, SerieA etc
WC_QUALIFIERS_IDS = [159, 160, 161]  # World Cup qualifiers
LEAGUES_IDS = TOP_LEAGUES_IDS + WC_QUALIFIERS_IDS

# -------------------------------
# Telegram Goal Alert
# -------------------------------
def send_goal_alert(home, away, league, chance):
    message = f"🔥 GOAL ALERT 🔥\nLeague: {league}\nMatch: {home} vs {away}\nChance: {chance}%"
    try:
        bot.send_message(OWNER_CHAT_ID, message)
        print(f"Alert sent: {home} vs {away}")
    except Exception as e:
        print(f"Telegram error: {e}")

# -------------------------------
# Fetch live matches from Sportmonks
# -------------------------------
def fetch_live_matches():
    try:
        url = f"https://api.sportmonks.com/v3/football/livescores?api_token={SPORTMONKS_API}&include=league,participants"
        print(f"Fetching live matches from: {url[:50]}...")
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        matches = []

        for match in data.get("data", []):
            league_id = match.get("league_id")
            if league_id in LEAGUES_IDS:
                # Get team names from participants
                home_team = "Unknown Home"
                away_team = "Unknown Away"
                league_name = "Unknown League"
                
                # Extract team names
                participants = match.get("participants", [])
                if len(participants) >= 2:
                    home_team = participants[0].get("name", "Unknown Home")
                    away_team = participants[1].get("name", "Unknown Away")
                
                # Extract league name
                league_data = match.get("league", {})
                if league_data:
                    league_name = league_data.get("name", "Unknown League")

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
        
        print(f"Found {len(matches)} live matches")
        return matches
    except requests.exceptions.RequestException as e:
        print(f"Network error fetching matches: {e}")
        return []
    except Exception as e:
        print(f"Error fetching live matches: {e}")
        return []

# -------------------------------
# Main Bot Loop
# -------------------------------
def start_bot():
    print("Telegram bot started, fetching matches every 60 seconds...")
    
    # Send startup message
    try:
        bot.send_message(OWNER_CHAT_ID, "🤖 Bot started successfully! Monitoring for goals...")
    except Exception as e:
        print(f"Startup message failed: {e}")
    
    while True:
        try:
            live_matches = fetch_live_matches()
            print(f"Processing {len(live_matches)} matches...")
            
            for m in live_matches:
                stats = m["stats"]
                X = np.array([[stats["last_3_min_goals"], stats["shots_on_target"], stats["possession"]]])
                
                try:
                    chance = ml_model.predict_proba(X)[0][1] * 100
                    print(f"Match: {m['home']} vs {m['away']} - Chance: {chance:.2f}%")
                    
                    if chance >= 80:
                        send_goal_alert(m["home"], m["away"], m["league"], round(chance, 2))
                except Exception as e:
                    print(f"ML prediction error: {e}")
                    
            time.sleep(60)
        except KeyboardInterrupt:
            print("Bot stopped by user")
            break
        except Exception as e:
            print(f"Bot loop error: {e}")
            time.sleep(60)

# -------------------------------
# Run Flask + Bot concurrently
# -------------------------------
if __name__ == "__main__":
    print("Starting application...")
    
    # Start bot in a separate thread
    from threading import Thread
    bot_thread = Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Start Flask app
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting Flask app on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
