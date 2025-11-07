import os
from dotenv import load_dotenv
load_dotenv()

import telebot
import time
from datetime import datetime
import requests







# -------------------------
# Analyze ANY team - live or upcoming matches
# -------------------------
def analyze_any_team(team_name):
    """
    Search for live or upcoming matches for any team and return analysis
    """
    try:
        # Search fixtures by team name
        url = f"{API_BASE}/fixtures?search={requests.utils.quote(team_name)}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json().get("response", [])
        
        if not data:
            return f"⚠️ No matches found for: {team_name.title()}"
        
        # Prioritize live matches first, then upcoming
        live_matches = []
        upcoming_matches = []
        
        for fixture in data:
            status = safe_get(fixture, "fixture", "status", "short", default="NS")
            if status == "LIVE":
                live_matches.append(fixture)
            elif status in ["NS", "1H", "2H", "HT"]:  # Not started or upcoming
                upcoming_matches.append(fixture)
        
        # Choose the most relevant match
        target_fixture = None
        if live_matches:
            target_fixture = live_matches[0]  # Take first live match
            match_type = "LIVE"
        elif upcoming_matches:
            target_fixture = upcoming_matches[0]  # Take next upcoming match
            match_type = "UPCOMING"
        else:
            return f"⚠️ No active matches for: {team_name.title()}"
        
        # Get analysis
        probs = compute_probabilities_from_fixture(target_fixture)
        if not probs:
            return "⚠️ Unable to analyze this match right now."
        
        # Prepare analysis
        home = probs['home']
        away = probs['away']
        minute = probs['minute']
        score = f"{probs['home_goals']}-{probs['away_goals']}"
        
        analysis = []
        analysis.append(f"🔍 **Match Found ({match_type}):**")
        analysis.append(f"**{home}** vs **{away}**")
        
        if match_type == "LIVE":
            analysis.append(f"🕒 **{minute}′** | 📊 **Score: {score}**")
        else:
            analysis.append(f"⏰ **Upcoming Match**")
        
        analysis.append("")
        analysis.append("📈 **Market Probabilities:**")
        analysis.append(f"• Home Win: {probs['home_prob']}%")
        analysis.append(f"• Draw: {probs['draw_prob']}%") 
        analysis.append(f"• Away Win: {probs['away_prob']}%")
        analysis.append(f"• Over 2.5 Goals: {probs['over25_prob']}%")
        analysis.append(f"• BTTS: {probs['btts_prob']}%")
        analysis.append(f"• Last 10-min Goal: {probs['last10_prob']}%")
        
        # Check for 85%+ bets
        chosen = choose_best_market(probs)
        if chosen:
            analysis.append("")
            analysis.append("🎯 **85%+ CONFIDENCE BET:**")
            analysis.append(format_output_single(chosen))
        else:
            analysis.append("")
            analysis.append("ℹ️ No 85%+ confidence bets found for this match.")
        
        return "\n".join(analysis)
        
    except Exception as e:
        print(f"analyze_any_team error: {e}")
        return "⚠️ Error analyzing team. Please try again."

# -------------------------
# Updated Telegram handler
# -------------------------
@bot.message_handler(func=lambda m: True)
def cmd_any(m):
    text = (m.text or "").strip()
    if not text:
        bot.reply_to(m, "⚽ Send me a team name (e.g.: 'Real Madrid') or 'TeamA vs TeamB'")
        return
    
    # If it's a vs format, use existing analysis
    if " vs " in text.lower() or " v " in text.lower():
        reply = analyze_match_text(text)
        bot.reply_to(m, reply)
    else:
        # Single team name - search for their matches
        bot.reply_to(m, f"🔍 Searching for {text}...")
        reply = analyze_any_team(text)
        bot.reply_to(m, reply)









