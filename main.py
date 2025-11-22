import os import requests import time import logging import json import pandas as pd from datetime import datetime from flask import Flask, request from dotenv import load_dotenv

----------------------------

ENV LOAD

----------------------------

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN") OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID") API_KEY = os.getenv("API_KEY")  # API-FOOTBALL KEY SPORTMONKS_API = os.getenv("SPORTMONKS_API") BOT_NAME = os.getenv("BOT_NAME") DOMAIN = os.getenv("DOMAIN") PORT = int(os.getenv("PORT", 8080))

API Football Base URL

API_FOOTBALL_BASE = "https://api-football-v1.p.rapidapi.com/v3"

----------------------------

FLASK APP

----------------------------

app = Flask(name) logging.basicConfig(level=logging.INFO)

----------------------------

SAFE HTTP REQUEST

----------------------------

def safe_get(url, headers=None): try: r = requests.get(url, headers=headers, timeout=10) if r.status_code != 200: logging.error(f"HTTP {r.status_code} → {url}") return None return r.json() except Exception as e: logging.error(f"Request Error: {e}") return None

----------------------------

FETCH LIVE MATCHES (API-FOOTBALL)

----------------------------

def get_live_matches(): url = f"{API_FOOTBALL_BASE}/fixtures?live=all" headers = { "X-RapidAPI-Key": API_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com", } return safe_get(url, headers)

----------------------------

FETCH HISTORICAL H2H

----------------------------

def get_historical(h_id, a_id): url = f"{API_FOOTBALL_BASE}/fixtures/headtohead?h2h={h_id}-{a_id}" headers = { "X-RapidAPI-Key": API_KEY, "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com", } return safe_get(url, headers)

----------------------------

ML PLACEHOLDER (REAL MODELS CONNECT LATER)

----------------------------

def ml_predict(features: dict): # Placeholder — later integrate real XGBoost models return { "winner": "DRAW",  # HOME / AWAY / DRAW "over25": 0.66, "btts": 0.52, "last10_goal": 0.21, }

----------------------------

FINAL PREDICTOR

----------------------------

def process_match(match): try: fixture = match.get("fixture", {}) teams = match.get("teams", {}) goals = match.get("goals", {})

h_id = teams.get("home", {}).get("id")
    a_id = teams.get("away", {}).get("id")

    # Fetch H2H
    h2h = get_historical(h_id, a_id)
    if h2h is None:
        h2h = []

    features = {
        "home_team": teams.get("home", {}).get("name"),
        "away_team": teams.get("away", {}).get("name"),
        "league": match.get("league", {}).get("name"),
        "h2h": len(h2h),
        "home_goals": goals.get("home", 0) or 0,
        "away_goals": goals.get("away", 0) or 0,
    }

    pred = ml_predict(features)

    return {
        "match": f"{features['home_team']} vs {features['away_team']}",
        "winner": pred["winner"],
        "over25": pred["over25"],
        "btts": pred["btts"],
        "last10": pred["last10_goal"],
        "timestamp": datetime.utcnow().isoformat(),
    }

except Exception as e:
    logging.error(f"Processing Error: {e}")
    return None

----------------------------

ROUTES

----------------------------

@app.route("/") def home(): return "Football ML Bot Running"

@app.route("/live") def live(): live_data = get_live_matches() if (not live_data) or ("response" not in live_data): return {"error": "No Live Matches"}

output = []
for m in live_data.get("response", []):
    out = process_match(m)
    if out:
        output.append(out)

return json.dumps(output, indent=4)

----------------------------

MAIN

----------------------------

if name == "main": app.run(host="0.0.0.0", port=PORT)
