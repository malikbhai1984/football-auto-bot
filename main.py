import os
import requests
import telebot
import time
from datetime import datetime
from flask import Flask, request
import threading

# Telegram bot + Flask setup
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
API_KEY = os.getenv("API_KEY")
DOMAIN = os.getenv("DOMAIN")
AUTO_INTERVAL_SECONDS = int(os.getenv("AUTO_INTERVAL_SECONDS", 300))
CONFIDENCE_THRESHOLD = int(os.getenv("CONFIDENCE_THRESHOLD", 85))
USE_WEBHOOK = os.getenv("USE_WEBHOOK", "False").lower() == "true"

PORT = int(os.getenv("PORT", 8080))

if not all([BOT_TOKEN, OWNER_CHAT_ID, API_KEY, DOMAIN]):
    raise ValueError("❌ BOT_TOKEN, OWNER_CHAT_ID, API_KEY, or DOMAIN missing!")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
API_URL = "https://apiv3.apifootball.com"
