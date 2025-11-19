# main.py
import time
import telebot
from datetime import datetime

BOT_TOKEN = "8336882129:AAFZ4oVAY_cEyy_JTi5A0fo12TnTXSEI8as"
OWNER_CHAT_ID = 7742985526

bot = telebot.TeleBot(BOT_TOKEN)

def get_live_matches():
    now = datetime.now().strftime('%H:%M:%S')
    return [{"match_hometeam_name":"Team A","match_awayteam_name":"Team B",
             "match_hometeam_score":"1","match_awayteam_score":"0","time":now}]

def generate_prediction(match):
    return f"🤖 LIVE PREDICTION\n{match['match_hometeam_name']} vs {match['match_awayteam_name']}\nScore: {match['match_hometeam_score']}-{match['match_awayteam_score']}"

def auto_update():
    while True:
        matches = get_live_matches()
        if matches:
            for match in matches:
                try:
                    bot.send_message(OWNER_CHAT_ID, generate_prediction(match))
                    print(f"Message sent at {datetime.now()}")
                    time.sleep(2)
                except Exception as e:
                    print(f"❌ Send message error: {e}")
        time.sleep(300)

if __name__ == "__main__":
    print("✅ Bot started!")
    auto_update()
