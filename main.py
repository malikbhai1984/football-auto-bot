import os
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
import telebot
import logging

# ---------------------------
# Load Environment Variables
# ---------------------------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
API_FOOTBALL_KEY = os.getenv("API_KEY")  # api-football first
SPORTMONKS_API = os.getenv("SPORTMONKS_API")  # sportsmonks second

bot = telebot.TeleBot(BOT_TOKEN)

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ---------------------------
# Helper Functions
# ---------------------------

def fetch_live_matches():
    """
    Fetch live matches from API-Football first, fallback to SportMonks
    Returns list of matches with all details
    """
    matches = []
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    
    try:
        url = "https://v3.football.api-sports.io/fixtures?live=all"
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        if "response" in data:
            for match in data["response"]:
                matches.append({
                    "league": match["league"]["name"],
                    "home": match["teams"]["home"]["name"],
                    "away": match["teams"]["away"]["name"],
                    "minute": match["fixture"]["status"]["elapsed"]
                })
    except Exception as e:
        logging.warning(f"API-Football failed: {e}, trying SportMonks fallback.")
        # Fallback to SportMonks
        try:
            sm_url = f"https://soccer.sportmonks.com/api/v2.0/livescores?api_token={SPORTMONKS_API}"
            sm_data = requests.get(sm_url, timeout=10).json()
            for m in sm_data.get("data", []):
                matches.append({
                    "league": m.get("league", {}).get("data", {}).get("name", "Unknown League"),
                    "home": m.get("localTeam", {}).get("data", {}).get("name", "Unknown"),
                    "away": m.get("visitorTeam", {}).get("data", {}).get("name", "Unknown"),
                    "minute": m.get("time", {}).get("minute", 0)
                })
        except Exception as e2:
            logging.error(f"SportMonks also failed: {e2}")
    
    return matches

def generate_predictions(match):
    """
    Dummy ML/AI predictions (replace with your trained model)
    """
    # For now random predictions
    over_prob = round(np.random.uniform(40, 80), 1)
    btts_prob = round(np.random.uniform(50, 85), 1)
    last_10_prob = round(np.random.uniform(10, 30), 1)
    top_scores = [(1,1), (1,0)]
    
    return {
        "Over 0.5-5.5 Goal Probability": f"{over_prob}%",
        "BTTS Probability": f"{btts_prob}%",
        "Last 10-min Goal Probability": f"{last_10_prob}%",
        "Top Correct Scores": top_scores
    }

def send_match_updates():
    matches = fetch_live_matches()
    if not matches:
        bot.send_message(OWNER_CHAT_ID, "⚠️ No live matches right now.")
        return
    
    for match in matches:
        preds = generate_predictions(match)
        message = (
            f"⚽ League: {match.get('league', 'Unknown')}\n"
            f"Match: {match.get('home', 'N/A')} vs {match.get('away', 'N/A')}\n"
            f"Minute: {match.get('minute', '0')}\n"
            f"Over 0.5-5.5 Goal Probability: {preds['Over 0.5-5.5 Goal Probability']}\n"
            f"BTTS Probability: {preds['BTTS Probability']}\n"
            f"Last 10-min Goal Probability: {preds['Last 10-min Goal Probability']}\n"
            f"Top Correct Scores: {preds['Top Correct Scores']}"
        )
        try:
            bot.send_message(OWNER_CHAT_ID, message)
            logging.info(f"Sent update for {match.get('home')} vs {match.get('away')}")
        except Exception as e:
            logging.error(f"Failed to send message: {e}")

# ---------------------------
# Main Loop
# ---------------------------

if __name__ == "__main__":
    logging.info("MyBetAlert_Bot started.")
    while True:
        try:
            send_match_updates()
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
        logging.info("✅ Cycle complete. Waiting 7 minutes...")
        time.sleep(420)  # 7 minutes
