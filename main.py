import time
import telebot
from datetime import datetime

# -------------------------
# Telegram credentials
# -------------------------
BOT_TOKEN = "8336882129:AAFZ4oVAY_cEyy_JTi5A0fo12TnTXSEI8as"
OWNER_CHAT_ID = 7742985526  # integer

bot = telebot.TeleBot(BOT_TOKEN)

# -------------------------
# Dummy live match data
# -------------------------
def get_live_matches():
    # Replace with API fetch if you want real matches later
    now = datetime.now().strftime('%H:%M:%S')
    return [{
        "match_hometeam_name": "Team A",
        "match_awayteam_name": "Team B",
        "match_hometeam_score": "1",
        "match_awayteam_score": "0",
        "time": now
    }]

# -------------------------
# Generate prediction message
# -------------------------
def generate_prediction(match):
    msg = f"🤖 LIVE PREDICTION\n"
    msg += f"{match['match_hometeam_name']} vs {match['match_awayteam_name']}\n"
    msg += f"Score: {match['match_hometeam_score']}-{match['match_awayteam_score']}\n"
    msg += f"Home Win: 70% | Draw: 15% | Away Win: 15%\n"
    msg += "BTTS: Yes\n"
    msg += "Last 10-min Goal Chance: 75%\n"
    msg += "Correct Scores: 1-0, 2-0\n"
    msg += "High-probability Goal Minutes: 23, 45, 60, 78, 85\n"
    return msg

# -------------------------
# Auto-update every 5 min
# -------------------------
def auto_update():
    while True:
        matches = get_live_matches()
        if matches:
            for match in matches:
                msg = generate_prediction(match)
                try:
                    bot.send_message(OWNER_CHAT_ID, msg)
                    print(f"Message sent at {datetime.now()}")
                    time.sleep(2)
                except Exception as e:
                    print(f"❌ Send message error: {e}")
        else:
            print("⏳ No live matches currently.")
        time.sleep(300)  # 5 minutes

# -------------------------
# Start bot
# -------------------------
if __name__ == "__main__":
    print("✅ Bot started, sending messages every 5 min...")
    auto_update()  # directly run auto-update
