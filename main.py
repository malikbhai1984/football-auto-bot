"""
Telegram Live Odds + Live Score + Simple Prediction Bot
Integrates:
 - The Odds API (https://the-odds-api.com)  -> realtime odds
 - API-Football (https://www.api-football.com) -> fixtures / live scores / stats

Environment variables (use .env):
 - TELEGRAM_TOKEN
 - THE_ODDS_API_KEY
 - API_FOOTBALL_KEY
"""

import os
import time
import threading
import math
import requests
import logging
from datetime import datetime, timezone
import telebot
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
THE_ODDS_API_KEY = os.getenv("THE_ODDS_API_KEY")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")

if not (TELEGRAM_TOKEN and THE_ODDS_API_KEY and API_FOOTBALL_KEY):
    raise SystemExit("Please set TELEGRAM_TOKEN, THE_ODDS_API_KEY and API_FOOTBALL_KEY in environment or .env file")

# Initialize bot
bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="HTML")

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ----- Config -----
POLL_INTERVAL_SECONDS = 30     # how often the bot fetches updates (can change)
TARGET_REGIONS = "uk"          # for the-odds-api regions param, change as needed
MARKETS = "h2h,totals"         # markets we want: head-to-head (1X2) and totals (over/under)
LEAGUE_FILTER = None           # optionally set like "eng.1" for English Premier League slug used by the-odds-api
CHAT_WHITELIST = None          # list of chat ids allowed to use bot; None = public

# A simple in-memory cache to avoid spamming same updates
last_sent_for_match = {}

# ---------- Helper API functions ----------

