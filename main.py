import os
import requests
import threading
import time
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- Configuration ---
BOT_TOKEN = "8336882129:AAFZ4oVAY_cEyy_JTi5A0fo12TnTXSEI8as"          # ⚠️ apna Telegram Bot Token yahan daalna
OWNER_CHAT_ID = "MyBetAlert_Bot" # ⚠️ optional: apna chat_id

API_KEY = "839f1988ceeaafddf8480de33d821556e29d8204b4ebdca13cb69c7a9bdcd325"
API_URL = "https://v3.football.api-sports.io"
HEADERS = {
    "x-apisports-key": API_KEY
}

app = Flask(__name__)
live_thread_running = False


# --- Function to Fetch Live Matches ---
def fetch_live_matches():
    """Fetch actual live matches from API-Football"""
    try:
        print("🔄 Fetching LIVE matches from API...")
        url = f"{API_URL}/fixtures?live=all"
        response = requests.get(url, headers=HEADERS, timeout=10)
        
        if response.status_code != 200:
            print(f"⚠️ API Error: {response.status_code} - {response.text}")
            return []
        
        data = response.json()
        matches = data.get("response", [])
        
        if not matches:
            print("⏳ No live matches found right now.")
            return []
        
        print(f"✅ Found {len(matches)} live matches!")
        for m in matches:
            home = m["teams"]["home"]["name"]
            away = m["teams"]["away"]["name"]
            status = m["fixture"]["status"]["short"]
            print(f"   🏆 {home} vs {away} | Status: {status}")
        
        return matches

    except Exception as e:
        print(f"❌ Error fetching live matches: {e}")
        return []


# --- Telegram Bot Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚽ Football Live Bot Activated!\n\nUse /live to see all live matches now.")


async def live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current live matches"""
    matches = fetch_live_matches()
    
    if not matches:
        await update.message.reply_text("⏳ No live matches at the moment.")
        return
    
    reply_text = "🔥 *Current Live Matches:*\n\n"
    for match in matches:
        home = match["teams"]["home"]["name"]
        away = match["teams"]["away"]["name"]
        status = match["fixture"]["status"]["short"]
        goals_home = match["goals"]["home"]
        goals_away = match["goals"]["away"]
        time_now = match["fixture"]["status"]["elapsed"]
        reply_text += f"🏆 {home} {goals_home} - {goals_away} {away}\n⏱️ {status} ({time_now}’)\n\n"
    
    await update.message.reply_text(reply_text, parse_mode="Markdown")


async def predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Predict simple live outcome based on score"""
    matches = fetch_live_matches()
    
    if not matches:
        await update.message.reply_text("⏳ No live matches currently running.")
        return
    
    reply_text = "📊 *Live Match Predictions:*\n\n"
    for match in matches:
        home = match["teams"]["home"]["name"]
        away = match["teams"]["away"]["name"]
        home_goals = match["goals"]["home"]
        away_goals = match["goals"]["away"]
        
        if home_goals > away_goals:
            pred = f"✅ {home} likely to WIN"
        elif away_goals > home_goals:
            pred = f"✅ {away} likely to WIN"
        else:
            pred = "⚖️ Match could end DRAW"
        
        reply_text += f"{home} vs {away}\nPrediction: {pred}\n\n"
    
    await update.message.reply_text(reply_text, parse_mode="Markdown")


# --- Auto Thread to Send Live Updates Every 7 Min ---
def auto_update_thread(application):
    global live_thread_running
    while live_thread_running:
        print("🔁 Auto-checking live matches...")
        matches = fetch_live_matches()
        if matches:
            text = "🕐 *Auto Live Update:*\n\n"
            for m in matches:
                home = m["teams"]["home"]["name"]
                away = m["teams"]["away"]["name"]
                score = f"{m['goals']['home']} - {m['goals']['away']}"
                minute = m["fixture"]["status"]["elapsed"]
                text += f"{home} {score} {away} ({minute}’)\n"
            application.bot.send_message(chat_id=OWNER_CHAT_ID, text=text, parse_mode="Markdown")
        time.sleep(420)  # every 7 minutes


async def autolive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global live_thread_running
    if live_thread_running:
        await update.message.reply_text("🔁 Auto-update already running.")
    else:
        live_thread_running = True
        threading.Thread(target=auto_update_thread, args=(context.application,), daemon=True).start()
        await update.message.reply_text("✅ Auto Live Updates started! (every 7 minutes)")


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global live_thread_running
    live_thread_running = False
    await update.message.reply_text("🛑 Auto Live Updates stopped.")


# --- Run Flask and Bot Together ---
def start_bot():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("live", live))
    application.add_handler(CommandHandler("predict", predict))
    application.add_handler(CommandHandler("autolive", autolive))
    application.add_handler(CommandHandler("stop", stop))
    
    print("🤖 Telegram Bot Running...")
    application.run_polling()


if __name__ == "__main__":
    threading.Thread(target=start_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=8000)
