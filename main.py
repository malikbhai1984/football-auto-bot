import os
from dotenv import load_dotenv
load_dotenv()

import telebot
import time
from datetime import datetime
import requests




@app.route("/" + BOT_TOKEN, methods=["POST"])
def receive_update():
    update = telebot.types.Update.de_json(request.data.decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200





# main.py
import os
import math
import asyncio
import requests
import telebot
from flask import Flask, request
from datetime import datetime

# -------------------------
# Environment / config
# -------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
API_KEY = os.environ.get("API_KEY")
DOMAIN = os.environ.get("DOMAIN", "https://football-auto-bot-production.up.railway.app")
BOT_NAME = os.environ.get("BOT_NAME", "Football Smart Bot")

if not BOT_TOKEN or not OWNER_CHAT_ID or not API_KEY:
    raise ValueError("❌ BOT_TOKEN, OWNER_CHAT_ID and API_KEY must be set in environment variables!")

# Ensure owner id numeric if possible
try:
    OWNER_CHAT_ID_INT = int(OWNER_CHAT_ID)
except:
    OWNER_CHAT_ID_INT = OWNER_CHAT_ID

API_BASE = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# -------------------------
# Flask + Telebot init
# -------------------------
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

# Avoid duplicate alerts
sent_alerts = set()

# -------------------------
# Helpers
# -------------------------
def safe_get(d, *keys, default=None):
    v = d
    try:
        for k in keys:
            if isinstance(v, dict):
                v = v.get(k, {})
            else:
                return default
        return v if v != {} else default
    except Exception:
        return default

def roundp(x):
    try:
        return int(round(x))
    except:
        return 0

# -------------------------
# API helpers
# -------------------------
def fetch_fixtures_search(home, away):
    """
    Search fixtures by team name keywords. Return first matching fixture object or None.
    """
    try:
        q = home
        url = f"{API_BASE}/fixtures?search={requests.utils.quote(q)}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json().get("response", [])
        for f in data:
            away_name = safe_get(f, "teams", "away", "name", default="").lower()
            home_name = safe_get(f, "teams", "home", "name", default="").lower()
            if away.lower() in away_name and home.lower() in home_name:
                return f
        # fallback: search by away then match home
        q2 = away
        url2 = f"{API_BASE}/fixtures?search={requests.utils.quote(q2)}"
        r2 = requests.get(url2, headers=HEADERS, timeout=15)
        data2 = r2.json().get("response", [])
        for f in data2:
            if home.lower() in safe_get(f, "teams", "home", "name", default="").lower():
                return f
    except Exception as e:
        print("fetch_fixtures_search error:", e)
    return None

def fetch_team_stats(team_id, league_id=None, season=None):
    """
    Fetch teams/statistics from API-Football. Returns response dict or {}.
    """
    try:
        url = f"{API_BASE}/teams/statistics?team={team_id}"
        if league_id:
            url += f"&league={league_id}"
        if season:
            url += f"&season={season}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        return r.json().get("response", {}) or {}
    except Exception as e:
        print("fetch_team_stats error:", e)
        return {}

# -------------------------
# Core heuristics & analysis
# -------------------------
def compute_probabilities_from_fixture(f):
    """
    Compute market probabilities for a fixture (live or upcoming).
    Returns dict with probabilities and helper fields.
    """
    try:
        home = safe_get(f, "teams", "home", "name", default="Home")
        away = safe_get(f, "teams", "away", "name", default="Away")
        home_id = safe_get(f, "teams", "home", "id", default=None)
        away_id = safe_get(f, "teams", "away", "id", default=None)
        league = safe_get(f, "league", "id")
        season = safe_get(f, "league", "season")

        gh = safe_get(f, "goals", "home", default=0) or 0
        ga = safe_get(f, "goals", "away", default=0) or 0
        total = gh + ga
        minute = safe_get(f, "fixture", "status", "elapsed", default=0) or 0
        status_short = safe_get(f, "fixture", "status", "short", default="NS")

        # fetch team stats (safely)
        h_stats = fetch_team_stats(home_id, league_id=league, season=season) if home_id else {}
        a_stats = fetch_team_stats(away_id, league_id=league, season=season) if away_id else {}

        # average goals (fallback to 1.2)
        try:
            h_avg = float(safe_get(h_stats, "goals", "for", "average", "total", default=1.2) or 1.2)
        except:
            h_avg = 1.2
        try:
            a_avg = float(safe_get(a_stats, "goals", "for", "average", "total", default=1.2) or 1.2)
        except:
            a_avg = 1.2

        # form strings (like "WWDL")
        h_form = "".join(safe_get(h_stats, "form", default="") or "")
        a_form = "".join(safe_get(a_stats, "form", default="") or "")

        # Heuristics:
        # Over 2.5 baseline from combined averages
        over25 = (h_avg + a_avg) * 22
        over25 += min(30, total * 20)
        over25 += min(20, (minute / 90) * 20)
        # BTTS baseline
        btts = (h_avg + a_avg) * 20 + 30
        if gh == 0 and ga == 0 and minute < 20:
            btts -= 10

        # Winner probability heuristic from averages + form
        home_strength = h_avg + (0.5 * h_form.count("W")) - (0.5 * h_form.count("L"))
        away_strength = a_avg + (0.5 * a_form.count("W")) - (0.5 * a_form.count("L"))
        total_strength = (home_strength + away_strength) if (home_strength + away_strength) > 0 else 1
        home_prob = 50 * (home_strength / total_strength)
        away_prob = 50 * (away_strength / total_strength)

        # adjust for current score/time
        if minute > 60:
            if gh > ga:
                home_prob += 8
            elif ga > gh:
                away_prob += 8

        # clamp and compute draw
        over25 = max(0, min(99, over25))
        btts = max(0, min(99, btts))
        home_prob = max(0, min(99, home_prob))
        away_prob = max(0, min(99, away_prob))
        draw_prob = max(0, min(99, 100 - (home_prob + away_prob)))

        # last10 heuristic
        last10 = 5 + ((h_avg + a_avg) * 4) + ((total / 2) if minute > 60 else 0)
        last10 = max(1, min(60, last10))

        # suggested correct scores
        if total == 0:
            suggestions = [f"{home} 1-0 {away}", f"{home} 0-1 {away}"]
        elif total == 1:
            if gh > ga:
                suggestions = [f"{home} 2-0 {away}", f"{home} 2-1 {away}"]
            else:
                suggestions = [f"{home} 1-2 {away}", f"{home} 0-2 {away}"]
        else:
            suggestions = [f"{home} {gh+1}-{ga} {away}", f"{home} {gh}-{ga+1} {away}"]

        return {
            "home": home,
            "away": away,
            "home_prob": roundp(home_prob),
            "draw_prob": roundp(draw_prob),
            "away_prob": roundp(away_prob),
            "over25_prob": roundp(over25),
            "btts_prob": roundp(btts),
            "last10_prob": roundp(last10),
            "suggested_scores": suggestions,
            "minute": minute,
            "home_goals": gh,
            "away_goals": ga,
        }
    except Exception as e:
        print("compute_probabilities_from_fixture error:", e)
        return None

def choose_best_market(probs):
    """
    Return a single market tuple if >=85% found, else None.
    Tuple: (market_text, confidence_int, short_reason, odds_range, risk_note)
    """
    if probs["home_prob"] >= 85:
        return (f"Match Winner: {probs['home']} to Win", probs["home_prob"],
                f"{probs['home']} strong vs {probs['away']}", "1.60-1.95", "Injuries/cards may change outcome")
    if probs["away_prob"] >= 85:
        return (f"Match Winner: {probs['away']} to Win", probs["away_prob"],
                f"{probs['away']} stronger form vs {probs['home']}", "1.60-2.00", "Rotation/fitness risk")
    if probs["btts_prob"] >= 85:
        return ("Both Teams To Score - Yes", probs["btts_prob"],
                "Both teams scoring frequently (high avg goals)", "1.65-1.95", "Red cards / keeper form")
    if probs["over25_prob"] >= 85:
        return ("Over 2.5 Goals", probs["over25_prob"],
                f"High combined scoring / current total {probs['home_goals']+probs['away_goals']}", "1.70-1.95", "Momentum shifts")
    if probs["last10_prob"] >= 85:
        return ("Goal in Last 10 Minutes", probs["last10_prob"],
                "Late goals historically likely", "1.90-2.50", "Very situational")
    return None

def format_output_single(profit):
    market, conf, reason, odds, risk = profit
    return (
        f"🔹 Final 85%+ Confirmed Bet: {market}\n"
        f"💰 Confidence Level: {conf}%\n"
        f"📊 Reasoning: {reason}\n"
        f"🔥 Odds Range: {odds}\n"
        f"⚠️ Risk Note: {risk}"
    )

# -------------------------
# Text-based analyze (user queries)
# -------------------------
def analyze_match_text(text):
    """
    Accepts strings like 'Levante vs Celta Vigo' and returns analysis string.
    """
    t = text.lower().replace("prediction", "").strip()
    if " vs " in t:
        parts = [p.strip() for p in t.split(" vs ")]
    elif " v " in t:
        parts = [p.strip() for p in t.split(" v ")]
    else:
        return "⚠️ Please send like: Levante vs Celta Vigo"

    if len(parts) < 2:
        return "⚠️ Please specify both teams like 'TeamA vs TeamB'."

    home, away = parts[0], parts[1]
    fixture = fetch_fixtures_search(home, away)
    if not fixture:
        return f"⚠️ Match not found for: {home.title()} vs {away.title()}"

    probs = compute_probabilities_from_fixture(fixture)
    if not probs:
        return "⚠️ Unable to compute probabilities right now."

    # Detailed breakdown
    details = []
    details.append(f"Match: {probs['home']} vs {probs['away']} (minute: {probs['minute']}′)")
    details.append(f"1) Match Winner (H/D/A): {probs['home_prob']}% / {probs['draw_prob']}% / {probs['away_prob']}%")
    details.append(f"2) Over/Under → Over 2.5: {probs['over25_prob']}%")
    details.append(f"3) BTTS (Yes): {probs['btts_prob']}%")
    details.append(f"4) Last 10-min goal chance: {probs['last10_prob']}%")
    details.append(f"5) Correct scores: {', '.join(probs['suggested_scores'])}")
    details.append(f"6) High-prob minutes: 20-30′ and 75-85′")

    chosen = choose_best_market(probs)
    if not chosen:
        full = "NO 85%+ BET FOUND\n\n" + "\n".join(details)
        return full

    out = format_output_single(chosen)
    out += "\n\nFull market breakdown:\n" + "\n".join(details[:4])
    return out

# -------------------------
# Telegram handlers
# -------------------------
@bot.message_handler(commands=['start','help'])
def cmd_start(m):
    bot.reply_to(m, f"👋 {BOT_NAME} online. Send 'TeamA vs TeamB' for analysis. I will only return a bet if 85%+ confidence found.")

@bot.message_handler(func=lambda m: True)
def cmd_any(m):
    text = (m.text or "").strip()
    if not text:
        bot.reply_to(m, "⚠️ Send: TeamA vs TeamB")
        return
    if " vs " in text.lower() or " v " in text.lower():
        reply = analyze_match_text(text)
        bot.reply_to(m, reply)
    else:
        bot.reply_to(m, "⚽ Send me like: 'Levante vs Celta Vigo' for a full analysis and (only) 85%+ bets.")

# -------------------------
# Live match analyzer + alert sender
# -------------------------
async def analyze_live_fixture_and_alert(f):
    fi_id = safe_get(f, "fixture", "id", default=None)
    probs = compute_probabilities_from_fixture(f)
    if not probs or not fi_id:
        return
    chosen = choose_best_market(probs)
    if chosen:
        key = (fi_id, chosen[0])
        if key in sent_alerts:
            return
        text = format_output_single(chosen)
        text += f"\n\nMatch live: {probs['home']} {probs['home_goals']}-{probs['away_goals']} {probs['away']} ({probs['minute']}′)"
        try:
            bot.send_message(OWNER_CHAT_ID_INT, text)
            sent_alerts.add(key)
            print("Sent alert for", key)
        except Exception as e:
            print("Error sending live alert:", e)

async def poll_live_loop():
    while True:
        try:
            url = f"{API_BASE}/fixtures?live=all"
            r = requests.get(url, headers=HEADERS, timeout=15)
            data = r.json().get("response", [])
            if not data:
                print(f"[{datetime.utcnow().isoformat()}] No live fixtures")
            else:
                for f in data:
                    await analyze_live_fixture_and_alert(f)
        except Exception as e:
            print("poll_live_loop error:", e)
        await asyncio.sleep(300)

# -------------------------
# Run server + background
# -------------------------
async def main():
    print("🏁 Phase3: Setting webhook and starting background poller...")
    bot.remove_webhook()
    bot.set_webhook(url=f"{DOMAIN}/{BOT_TOKEN}")
    print("✅ Webhook set:", f"{DOMAIN}/{BOT_TOKEN}")

    # Start poller
    asyncio.create_task(poll_live_loop())

    # Serve Flask via hypercorn for async support
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    cfg = Config()
    cfg.bind = ["0.0.0.0:8080"]
    await serve(app, cfg)

if __name__ == "__main__":
    asyncio.run(main())











