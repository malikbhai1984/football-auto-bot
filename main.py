import os
from dotenv import load_dotenv
load_dotenv()

import telebot
import time
from datetime import datetime
import requests






import os
import telebot
import asyncio
import re
import requests
from flask import Flask, request

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
API_FOOTBALL_KEY = os.environ.get("API_KEY")
BOT_NAME = os.environ.get("BOT_NAME", "Football Bot")

# Safety check
if not BOT_TOKEN or not OWNER_CHAT_ID:
    raise ValueError("❌ BOT_TOKEN or OWNER_CHAT_ID missing in Railway variables!")

print(f"✅ Loaded BOT_TOKEN: {BOT_TOKEN[:10]}...")
print(f"✅ OWNER_CHAT_ID: {OWNER_CHAT_ID}")
print(f"✅ BOT_NAME: {BOT_NAME}")

# ✅ IMPORTANT: Create bot instance BEFORE using @bot.message_handler
bot = telebot.TeleBot(BOT_TOKEN)




