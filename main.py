import os
from dotenv import load_dotenv
load_dotenv()

import telebot
import time
from datetime import datetime
import requests







import os
import math
import time
import asyncio
import requests
import telebot
import threading
from flask import Flask, request
from datetime import datetime, timedelta

# -------------------------
# Load env
# -------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
API_KEY = os.environ.get("API_KEY")
DOMAIN = os.environ.get("DOMAIN", "https://football-auto-bot-production.up.railway.app")
BOT_NAME = os.environ.get("BOT_NAME", "Football Smart Bot")

if not BOT_TOKEN or not OWNER_CHAT_ID or not API_KEY:
    raise ValueError("❌ BOT_TOKEN, OWNER_CHAT_ID and API_KEY must be set in environment variables!")

OWNER_CHAT_ID_INT = int(OWNER_CHAT_ID) if str(OWNER_CHAT_ID).isdigit() else OWNER_CHAT_ID

API_BASE = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# -------------------------
# ✅ PEHLE FLASK APP DEFINE KARO
# -------------------------
app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)

# -------------------------
# ✅ AB WEBHOOK ROUTES DEFINE KARO
# -------------------------
@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'OK', 200

@app.route('/')
def home():
    return f"⚽ {BOT_NAME} is running!", 200

# Keep set of alerts sent to avoid duplicates: (fixture_id, market_key)
sent_alerts = set()

# -------------------------
# Utility helpers
# -------------------------
def safe_get(d, *keys, default=None):
    v = d
    try:
        for k in keys:
            v = v.get(k, {})
        if v == {}: return default
        return v
    except Exception:
        return default

def roundp(x): return int(round(x))

# -------------------------
# Analysis functions
# -------------------------
def fetch_fixtures_search(home, away):
    """
    Search fixtures by home and try to match away.
    Returns first matching fixture dict or None.
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
        # fallback: try searching by away
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
    Returns stats dict via /teams/statistics if available.
    """
    try:
        url = f"{API_BASE}/teams/statistics?team={team_id}"
        if league_id:
            url += f"&league={league_id}"
        if season:
            url += f"&season={season}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        return r.json().get("response", {})
    except Exception as e:
        print("fetch_team_stats error:", e)
        return {}

