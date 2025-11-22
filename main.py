

import os import requests import time import logging import json import pandas as pd from datetime import datetime from flask import Flask, request from dotenv import load_dotenv

----------------------------

ENV LOAD

----------------------------

load_dotenv() API_FOOTBALL = os.getenv("API_FOOTBALL") API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY") BOT_TOKEN = os.getenv("BOT_TOKEN") OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")

----------------------------

FLASK APP

----------------------------

app = Flask(name) logging.basicConfig(level=logging.INFO)

----------------------------

SAFE HTTP REQUEST

----------------------------

def safe_get(url): try: r = requests.get(url, timeout=10) if r.status_code != 200: logging.error(f"HTTP {r.status_code} → {url}") return None return r.json() except Exception as e: logging.error(f"Request Error: {e}") return None

----------------------------

FETCH LIVE MATCHES

----------------------------

def get_live_matches(): url = f"{API_FOOTBALL}/?action=get_events&match_live=1&APIkey={API_FOOTBALL_KEY}" return safe_get(url)

----------------------------

FETCH HISTORICAL H2H

----------------------------

def get_historical(h_id, a_id): url = f"{API_FOOTBALL}/?action=get_H2H&firstTeamId={h_id}&secondTeamId={a_id}&APIkey={API_FOOTBALL_KEY}" return safe_get(url)

----------------------------

ML PLACEHOLDER (Later trained models)

----------------------------

def ml_predict(features: dict): # Placeholder. Replace with real model prediction return { "winner": "HOME", "over25": 0.62, "btts": 0.48, "last10_goal": 0.14, }

----------------------------

FINAL PREDICTOR

----------------------------

def process_match(match): try: h_id = match.get("match_hometeam_id") a_id = match.get("match_awayteam_id")

h2h = get_historical(h_id, a_id)
    if h2h is None:
        h2h = []

    features = {
        "home_team": match.get("match_hometeam_name"),
        "away_team": match.get("match_awayteam_name"),
        "league": match.get("league_name"),
        "h2h": len(h2h),
        "home_goals": int(match.get("match_hometeam_score", 0) or 0),
        "away_goals": int(match.get("match_awayteam_score", 0) or 0),
    }

    pred = ml_predict(features)

    return {
        "match": f"{features['home_team']} vs {features['away_team']}",
        "winner": pred["winner"],
        "over25": pred["over25"],
        "btts": pred["btts"],
        "last10": pred["last10_goal"],
        "timestamp": datetime.utcnow().isoformat()
    }

except Exception as e:
    logging.error(f"Processing Error: {e}")
    return None

----------------------------

ROUTES

----------------------------

@app.route("/") def home(): return "Football ML Bot Running"

@app.route("/live") def live(): live_data = get_live_matches() if not live_data: return {"error": "No Live Matches"}

output = []
for m in live_data:
    out = process_match(m)
    if out:
        output.append(out)
return json.dumps(output, indent=4)

----------------------------

MAIN

----------------------------

if name == "main": app.run(host="0.0.0.0", port=8080)
