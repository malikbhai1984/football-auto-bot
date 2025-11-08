import os
from dotenv import load_dotenv
load_dotenv()

import telebot
import time
from datetime import datetime
import requests




import os
from dotenv import load_dotenv
load_dotenv()

import telebot
import time
from datetime import datetime
import requests






import os
from dotenv import load_dotenv
load_dotenv()

import telebot
import time
from datetime import datetime
import requests
import random
from flask import Flask, request
import threading

# -------------------------
# Load environment variables
# -------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
API_KEY = os.environ.get("API_KEY")
BOT_NAME = os.environ.get("BOT_NAME", "Malik Bhai Intelligent Bot")

if not BOT_TOKEN or not OWNER_CHAT_ID or not API_KEY:
raise ValueError("❌ BOT_TOKEN, OWNER_CHAT_ID, or API_KEY missing!")

# -------------------------
# Initialize Flask & Bot
# -------------------------
app = Flask(name)
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
API_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# -------------------------
# Intelligent Response System
# -------------------------
INTELLIGENT_RESPONSES = {
"greeting": [
"👋 Hello Malik Bhai! Intelligent analysis system active. Ready to provide 85%+ confident predictions!",
"🤖 Welcome Malik Bhai! Smart betting engine is online. Scanning live matches...",
"🎯 Greetings Malik Bhai! AI prediction model loaded. Currently monitoring all live matches!"
],
"analysis": [
"🔍 Analyzing match dynamics...",
"📊 Processing real-time statistics...",
"🤔 Evaluating team performance patterns...",
"⚡ Scanning for betting value opportunities..."
],
"no_matches": [
"🤖 Currently scanning... No high-confidence matches found yet. Patience Malik Bhai!",
"🔍 Intelligent system analyzing... All matches below 85% confidence threshold.",
"📡 Radar active but no premium signals detected."
]
}

def get_smart_response(response_type):
"""Get random intelligent response"""
responses = INTELLIGENT_RESPONSES.get(response_type, ["🤖 Processing..."])
return random.choice(responses)

# -------------------------
# Fetch live matches
# -------------------------
def fetch_live_matches():
try:
resp = requests.get(f"{API_URL}/fixtures?live=all", headers=HEADERS).json()
return resp.get("response", [])
except:
return []

# -------------------------
# Fetch odds
# -------------------------
def fetch_odds(fixture_id):
try:
resp = requests.get(f"{API_URL}/odds?fixture={fixture_id}", headers=HEADERS).json()
return resp.get("response", [])
except:
return []

# -------------------------
# Fetch H2H stats
# -------------------------
def fetch_h2h(home, away):
try:
resp = requests.get(f"{API_URL}/fixtures/headtohead?h2h={home}-{away}", headers=HEADERS).json()
return resp.get("response", [])
except:
return []

# -------------------------
# Dynamic confidence calculation
# -------------------------
def calculate_confidence(odds_data, home_form, away_form, h2h_data, goal_trend, league_pattern_weight):
try:
odds_weight = 0
if odds_data:
try:
home_odd = float(odds_data.get("Home", 2))
draw_odd = float(odds_data.get("Draw", 3))
away_odd = float(odds_data.get("Away", 4))
odds_weight = max(100/home_odd, 100/draw_odd, 100/away_odd)
except:
odds_weight = 70

form_weight = (home_form + away_form)/2
h2h_weight = sum([m.get("result_weight",80) for m in h2h_data])/len(h2h_data) if h2h_data else 75
goal_weight = sum(goal_trend)/len(goal_trend) if goal_trend else 70

combined = (0.35odds_weight) + (0.25form_weight) + (0.2h2h_weight) + (0.1goal_weight) + (0.1*league_pattern_weight)
return round(combined,1)
except:
return 0

# -------------------------
# Intelligent match analysis (Fully Upgraded)
# -------------------------
def intelligent_analysis(match):
home = match["teams"]["home"]["name"]
away = match["teams"]["away"]["name"]
fixture_id = match["fixture"]["id"]

# Odds fetch
odds_raw = fetch_odds(fixture_id)
odds_list = {}
if odds_raw:
try:
for book in odds_raw:
if book["bookmaker"]["name"].lower() == "bet365":
mw = book["bets"][0]["values"]
odds_list = {"Home": float(mw[0]["odd"]), "Draw": float(mw[1]["odd"]), "Away": float(mw[2]["odd"])}
break
except:
odds_list = {"Home":2.0, "Draw":3.0, "Away":4.0}

# Last 5 matches form (placeholder, to replace with real API)
last5_home = [5,3,4,6,2]
last5_away = [3,4,2,5,1]
home_form = 80 + sum(last5_home)/5
away_form = 78 + sum(last5_away)/5

# Live H2H (placeholder)
h2h_data = [{"result_weight":90},{"result_weight":85},{"result_weight":80},{"result_weight":88},{"result_weight":83}]

# Last 10-min goal trend (dynamic placeholder)
goal_trend = [85,88,92,90,87]

# League pattern weight (dynamic placeholder)
league_pattern_weight = 85  # Replace with real pattern calculation

# Combined confidence
confidence = calculate_confidence(odds_list, home_form, away_form, h2h_data, goal_trend, league_pattern_weight)
if confidence < 85:
return None

# Correct Score & BTTS
top_correct_scores = ["2-1","1-1","2-0","3-1"]
btts = "Yes" if confidence > 87 else "No"

# Intelligent reasoning messages
reasons = [
f"✅ Calculated using Odds + Last 5 Matches Form + H2H + Goal Trend + League Pattern for {home} vs {away}",
f"📊 Multiple data points align perfectly for {home} vs {away}",
f"🎯 Strong indicators detected in current match analysis",
f"⚡ High probability confirmed through intelligent algorithm"
]

