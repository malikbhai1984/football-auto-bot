#!/usr/bin/env python3
import os
import time
import random
import logging
import threading
import requests
from datetime import datetime
from flask import Flask, request
from dotenv import load_dotenv
import telebot

# -------------------- Load ENV --------------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
DOMAIN = os.getenv("DOMAIN")
PORT = int(os.getenv("PORT", 8080))
THE_ODDS_API_KEY = os.getenv("API_KEY")  # The Odds API
SPORT_KEY = "soccer"  # sport key for The Odds API

# -------------------- Logging --------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("BOT")

# -------------------- Validation --------------------
missing = [k for k in ("BOT_TOKEN", "OWNER_CHAT_ID", "DOMAIN", "THE_ODDS_API_KEY") if not os.getenv(k)]
if missing:
    log.error("Missing ENV vars: %s", missing)
    raise SystemExit(f"Missing environment variables: {', '.join(missing)}")

# -------------------- Bot & App --------------------
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

# -------------------- Config --------------------
POLL_INTERVAL_MIN = 300  # 5 min
POLL_INTERVAL_MAX = 420  # 7 min
active_chats = set()
last_sent_for_match = {}

# -------------------- Helpers --------------------
def safe_request(url, method="get", **kwargs):
    try:
        r = requests.request(method, url, timeout=15, **kwargs)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning("HTTP request failed: %s %s", url, e)
        return None

# -------------------- Fetch Live Odds --------------------
def get_live_odds():
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT_KEY}/odds"
    params = {
        "apiKey": THE_ODDS_API_KEY,
        "regions": "uk",
        "markets": "h2h,totals",
        "oddsFormat": "decimal",
        "dateFormat": "iso"
    }
    data = safe_request(url, params=params)
    return data if data else []

# -------------------- Prediction Logic --------------------
def implied_prob_from_decimal(odds):
    try:
        return 1.0 / float(odds)
    except Exception:
        return 0.0

def normalize_probs(probs):
    s = sum(probs.values())
    if s <= 0:
        return {k: 0.0 for k in probs}
    return {k: v / s for k, v in probs.items()}

def simple_prediction_from_odds(odds_entry):
    try:
        bookmakers = odds_entry.get("bookmakers", [])
        if not bookmakers:
            return None
        bm = bookmakers[0]
        markets = {m["key"]: m for m in bm.get("markets", [])}
    except Exception:
        return None

    h2h = markets.get("h2h", {}).get("outcomes", [])
    totals = markets.get("totals", {}).get("outcomes", [])

    home_p = away_p = draw_p = 0.0
    names = [o.get("name","").lower() for o in h2h]
    for o in h2h:
        name = o.get("name","").lower()
        price = o.get("price",0)
        p = implied_prob_from_decimal(price)
        if "home" in name or name in (odds_entry.get("home_team","").lower(),):
            home_p = p
        elif "away" in name or name in (odds_entry.get("away_team","").lower(),):
            away_p = p
        elif "draw" in name or "x" in name:
            draw_p = p
    if home_p + away_p + draw_p == 0 and len(h2h) >= 2:
        vals = [implied_prob_from_decimal(x["price"]) for x in h2h[:3]]
        home_p, draw_p, away_p = (vals + [0,0,0])[:3]

    probs = normalize_probs({"home": home_p, "draw": draw_p, "away": away_p})

    over25_p = under25_p = None
    for t in totals:
        name = t.get("name","").lower()
        price = t.get("price",0)
        if "over 2.5" in name:
            over25_p = implied_prob_from_decimal(price)
        if "under 2.5" in name:
            under25_p = implied_prob_from_decimal(price)

    suggestion = {"win_probs": probs, "best_pick": max(probs, key=probs.get)}
    if over25_p and under25_p:
        tot = normalize_probs({"over25": over25_p, "under25": under25_p})
        suggestion["totals"] = tot
        suggestion["totals_pick"] = "over25" if tot["over25"] > tot["under25"] else "under25"

    return suggestion

# -------------------- Format Message --------------------
def format_match_message(match, prediction):
    home = match.get("home_team","Home")
    away = match.get("away_team","Away")
    commence = match.get("commence_time","")
    try:
        dt = datetime.fromisoformat(commence.replace("Z","+00:00"))
        commence_str = dt.strftime("%Y-%m-%d %H:%M UTC")
    except:
        commence_str = commence

    msg = f"<b>{home} vs {away}</b>\nTime: {commence_str}\n"
    if prediction:
        wp = prediction["win_probs"]
        msg += f"Win probabilities:\n - {home}: {wp['home']*100:.1f}%\n - Draw: {wp['draw']*100:.1f}%\n - {away}: {wp['away']*100:.1f}%\n"
        msg += f"Best pick: <b>{prediction['best_pick'].upper()}</b>\n"
        if prediction.get("totals"):
            t = prediction["totals"]
            msg += f"Totals pick: <b>{prediction['totals_pick']}</b> (Over25: {t['over25']*100:.1f}%, Under25: {t['under25']*100:.1f}%)\n"
    else:
        msg += "No prediction available.\n"
    msg += "\n---\nThis is a probability-based suggestion only."
    return msg

# -------------------- Background Auto-Worker --------------------
def auto_worker():
    log.info("Background worker started...")
    while True:
        try:
            live_matches = get_live_odds()
            now = time.time()
            for match in live_matches:
                match_id = match.get("id") or match.get("key") or match.get("sport_key")
                key = str(match_id)
                last = last_sent_for_match.get(key,0)
                if now - last < 300:  # 5 min cooldown per match
                    continue
                pred = simple_prediction_from_odds(match)
                msg = format_match_message(match, pred)
                for chat_id in active_chats:
                    try:
                        bot.send_message(chat_id, msg)
                    except Exception as e:
                        log.warning("Send failed: %s", e)
                last_sent_for_match[key] = now
            interval = random.randint(POLL_INTERVAL_MIN,POLL_INTERVAL_MAX)
            time.sleep(interval)
        except Exception as e:
            log.error("Worker error: %s", e)
            time.sleep(POLL_INTERVAL_MIN)

threading.Thread(target=auto_worker, daemon=True).start()

# -------------------- Bot Commands --------------------
@bot.message_handler(commands=["start","help"])
def start_help(msg):
    bot.reply_to(msg, "Salaam! Use /live to get live updates every 5–7 minutes.")

@bot.message_handler(commands=["live"])
def enable_live(msg):
    chat_id = msg.chat.id
    if chat_id in active_chats:
        bot.reply_to(msg, "Live updates already enabled.")
    else:
        active_chats.add(chat_id)
        bot.reply_to(msg, "✅ Live updates enabled!")

@bot.message_handler(commands=["stop"])
def stop_live(msg):
    chat_id = msg.chat.id
    if chat_id in active_chats:
        active_chats.remove(chat_id)
        bot.reply_to(msg, "Live updates stopped.")
    else:
        bot.reply_to(msg, "No active live updates.")

# -------------------- Webhook --------------------
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json(force=True)
    bot.process_new_updates([telebot.types.Update.de_json(update)])
    return "OK", 200

@app.route("/", methods=["GET"])
def home():
    return "Bot running!"

def set_webhook():
    url = f"{DOMAIN}/{BOT_TOKEN}"
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=url)
        log.info(f"Webhook set: {url}")
    except Exception as e:
        log.error(f"Webhook error: {e}")

# -------------------- Run --------------------
if __name__ == "__main__":
    set_webhook()
    app.run(host="0.0.0.0", port=PORT)
