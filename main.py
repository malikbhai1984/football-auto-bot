import os import telebot import logging from flask import Flask, request from dotenv import load_dotenv import threading import time

---------------------------

Load ENV

---------------------------

load_dotenv() BOT_TOKEN = os.getenv("BOT_TOKEN") OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID") DOMAIN = os.getenv("DOMAIN") PORT = int(os.getenv("PORT", 8080)) API_KEY = os.getenv("API_KEY") SPORTMONKS_API = os.getenv("SPORTMONKS_API") BOT_NAME = os.getenv("BOT_NAME", "MyBetAlert_Bot")

---------------------------

Telegram Bot Init

---------------------------

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)

---------------------------

Flask App Init

---------------------------

app = Flask(name)

---------------------------

Startup SAFE LOGGER

---------------------------

logging.basicConfig(level=logging.INFO) logger = logging.getLogger("BOT")

---------------------------

Background Auto Thread (Your auto prediction)

---------------------------

def background_worker(): while True: try: # Replace this with your real auto update logic bot.send_message(OWNER_CHAT_ID, "⏳ Auto-worker running...") except Exception as e: logger.error(f"Worker Error: {e}") time.sleep(20)  # Run every 20 sec

Start background thread

threading.Thread(target=background_worker, daemon=True).start()

---------------------------

Telegram Webhook Endpoint

---------------------------

@app.route(f"/{BOT_TOKEN}", methods=["POST"]) def telegram_webhook(): update = request.get_data().decode("utf-8") bot.process_new_updates([telebot.types.Update.de_json(update)]) return "OK", 200

---------------------------

Test routes

---------------------------

@app.route("/") def home(): return "Bot Running Successfully!"

---------------------------

Set WEBHOOK at startup

---------------------------

def set_webhook(): webhook_url = f"{DOMAIN}/{BOT_TOKEN}" try: bot.remove_webhook() time.sleep(1) bot.set_webhook(url=webhook_url) logger.info(f"Webhook Set: {webhook_url}") except Exception as e: logger.error(f"Webhook Error: {e}")

---------------------------

Run APP

---------------------------

if name == "main": try: set_webhook() except Exception as e: logger.error(f"Startup webhook crash: {e}")

app.run(host="0.0.0.0", port=PORT)