def get_odds_for_sport(sport_key="soccer_epl"):
    """
    Uses The Odds API v4 to fetch odds for a sport.
    sport_key examples: 'soccer_epl', 'soccer_world_cup', etc.
    If you want all soccer: use 'soccer' or specific league slug.
    """
    base = "https://api.the-odds-api.com/v4/sports"
    endpoint = f"{base}/{sport_key}/odds"
    params = {
        "apiKey": THE_ODDS_API_KEY,
        "regions": TARGET_REGIONS,
        "markets": "h2h,totals",
        "oddsFormat": "decimal"
    }
    if LEAGUE_FILTER:
        params["bookmakers"] = LEAGUE_FILTER
    try:
        r = requests.get(endpoint, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logging.warning("Failed to fetch odds: %s", e)
        return []

def get_upcoming_live_matches_from_api_football(day_from=None, day_to=None):
    """
    Example: fetch fixtures from API-Football
    API-Football docs: use 'fixtures' endpoint
    This returns fixtures for a given date range.
    """
    endpoint = "https://v3.football.api-sports.io/fixtures"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    params = {}
    if day_from:
        params["from"] = day_from
    if day_to:
        params["to"] = day_to
    # Add live parameter if you want live matches: status=LIVE
    try:
        r = requests.get(endpoint, headers=headers, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data.get("response", [])
    except Exception as e:
        logging.warning("Failed to fetch fixtures from API-Football: %s", e)
        return []

def get_live_fixture_details_api_football(fixture_id):
    """
    Fetch detailed fixture by id (lineups, events, stats) from API-Football
    """
    endpoint = "https://v3.football.api-sports.io/fixtures"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    params = {"id": fixture_id}
    try:
        r = requests.get(endpoint, headers=headers, params=params, timeout=12)
        r.raise_for_status()
        data = r.json()
        return data.get("response", [])
    except Exception as e:
        logging.warning("Failed to fetch fixture details: %s", e)
        return []

# ---------- Prediction logic (simple) ----------

def implied_prob_from_decimal(odds):
    """ Convert decimal odds to implied probability (not normalized for vig) """
    try:
        return 1.0/float(odds)
    except Exception:
        return 0.0

def normalize_probs(probs):
    """ Normalize a dict of probs so they sum to 1 """
    s = sum(probs.values())
    if s <= 0:
        return {k: 0.0 for k in probs}
    return {k: v/s for k, v in probs.items()}

def simple_prediction_from_odds_and_stats(odds_entry, match_stats=None):
    """
    Build a small combined prediction score.
    odds_entry: the object from the-odds-api for one match
    match_stats: optional dict with additional info (e.g., form, xG) from API-Football
    Returns a dict with probabilities & suggested markets.
    """
    # Collect best bookmakers (first bookmaker entry)
    try:
        bookmakers = odds_entry.get("bookmakers", [])
        if not bookmakers:
            return None
        bm = bookmakers[0]
        markets = {m["key"]: m for m in bm.get("markets", [])}
    except Exception:
        return None

    # h2h outcomes
    h2h = markets.get("h2h", {}).get("outcomes", [])
    totals = markets.get("totals", {}).get("outcomes", [])

    # Safe defaults
    home_p = away_p = draw_p = 0.0
    if h2h:
        # find outcomes by name ordering depends on provider
        # We'll map by 'name' field
        for o in h2h:
            name = o.get("name", "").lower()
            price = o.get("price", 0)
            p = implied_prob_from_decimal(price)
            if name in ["home", odds_entry.get("home_team","").lower(), odds_entry.get("home_team","")[:6].lower()]:
                home_p = p
            elif name in ["away", odds_entry.get("away_team","").lower(), odds_entry.get("away_team","")[:6].lower()]:
                away_p = p
            elif name in ["draw", "x", "tie"]:
                draw_p = p
        # fallback: if still zero, just take first three
        if home_p + away_p + draw_p == 0 and len(h2h) >= 2:
            # some markets omit draw (moneyline), so handle 2 outcomes
            if len(h2h) == 2:
                home_p = implied_prob_from_decimal(h2h[0]["price"])
                away_p = implied_prob_from_decimal(h2h[1]["price"])
                draw_p = 0.0
            else:
                # try first three
                vals = [implied_prob_from_decimal(x["price"]) for x in h2h[:3]]
                home_p, draw_p, away_p = (vals + [0,0,0])[:3]

    # Normalize
    probs = normalize_probs({"home": home_p, "draw": draw_p, "away": away_p})

    # Totals: check Over/Under 2.5 if available
    over25_p = under25_p = None
    for t in totals:
        # total outcomes often have 'name': 'Over 2.5' or 'Under 2.5'
        name = t.get("name", "")
        if "over 2.5" in name.lower():
            over25_p = implied_prob_from_decimal(t.get("price", 0))
        elif "under 2.5" in name.lower():
            under25_p = implied_prob_from_decimal(t.get("price", 0))

    # Basic blending with stats (if provided)
    # If match_stats contains 'goals_avg' or 'btts_likelihood', we can adjust slightly:
    adj_home = probs["home"]
    adj_away = probs["away"]
    if match_stats:
        # Example adjustments (very basic)
        # If home form strong, add 0.02 to home
        hf = match_stats.get("home_form_strength", 0)   # expected in 0..1
        af = match_stats.get("away_form_strength", 0)
        adj_home = adj_home * (1 + 0.1 * (hf - af))
        adj_away = adj_away * (1 + 0.1 * (af - hf))
        probs = normalize_probs({"home": adj_home, "draw": probs["draw"], "away": adj_away})

    # Suggest top markets
    suggestion = {
        "win_probs": probs,
        "best_pick": max(probs, key=probs.get),
    }

    # Suggest over/under if available
    if over25_p and under25_p:
        tot_probs = normalize_probs({"over25": over25_p, "under25": under25_p})
        suggestion["totals"] = tot_probs
        suggestion["totals_pick"] = "over25" if tot_probs["over25"] > tot_probs["under25"] else "under25"

    return suggestion

# ---------- Bot functions ----------

def format_match_message(odds_entry, prediction):
    """Return a nicely formatted HTML message for Telegram."""
    home = odds_entry.get("home_team", "Home")
    away = odds_entry.get("away_team", "Away")
    commence = odds_entry.get("commence_time")
    commence_str = commence or ""
    try:
        # pretty time if available
        commence_dt = datetime.fromisoformat(commence.replace("Z", "+00:00"))
        commence_str = commence_dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        pass

    # odds top bookmaker summary
    bm_name = odds_entry.get("bookmakers", [{}])[0].get("title", "bookmaker")
    msg = f"<b>{home} vs {away}</b>\nTime: {commence_str}\nBookmaker: {bm_name}\n\n"

    if prediction:
        wp = prediction["win_probs"]
        msg += f"Win probabilities (implied):\n - {home}: {wp['home']*100:.1f}%\n - Draw: {wp['draw']*100:.1f}%\n - {away}: {wp['away']*100:.1f}%\n\n"
        msg += f"Best pick: <b>{prediction['best_pick'].upper()}</b>\n"
        if prediction.get("totals"):
            t = prediction["totals"]
            msg += f"Totals pick: <b>{prediction['totals_pick']}</b> (Over25: {t['over25']*100:.1f}%, Under25: {t['under25']*100:.1f}%)\n"
    else:
        msg += "No prediction could be produced for this match."

    msg += "\n---\nThis is a <i>probability-based</i> suggestion for analysis only. Not financial advice."
    return msg

def process_and_send_updates(chat_id):
    """
    Core loop: fetch odds, build predictions, send messages if changed.
    """
    logging.info("Fetching odds...")
    # sport key: 'soccer' gets more generic; pick specific league slugs if needed
    # To keep it broad, we'll try 'soccer' first (but some endpoints require league-specific slugs)
    # If your API plan restricts endpoints, change sport_key accordingly.
    sport_key = "soccer"
    odds_list = get_odds_for_sport(sport_key)

    for match in odds_list:
        # Use match id provided by the-odds-api
        match_id = match.get("id")
        home = match.get("home_team")
        away = match.get("away_team")
        key = f"{match_id}"

        # Skip if previously sent within 60s
        now = time.time()
        last = last_sent_for_match.get(key, 0)
        if now - last < 30:
            continue

        # Optionally fetch match stats from API-Football - we skip heavy calls for every match,
        # but you can use fixture id mapping to query exact fixture when needed.
        # For demonstration, we won't call API-Football for each match here to keep within rate limits.
        match_stats = None

        prediction = simple_prediction_from_odds_and_stats(match, match_stats)
        if not prediction:
            continue

        # Compose message
        msg = format_match_message(match, prediction)
        # Send message
        try:
            bot.send_message(chat_id, msg)
            last_sent_for_match[key] = now
            logging.info("Sent update for %s vs %s to %s", home, away, chat_id)
        except Exception as e:
            logging.warning("Failed to send message: %s", e)

# ---------- Bot command handlers ----------

@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    txt = (
        "Salaam! Main live odds + basic prediction bot hoon.\n\n"
        "Commands:\n"
        "/live <chat_id> - start sending live odds to this chat (owner only)\n"
        "/stop - stop live updates in this chat\n"
        "/odds - fetch current odds snapshot (single update)\n"
        "/help - this help\n\n"
        "Make sure you run this bot on a server to keep it online."
    )
    bot.reply_to(message, txt)

# simple in-memory registry of active chats
active_chats = set()

@bot.message_handler(commands=["live"])
def cmd_live(message):
    chat_id = message.chat.id
    # Optionally restrict who can start
    if CHAT_WHITELIST and chat_id not in CHAT_WHITELIST:
        bot.reply_to(message, "You are not authorized to start live updates.")
        return

    if chat_id in active_chats:
        bot.reply_to(message, "Live updates already active in this chat.")
    else:
        active_chats.add(chat_id)
        bot.reply_to(message, "✅ Live updates enabled. You will receive odds & predictions periodically.")
        logging.info("Enabled live updates for chat %s", chat_id)

@bot.message_handler(commands=["stop"])
def cmd_stop(message):
    chat_id = message.chat.id
    if chat_id in active_chats:
        active_chats.remove(chat_id)
        bot.reply_to(message, "Live updates stopped for this chat.")
    else:
        bot.reply_to(message, "Live updates are not active in this chat.")

@bot.message_handler(commands=["odds"])
def cmd_odds(message):
    chat_id = message.chat.id
    bot.reply_to(message, "Fetching fresh odds... please wait.")
    # fetch and send one snapshot to user
    odds = get_odds_for_sport("soccer")
    if not odds:
        bot.send_message(chat_id, "No odds returned or API error.")
        return

    # send top 5 matches as snapshot
    count = 0
    for m in odds:
        pred = simple_prediction_from_odds_and_stats(m, None)
        bot.send_message(chat_id, format_match_message(m, pred))
        count += 1
        if count >= 5:
            break

# ---------- Background worker to push updates to active chats ----------

def background_worker():
    while True:
        if active_chats:
            for chat_id in list(active_chats):
                try:
                    process_and_send_updates(chat_id)
                except Exception as e:
                    logging.warning("Error processing updates for %s: %s", chat_id, e)
        time.sleep(POLL_INTERVAL_SECONDS)

# Start background worker thread
worker_thread = threading.Thread(target=background_worker, daemon=True)
worker_thread.start()

# Start bot (long polling)
if __name__ == "__main__":
    logging.info("Bot started. Listening for commands...")
    bot.infinity_polling()