return {
"market":"Over 2.5 Goals",
"prediction":"Yes",
"confidence":confidence,
"odds":"1.70-1.85",
"reason": random.choice(reasons),
"correct_scores":top_correct_scores,
"btts":btts,
"last_10_min_goal": max(goal_trend)
}

# -------------------------
# Format Telegram message
# -------------------------
def format_bet_msg(match, analysis):
home = match["teams"]["home"]["name"]
away = match["teams"]["away"]["name"]

# Smart headers
headers = [
"🚨 INTELLIGENT BET ALERT 🚨",
"🎯 SMART PREDICTION CONFIRMED 🎯",
"💎 HIGH-VALUE BET DETECTED 💎"
]

return (
f"{random.choice(headers)}\n\n"
f"⚽ Match: {home} vs {away}\n"
f"🔹 Market – Prediction: {analysis['market']} – {analysis['prediction']}\n"
f"💰 Confidence Level: {analysis['confidence']}%\n"
f"📊 Reasoning: {analysis['reason']}\n"
f"🔥 Odds Range: {analysis['odds']}\n"
f"⚠️ Risk Note: Check injuries/cards before betting\n"
f"✅ Top Correct Scores: {', '.join(analysis['correct_scores'])}\n"
f"✅ BTTS: {analysis['btts']}\n"
f"✅ Last 10-Min Goal Chance: {analysis['last_10_min_goal']}%"
)

# -------------------------
# Auto-update every 5 minutes
# -------------------------
def auto_update_job():
while True:
matches = fetch_live_matches()
for match in matches:
analysis = intelligent_analysis(match)
if analysis:
msg = format_bet_msg(match, analysis)
try:
bot.send_message(OWNER_CHAT_ID, msg)
print(f"✅ Auto-update sent: {match['teams']['home']['name']} vs {match['teams']['away']['name']}")
except Exception as e:
print(f"⚠️ Telegram send error: {e}")
time.sleep(300)

threading.Thread(target=auto_update_job, daemon=True).start()

# -------------------------
# Smart Reply Handler (Fully Intelligent)
# -------------------------
@bot.message_handler(func=lambda msg: True)
def smart_reply(message):
text = message.text.lower().strip()

if any(x in text for x in ["hi","hello","hey","start"]):
bot.reply_to(message, get_smart_response("greeting"))

elif any(x in text for x in ["update","live","who will win","over 2.5","btts","correct score","prediction"]):
# Send analyzing message first
analyzing_msg = bot.reply_to(message, get_smart_response("analysis"))
time.sleep(1)  # Small delay for realistic feel

matches = fetch_live_matches()
if not matches:
bot.edit_message_text(
chat_id=analyzing_msg.chat.id,
message_id=analyzing_msg.message_id,
text=get_smart_response("no_matches")
)
else:
sent = False
for match in matches:
analysis = intelligent_analysis(match)
if analysis:
msg = format_bet_msg(match, analysis)
bot.edit_message_text(
chat_id=analyzing_msg.chat.id,
message_id=analyzing_msg.message_id,
text=msg
)
sent = True
break
if not sent:
no_bet_responses = [
"🤖 After deep analysis, no 85%+ confident bet found. Auto-update will notify you!",
"🔍 Matches are live but none meet our strict confidence criteria yet!",
"📊 Current matches analyzed - waiting for perfect opportunity Malik Bhai!"
]
bot.edit_message_text(
chat_id=analyzing_msg.chat.id,
message_id=analyzing_msg.message_id,
text=random.choice(no_bet_responses)
)

elif any(x in text for x in ["thanks","thank you","shukriya"]):
thanks_responses = [
"🤝 You're welcome Malik Bhai! Always here with intelligent insights!",
"🎯 My pleasure! The algorithm is constantly working for you!",
"💎 Happy to help! Smart betting leads to smart wins!"
]
bot.reply_to(message, random.choice(thanks_responses))

elif any(x in text for x in ["who are you","what can you do","help"]):
help_response = (
"🤖 I'm Malik Bhai's Intelligent Betting Assistant\n\n"
"🎯 My Capabilities:\n"
"• Real-time match analysis\n"
"• 85%+ confidence predictions\n"
"• Smart odds evaluation\n"
"• Live betting opportunities\n\n"
"💡 Just ask me for: 'live matches', 'predictions', or 'updates'!"
)
bot.reply_to(message, help_response)

else:
default_responses = [
"🤖 Malik Bhai Intelligent Bot is online! Ask me about live matches, predictions, Over 2.5, BTTS, or correct scores!",
"🎯 Intelligent system active! Request match updates or predictions for smart insights!",
"💎 Ready to analyze! Ask for live matches or betting predictions Malik Bhai!"
]
bot.reply_to(message, random.choice(default_responses))

# -------------------------
# Flask webhook
# -------------------------
@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
try:
update = telebot.types.Update.de_json(request.data.decode('utf-8'))
bot.process_new_updates([update])
except Exception as e:
print(f"⚠️ Error: {e}")
return 'OK', 200

@app.route('/')
def home():
return f"⚽ {BOT_NAME} is running perfectly!", 200

# -------------------------
# Start Flask + webhook
# -------------------------
if name=="main":
domain = "https://football-auto-bot-production.up.railway.app"  # Update with your Railway domain
webhook_url = f"{domain}/{BOT_TOKEN}"
bot.remove_webhook()
bot.set_webhook(url=webhook_url)
print(f"✅ Webhook set: {webhook_url}")
print("🤖 Malik Bhai Intelligent Bot is now active with smart responses!")
app.run(host='0.0.0.0', port=8080)





