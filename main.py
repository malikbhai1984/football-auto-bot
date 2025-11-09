import os
import time
import threading
import requests
from flask import Flask, request, jsonify

# --- CONFIG ---
BOT_TOKEN = "8336882129:AAFZ4oVAY_cEyy_JTi5A0fo12TnTXSEI8as"   # ✅ MyBetAlert_Bot token
OWNER_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"  # ⚠️ Apna chat_id daalo yahan (e.g., 123456789)
API_KEY = "839f1988ceeaafddf8480de33d821556e29d8204b4ebdca13cb69c7a9bdcd325"
API_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

app = Flask(__name__)
live_thread_running = False


# --- Function: Get Live Matches from API ---
def fetch_live_matches():
    try:
        print("🔄 Fetching LIVE matches from API...")
        url = f"{API_URL}/fixtures?live=all"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            print(f"⚠️ API error: {r.status_code}")
            return []
        data = r.json().get("response", [])
        return data
    except Exception as e:
        print(f"❌ Error fetching live data: {e}")
        return []


# --- Function: Send Telegram Message ---
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": OWNER_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"⚠️ Telegram send failed: {e}")


# --- Thread for Auto Updates ---
def auto_update_thread():
    global live_thread_running
    while live_thread_running:
        matches = fetch_live_matches()
        if matches:
            msg = "🟢 *Live Football Updates:*\n\n"
            for m in matches:
                home = m["teams"]["home"]["name"]
                away = m["teams"]["away"]["name"]
                hgoals = m["goals"]["home"]
                agoals = m["goals"]["away"]
                minute = m["fixture"]["status"]["elapsed"]
                msg += f"{home} {hgoals}-{agoals} {away} ({minute}’)\n"
            send_telegram_message(msg)
        else:
            send_telegram_message("⏳ No live matches right now.")
        time.sleep(420)  # every 7 minutes


# --- Flask Routes ---
@app.route('/')
def home():
    return jsonify({"status": "MyBetAlert_Bot is active!"})


@app.route('/start', methods=['GET'])
def start_updates():
    global live_thread_running
    if live_thread_running:
        return "Already running!"
    live_thread_running = True
    threading.Thread(target=auto_update_thread, daemon=True).start()
    return "✅ Auto live updates started (every 7 min)"


@app.route('/stop', methods=['GET'])
def stop_updates():
    global live_thread_running
    live_thread_running = False
    return "🛑 Auto updates stopped."


@app.route('/live', methods=['GET'])
def manual_live():
    matches = fetch_live_matches()
    if not matches:
        return "⏳ No live matches right now."
    msg = "🔥 *Current Live Matches:*\n\n"
    for m in matches:
        home = m["teams"]["home"]["name"]
        away = m["teams"]["away"]["name"]
        hgoals = m["goals"]["home"]
        agoals = m["goals"]["away"]
        minute = m["fixture"]["status"]["elapsed"]
        msg += f"{home} {hgoals}-{agoals} {away} ({minute}’)\n"
    send_telegram_message(msg)
    return msg


if __name__ == "__main__":
    print("🚀 MyBetAlert Football Bot Running...")
    app.run(host="0.0.0.0", port=8000)