def compute_probabilities_from_fixture(f):
    """
    Given an API fixture object (live or upcoming), compute market probabilities.
    Returns dict with market probabilities (0-100).
    Heuristics based on: current score, minute, teams' scoring averages, form strings.
    """
    try:
        home = safe_get(f, "teams", "home", "name", default="Home")
        away = safe_get(f, "teams", "away", "name", default="Away")
        home_id = safe_get(f, "teams", "home", "id", default=None)
        away_id = safe_get(f, "teams", "away", "id", default=None)
        league = safe_get(f, "league", "id", default=None)
        season = safe_get(f, "league", "season", default=None)

        # current score & time
        gh = safe_get(f, "goals", "home", default=0) or 0
        ga = safe_get(f, "goals", "away", default=0) or 0
        total = gh + ga
        minute = safe_get(f, "fixture", "status", "elapsed", default=0) or 0
        status = safe_get(f, "fixture", "status", "short", default="NS")

        # team stats (fallback values)
        h_stats = fetch_team_stats(home_id, league_id=league, season=season) if home_id else {}
        a_stats = fetch_team_stats(away_id, league_id=league, season=season) if away_id else {}

        # averages
        try:
            h_avg = float(safe_get(h_stats, "goals", "for", "average", "total", default=1.2) or 1.2)
        except:
            h_avg = 1.2
        try:
            a_avg = float(safe_get(a_stats, "goals", "for", "average", "total", default=1.2) or 1.2)
        except:
            a_avg = 1.2

        # form strings (like "WWDL")
        h_form = "".join(safe_get(h_stats, "form", default=""))
        a_form = "".join(safe_get(a_stats, "form", default=""))

        # base heuristics
        # Over 2.5: rises with combined avg and current total and elapsed
        over25 = (h_avg + a_avg) * 22  # base weight
        over25 += min(30, total * 20)
        over25 += min(20, (minute / 90) * 20)
        # BTTS: depends on both teams' scoring and conceding averages
        btts = (h_avg + a_avg) * 20 + 30
        if gh == 0 and ga == 0 and minute < 20:
            btts -= 10
        # Winner probabilities: naive Elo-ish heuristic
        home_strength = h_avg + (0.5 * h_form.count("W")) - (0.5 * h_form.count("L"))
        away_strength = a_avg + (0.5 * a_form.count("W")) - (0.5 * a_form.count("L"))
        total_strength = home_strength + away_strength if (home_strength + away_strength) > 0 else 1
        home_prob = 50 * (home_strength / total_strength)
        away_prob = 50 * (away_strength / total_strength)
        # small adjustments for current score & minute
        if minute > 60:
            # trailing team more likely to push and concede late
            if gh > ga:
                home_prob += 8
            elif ga > gh:
                away_prob += 8

        # clamp 0-100
        over25 = max(0, min(99, over25))
        btts = max(0, min(99, btts))
        home_prob = max(0, min(99, home_prob))
        away_prob = max(0, min(99, away_prob))
        draw_prob = max(0, min(99, 100 - (home_prob + away_prob)))

        # last-10-min chance heuristic
        last10 = 5 + ( (h_avg + a_avg) * 4 ) + ( (total / 2) if minute>60 else 0 )
        last10 = max(1, min(60, last10))

        # suggested correct scores: basic heuristics using current score
        suggestions = []
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
    From computed probabilities choose a single market if >=85% confidence.
    Return tuple (market_string, confidence, short_reason, odds_range, risk_note)
    """
    # check in priority order: outright win, BTTS, Over2.5, last10 (but must be >=85)
    if probs["home_prob"] >= 85:
        return (f"Match Winner: {probs['home']} to Win", probs["home_prob"],
                f"{probs['home']} strong vs {probs['away']}", "1.60-1.95", "Late cards/injuries")
    if probs["away_prob"] >= 85:
        return (f"Match Winner: {probs['away']} to Win", probs["away_prob"],
                f"{probs['away']} stronger form vs {probs['home']}", "1.60-2.00", "Pitch/rotation risks")
    if probs["btts_prob"] >= 85:
        return (f"Both Teams To Score - Yes", probs["btts_prob"],
                f"Both teams scoring frequently (avg goals high)", "1.65-1.95", "Red cards / keeper form")
    if probs["over25_prob"] >= 85:
        return (f"Over 2.5 Goals", probs["over25_prob"],
                f"High combined goals per match ({(probs['home_goals']+probs['away_goals'])} current + high xG)", "1.70-1.95", "Momentum can stop")
    if probs["last10_prob"] >= 85:
        return (f"Goal in Last 10 Minutes", probs["last10_prob"],
                f"Late goals historically likely", "1.90-2.50", "Very situational")
    return None  # no >=85

# -------------------------
# Format output as required
# -------------------------
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
# Analyze match by text (home vs away)
# -------------------------
def analyze_match_text(text):
    # expect "TeamA vs TeamB" somewhere in text
    t = text.lower().replace("prediction", "").strip()
    if " vs " in t:
        parts = [p.strip() for p in t.split(" vs ")]
    elif "v " in t:
        parts = [p.strip() for p in t.split(" v ")]
    else:
        return "⚠️ Please send like: Levante vs Celta Vigo"

    if len(parts) < 2:
        return "⚠️ Please specify both teams like 'TeamA vs TeamB'."

    home, away = parts[0], parts[1]
    # attempt to find fixture
    fixture = fetch_fixtures_search(home, away)
    if not fixture:
        return f"⚠️ Match not found for: {home.title()} vs {away.title()}"

    probs = compute_probabilities_from_fixture(fixture)
    if not probs:
        return "⚠️ Unable to compute probabilities right now."

    # Prepare required detailed analysis (all markets)
    details = []
    details.append(f"Match: {probs['home']} vs {probs['away']} (minute: {probs['minute']}′)")
    details.append(f"1) Match Winner (H/D/A): {probs['home_prob']}% / {probs['draw_prob']}% / {probs['away_prob']}%")
    details.append(f"2) Over/Under probabilities → Over2.5: {probs['over25_prob']}%")
    details.append(f"3) BTTS (Yes): {probs['btts_prob']}%")
    details.append(f"4) Last 10-min goal chance: {probs['last10_prob']}%")
    details.append(f"5) Correct scores: {', '.join(probs['suggested_scores'])}")
    details.append(f"6) High-prob minutes: 20-30′ and 75-85′")

    # Now choose the ONE 85%+ market
    chosen = choose_best_market(probs)
    if not chosen:
        # If strict rule: return NO 85%+ BET FOUND plus detailed analysis (as user wanted)
        full = "NO 85%+ BET FOUND\n\n" + "\n".join(details)
        return full

    # else format chosen market into required output (with 2-3 line reasoning)
    out = format_output_single(chosen)
    # add short 2-line economics
    out += "\n\n" + "Full market breakdown:\n" + "\n".join(details[:4])
    return out

# -------------------------
# Telegram handlers
# -------------------------
@bot.message_handler(commands=['start','help'])
def cmd_start(m):
    bot.reply_to(m, f"👋 {BOT_NAME} online. Send me 'TeamA vs TeamB' to get analysis (I will only return a bet if 85%+ confidence).")

@bot.message_handler(func=lambda m: True)
def cmd_any(m):
    text = (m.text or "").strip()
    # quick keywords
    if not text:
        bot.reply_to(m, "⚠️ Send: TeamA vs TeamB")
        return

    # if user asks for "who will win" or has 'vs' call analyze
    if " vs " in text.lower() or " v " in text.lower():
        reply = analyze_match_text(text)
        bot.reply_to(m, reply)
    else:
        bot.reply_to(m, "⚽ Send me like: 'Levante vs Celta Vigo' for a full analysis and (only) 85%+ bets.")

# -------------------------
# Background live poller
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
        # send alert
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
        await asyncio.sleep(300)  # 5 minutes

def start_poller():
    """Start background poller in a separate thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(poll_live_loop())

# -------------------------
# Run app + background tasks
# -------------------------
if __name__ == "__main__":
    print("🏁 Setting webhook and starting background poller...")
    
    # Webhook setup
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"{DOMAIN}/{BOT_TOKEN}")
    print(f"✅ Webhook set: {DOMAIN}/{BOT_TOKEN}")

    # Start background poller in separate thread
    poller_thread = threading.Thread(target=start_poller, daemon=True)
    poller_thread.start()
    print("✅ Background poller started")

    # Run Flask app
    print("✅ Starting Flask server...")
    app.run(host="0.0.0.0", port=8080, debug=False)









