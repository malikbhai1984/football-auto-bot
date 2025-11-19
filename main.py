import os
import requests
import telebot
import time
import random
from datetime import datetime
from flask import Flask, request
import threading
from dotenv import load_dotenv

# -------------------------
# Load environment variables
# -------------------------
load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID"))
API_KEY = os.environ.get("API_KEY")
DOMAIN = os.environ.get("DOMAIN")
PORT = int(os.environ.get("PORT", 8080))
CONFIDENCE_THRESHOLD = int(os.environ.get("CONFIDENCE_THRESHOLD", 85))
AUTO_INTERVAL_SECONDS = int(os.environ.get("AUTO_INTERVAL_SECONDS", 300))
USE_WEBHOOK = os.environ.get("USE_WEBHOOK", "true").lower() == "true"

if not all([BOT_TOKEN, OWNER_CHAT_ID, API_KEY, DOMAIN]):
    raise ValueError("❌ Missing required environment variables!")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
API_URL = "https://apiv3.apifootball.com"

# -------------------------
# Fetch live matches
# -------------------------
def fetch_live_matches():
    try:
        url = (
            f"{API_URL}/?action=get_events&APIkey={API_KEY}&"
            f"from={datetime.now().strftime('%Y-%m-%d')}&"
            f"to={datetime.now().strftime('%Y-%m-%d')}"
        )
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return [m for m in data if m.get("match_live")_]()
