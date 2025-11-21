import os
import requests
import numpy as np
import telebot
from sklearn.linear_model import LogisticRegression
import time
from flask import Flask
from threading import Thread

# -------------------------------
# Environment Variables (Assumed to be set by Railway)
# -------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Convert OWNER_CHAT_ID to int, defaulting to 0 if not found/invalid
try:
    OWNER_CHAT_ID = int(os.getenv("OWNER_CHAT_ID", 0))
except ValueError:
    OWNER_CHAT_ID = 0
SPORTMONKS_API = os.getenv("SPORTMONKS_API")

# Initialize Telegram Bot
if BOT_TOKEN:
    bot = telebot.TeleBot(BOT_TOKEN)
else:
    print("WARNING: BOT_TOKEN not found. Telegram functionality disabled.")
    # Create a dummy bot object to prevent immediate errors
    class DummyBot:
        def send_message(self, chat_id, text):
            print(f"DummyBot: Sending message to {chat_id}: {text}")
    bot = DummyBot()


# -------------------------------
# Optional Flask app for healthcheck (Web Process)
# -------------------------------
app = Flask(__name__)

@app.route("/")
def health():
    return "Bot worker is running!", 200

# -------------------------------
# ML Model (Dummy LogisticRegression)
# -------------------------------
ml_model = LogisticRegression()
# Train the dummy model once at startup
try:
    X_dummy = np.random.rand(50, 3)
    y_dummy = np.random.randint(0, 2, 50)
    ml_model.fit(X_dummy, y_dummy)
except Exception as e:
    print(f"Error initializing ML model: {e}")

# -------------------------------
# Leagues IDs
# -------------------------------
# Premier, LaLiga, SerieA, Ligue1, Bundesliga, Brazil Serie A, Argentina Liga Profesional, Portugal Liga
TOP_LEAGUES_IDS = [39, 140, 78, 61, 135, 2, 3, 8]
WC_QUALIFIERS_IDS = [159, 160, 161]
LEAGUES_IDS = TOP_LEAGUES_IDS + WC_QUALIFIERS_IDS

# -------------------------------
# Telegram Goal Alert
# -------------------------------
def send_goal_alert(home, away, league, chance):
    """Sends the alert message to the owner's chat ID."""
    if not OWNER_CHAT_ID or not BOT_TOKEN:
        print("Alert skipped: OWNER_CHAT_ID or BOT_TOKEN is missing.")
        return

    message = f"🔥 GOAL ALERT 🔥\nLeague: {league}\nMatch: {home} vs {away}\nChance: {round(chance, 2)}%"
    try:
        # Check if OWNER_CHAT_ID is valid before sending
        if OWNER_CHAT_ID > 0:
            bot.send_message(OWNER_CHAT_ID, message)
        else:
            print("Alert not sent: OWNER_CHAT_ID is invalid.")
    except Exception as e:
        print(f"Telegram error sending alert: {e}")

# -------------------------------
# Fetch live matches from Sportmonks
# -------------------------------
def fetch_live_matches():
    """Fetches live football matches from the Sportmonks API."""
    if not SPORTMONKS_API:
        print("Fetch skipped: SPORTMONKS_API is missing.")
        return []

    try:
        # Use a more specific endpoint for live scores if available, or just the main one.
        # Adding a filter for the included leagues would be ideal but sticking to current logic.
        url = f"https://api.sportmonks.com/v3/football/livescores?api_token={SPORTMONKS_API}"
        response = requests.get(url, timeout=15).json()
        matches = []

        for match in response.get("data", []):
            league_id = match.get("league_id")
            if league_id in LEAGUES_IDS:
                # Safely extract nested data
                home_team = match.get("name", "Unknown Match").split(" - ")[0] # Fallback extraction
                away_team = match.get("name", "Unknown Match").split(" - ")[-1]

                # If the names are available under the 'participants' or 'teams' key, use those
                # The provided SportMonks structure in the original code seems slightly off,
                # using mock data for teams for safety. Let's use the safer names:
                home_team = match.get("home_team", {}).get("name", "Unknown Home")
                away_team = match.get("away_team", {}).get("name", "Unknown Away")

                league_name = match.get("league", {}).get("name", "Unknown League")

                matches.append({
                    "home": home_team,
                    "away": away_team,
                    "league": league_name,
                    # Mock stats for the dummy model
                    "stats": {
                        "last_3_min_goals": np.random.randint(0, 2),
                        "shots_on_target": np.random.randint(0, 5),
                        "possession": np.random.randint(40, 60)
                    }
                })
        return matches
    except requests.exceptions.Timeout:
        print("Fetch live matches error: Request timed out.")
        return []
    except Exception as e:
        print(f"Fetch live matches error: {e}")
        return []

# -------------------------------
# Worker Process: Bot Loop
# -------------------------------
def run_worker():
    """The main bot loop for fetching data and sending alerts."""
    print("--- Worker Process (Telegram Bot) started. Fetching every 60 seconds... ---")
    while True:
        try:
            live_matches = fetch_live_matches()
            print(f"Found {len(live_matches)} matches to analyze.")

            for m in live_matches:
                stats = m["stats"]
                # Input features for the dummy model
                X = np.array([[stats["last_3_min_goals"], stats["shots_on_target"], stats["possession"]]])
                # Predict probability for class 1 (goal chance)
                chance = ml_model.predict_proba(X)[0][1] * 100

                if chance >= 80:
                    send_goal_alert(m["home"], m["away"], m["league"], chance)

            # Wait for 60 seconds before the next loop
            time.sleep(60)

        except Exception as e:
            print(f"Worker loop critical error: {e}")
            time.sleep(60) # Wait before retrying

# -------------------------------
# Web Process: Flask Server
# -------------------------------
def run_web():
    """Runs the Flask application for health checks."""
    print("--- Web Process (Flask Healthcheck) started. ---")
    port = int(os.environ.get("PORT", 8080))
    # This will be run by Gunicorn in production (e.g., Railway)
    app.run(host="0.0.0.0", port=port)


# -------------------------------
# Main Entry Point
# -------------------------------
if __name__ == "__main__":
    # Check if we are running as a Web process (default) or a Worker process
    process_type = os.environ.get("PROCESS_TYPE", "web").lower()

    if process_type == "worker":
        # If running as a worker, start the bot loop directly.
        run_worker()
    else:
        # If running as web, or if PROCESS_TYPE is missing/unknown, run the web process.
        # Note: In a real Gunicorn deployment, this path is rarely hit, as Gunicorn imports 'app' directly.
        # But this ensures the web function can be tested locally.
        run_web()
