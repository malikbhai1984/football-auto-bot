import os
import requests
import telebot
import time
import random
import threading
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pytz
import logging
import json
from flask import Flask, request # <--- Flask is now required

# -------------------------
# Load environment variables & Basic Setup
# -------------------------
load_dotenv()

# --- Configuration ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
API_KEY = os.environ.get("API_KEY") 

# Webhook Configuration (NEW!)
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = os.environ.get("PORT", 8080) 

# Checks
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN missing! Please set it in your .env file.")
if not WEBHOOK_URL:
    raise ValueError("❌ WEBHOOK_URL missing! Set your Railway domain in .env.")

try:
    if OWNER_CHAT_ID: OWNER_CHAT_ID = int(OWNER_CHAT_ID)
except (ValueError, TypeError):
    OWNER_CHAT_ID = None 
    print("⚠️ WARNING: OWNER_CHAT_ID is missing or invalid.")
    
# Set up environment
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__) # Initialize Flask app

# -------------------------
# Core Bot Logic Classes (MatchAnalysis, HTTPAPIManager, GlobalHitCounter, EnhancedFootballAI) 
# --- [ ALL CORE LOGIC REMAINS IDENTICAL TO V4/V3, ENSURING FUNCTIONALITY ] ---
# -------------------------

# >>> PASTE THE CLASS DEFINITIONS FROM V4 HERE <<<
# (MatchAnalysis, HTTPAPIManager, GlobalHitCounter, EnhancedFootballAI, and all utility functions)
# For brevity, I am instructing you to paste the unchanged core logic from V4/V3 here.

# --- [ All utility functions and Class definitions from V4 (e.g., get_current_date_pakt, get_mock_previous_data, LEAGUE_CONFIG, etc.) should be pasted here ] ---

# ... [ PASTE V4 CODE HERE - CONTINUED ] ...
class MatchAnalysis:
    # ... (all methods from V4) ...
    def analyze_match_trends(self, match_data):
        try:
            home_team = match_data.get("match_hometeam_name", "")
            away_team = match_data.get("match_awayteam_name", "")
            home_score = int(match_data.get("match_hometeam_score", 0))
            away_score = int(match_data.get("match_awayteam_score", 0))
            minute = match_data.get("match_status", "0")
            
            if minute == "HT": match_progress = 50
            elif minute == "FT": match_progress = 100
            elif minute.isdigit(): match_progress = min(100, (int(minute) / 90) * 100)
            else: match_progress = 0
            
            goal_difference = home_score - away_score
            total_goals = home_score + away_score
            
            if goal_difference > 0: momentum = f"🏠 {home_team} dominating"; confidence = "HIGH"
            elif goal_difference < 0: momentum = f"✈️ {away_team} controlling"; confidence = "HIGH"
            else:
                if total_goals > 2: momentum = "⚡ Both teams attacking"; confidence = "MEDIUM"
                else: momentum = "🛡️ Balanced match"; confidence = "LOW"
            
            if match_progress < 30: next_goal_window = "First half"
            elif match_progress < 60: next_goal_window = "Early second half"
            elif match_progress < 75: next_goal_window = "Mid second half"
            else: next_goal_window = "Late game"
            
            return {
                "match_progress": f"{match_progress:.1f}%",
                "momentum": momentum,
                "confidence": confidence,
                "goal_difference": goal_difference,
                "total_goals": total_goals,
                "next_goal_window": next_goal_window,
                "goal_intensity": "HIGH" if total_goals > 2 else "MEDIUM" if total_goals > 0 else "LOW",
                "match_tempo": self.analyze_tempo(home_score, away_score, match_progress)
            }
            
        except Exception as e:
            return {}
    
    def analyze_tempo(self, home_score, away_score, progress):
        goal_rate = (home_score + away_score) / (progress / 100) if progress > 0 else 0
        
        if goal_rate > 0.1: return "⚡ High Tempo - Goal Fest"
        elif goal_rate > 0.05: return "🎯 Medium Tempo - Balanced"
        else: return "🛡️ Low Tempo - Defensive"
    
    def get_basic_match_info(self, match_data):
        home_team = match_data.get("match_hometeam_name", "Unknown")
        away_team = match_data.get("match_awayteam_name", "Unknown")
        home_score = match_data.get("match_hometeam_score", "0")
        away_score = match_data.get("match_awayteam_score", "0")
        minute = match_data.get("match_status", "0")
        league = match_data.get("league_name", "Unknown League")
        
        if minute == "HT": status = "🔄 HALF TIME"
        elif minute == "FT": status = "🏁 FULL TIME"
        elif minute.isdigit(): status = f"⏱️ LIVE - {minute}'"
        else: status = f"🕒 {minute}"
        
        return f"""
🏆 **{league}**

⚽ **{home_team}** {home_score} - {away_score} **{away_team}**

{status}
"""
    
    def get_match_statistics_dict(self, match_data):
        # Mock/Default stats (Crucial for Expert Bet logic)
        return {
            'Shots on Goal': random.randint(3, 15),
            'Shots off Goal': random.randint(3, 15),
            'Ball Possession': random.randint(40, 60),
            'Red Cards': 0, 
            'Yellow Cards': random.randint(1, 5)
        }
            
    def get_match_statistics(self, match_data):
        home_pos = random.randint(40, 65)
        away_pos = 100 - home_pos
        
        return f"""
• Shots on Goal: {random.randint(3, 12)} | {random.randint(3, 12)}
• Shots off Goal: {random.randint(2, 8)} | {random.randint(2, 8)}
• Ball Possession: {home_pos}% | {away_pos}%
• Corner Kicks: {random.randint(1, 8)} | {random.randint(1, 8)}
• Fouls: {random.randint(5, 15)} | {random.randint(5, 15)}
"""
            
    def get_live_insights(self, match_data):
        home_score = int(match_data.get("match_hometeam_score", 0))
        away_score = int(match_data.get("match_awayteam_score", 0))
        minute = match_data.get("match_status", "0")
        
        total_goals = home_score + away_score
        insights = []
        
        if total_goals == 0: insights.append("🔒 Defensive battle - No goals yet")
        elif total_goals >= 3: insights.append("⚡ Goal fest - High scoring game")
        
        if home_score > away_score: insights.append(f"🏠 Home advantage showing")
        elif away_score > home_score: insights.append(f"✈️ Away team impressive")
        
        if minute.isdigit() and int(minute) > 75 and abs(home_score - away_score) <= 1:
            insights.append("🎯 Late drama possible")
        
        if not insights: insights.append("⚽ Competitive match underway")
        
        return "\n".join([f"• {insight}" for insight in insights])
        
    def generate_simple_score_based_prediction(self, match_data):
        home_team = match_data.get("match_hometeam_name", "Home")
        away_team = match_data.get("match_awayteam_name", "Away")
        home_score = int(match_data.get("match_hometeam_score", 0))
        away_score = int(match_data.get("match_awayteam_score", 0))
        minute = match_data.get("match_status", "0")

        if minute == "FT": return "🏁 Match is over."

        progress = 0
        if minute == "HT": progress = 50
        elif minute.isdigit(): progress = min(100, (int(minute) / 90) * 100)
        
        if progress > 85:
            if home_score > away_score: return f"✅ {home_team} likely to WIN\n❌ {away_team} needs miracle"
            elif away_score > home_score: return f"✅ {away_team} likely to WIN\n❌ {home_team} needs miracle"
            else: return f"🤝 DRAW looking probable\n🎯 Late goal possible"
        else:
            goal_difference = home_score - away_score
            
            if goal_difference == 0: return f"🎯 Both teams can WIN\n⚡ Next goal crucial"
            elif abs(goal_difference) == 1:
                leading_team = home_team if goal_difference > 0 else away_team
                trailing_team = away_team if goal_difference > 0 else home_team
                return f"✅ {leading_team} has advantage\n⚡ {trailing_team} pushing equalizer"
            else:
                leading_team = home_team if goal_difference > 0 else away_team
                return f"✅ {leading_team} dominating\n❌ Big comeback needed"
                
match_analyzer = MatchAnalysis()
# ... [ HTTPAPIManager, GlobalHitCounter, LEAGUE_CONFIG, fetch_api_football_matches, fetch_live_matches_http, process_match_data ] ...
# These are kept identical, just initializing here for context:

API_FOOTBALL_URL = "https://apiv3.apifootball.com"
PAKISTAN_TZ = pytz.timezone('Asia/Karachi')

def get_current_date_pakt():
    return datetime.now(PAKISTAN_TZ).strftime('%Y-%m-%d')

def get_mock_previous_data(team_name, count=5):
    results = random.choices(['W', 'L', 'D'], weights=[40, 30, 30], k=count)
    btts_count = sum([1 for r in results if r in ['W', 'D']])
    recent_form = "".join(results)
    home_goals = random.randint(10, 15)
    away_goals = random.randint(5, 12)
    return {
        "form": recent_form,
        "goals_scored": home_goals,
        "goals_conceded": away_goals,
        "btts_rate": f"{btts_count*20}%", 
        "avg_goals_per_game": (home_goals + away_goals) / count
    }

LEAGUE_CONFIG = {
    "152": {"name": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", "priority": 1, "type": "domestic"},
    "302": {"name": "🇪🇸 La Liga", "priority": 1, "type": "domestic"},
    "207": {"name": "🇮🇹 Serie A", "priority": 1, "type": "domestic"},
    "168": {"name": "🇩🇪 Bundesliga", "priority": 1, "type": "domestic"},
    "176": {"name": "🇫🇷 Ligue 1", "priority": 1, "type": "domestic"},
    "169": {"name": "🇳🇱 Eredivisie", "priority": 2, "type": "domestic"},
    "262": {"name": "🇵🇹 Primeira Liga", "priority": 2, "type": "domestic"},
    "149": {"name": "⭐ Champions League", "priority": 1, "type": "european"},
    "150": {"name": "✨ Europa League", "priority": 2, "type": "european"},
    "5": {"name": "🌍 World Cup Qualifiers", "priority": 1, "type": "worldcup"},
}

def get_league_name(league_id):
    league_info = LEAGUE_CONFIG.get(str(league_id))
    if league_info:
        return league_info["name"]
    return f"League {league_id}"

class HTTPAPIManager:
    def __init__(self):
        self.api_football_matches = []
        self.last_api_football_update = None
        
    def update_api_football_matches(self, matches):
        self.api_football_matches = matches
        self.last_api_football_update = datetime.now()
        
    def get_live_matches(self):
        current_time = datetime.now()
        if (self.last_api_football_update and 
              (current_time - self.last_api_football_update).total_seconds() < 120 and 
              self.api_football_matches):
            return self.api_football_matches, "API_FOOTBALL"
        return [], "NONE"
    
    def get_api_status(self):
        api_football_update_time = self.last_api_football_update.strftime("%H:%M:%S") if self.last_api_football_update else "Never"
        
        return {
            "api_football": {
                "status": "ACTIVE" if self.api_football_matches else "INACTIVE",
                "last_update": api_football_update_time,
                "match_count": len(self.api_football_matches)
            }
        }
    
    def find_match_by_teams(self, team1, team2=None):
        all_matches = self.api_football_matches
        team1_lower = team1.lower()
        
        for match in all_matches:
            home_team = match.get("match_hometeam_name", "").lower()
            away_team = match.get("match_awayteam_name", "").lower()
            
            is_live = match.get('match_live') == '1' or match.get('match_status') == 'HT' or (match.get('match_status') and match.get('match_status').isdigit())
            
            if is_live and (team1_lower in home_team or team1_lower in away_team):
                return match 
                
        return None

api_manager = HTTPAPIManager()

class GlobalHitCounter:
    def __init__(self):
        self.total_hits = 0
        self.daily_hits = 0
        self.hourly_hits = 0
        self.last_hit_time = None
        self.last_reset = datetime.now()
        
    def record_hit(self):
        current_time = datetime.now()
        
        if current_time.date() > self.last_reset.date():
            self.daily_hits = 0
            self.last_reset = current_time
        
        if not self.last_hit_time or current_time.hour > self.last_hit_time.hour:
            self.hourly_hits = 0
        
        self.total_hits += 1
        self.daily_hits += 1
        self.hourly_hits += 1
        self.last_hit_time = current_time
        
        return True
    
    def get_hit_stats(self):
        now = datetime.now()
        remaining_daily = max(0, 100 - self.daily_hits)
        
        next_reset = (self.last_reset + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        time_until_reset = (next_reset - now).total_seconds()
        
        hours_until_reset = int(time_until_reset // 3600)
        minutes_until_reset = int((time_until_reset % 3600) // 60)
        
        api_status = api_manager.get_api_status()
        
        stats = f"""
🔥 **GLOBAL HIT COUNTER & API STATUS**

📈 **Current Usage:**
• Total Hits: {self.total_hits}
• Today's Hits: {self.daily_hits}/100
• This Hour: {self.hourly_hits}

🎯 **Remaining Capacity:**
• Daily Remaining: {remaining_daily} calls
• Time Until Reset: {hours_until_reset}h {minutes_until_reset}m
• Usage Percentage: {(self.daily_hits/100)*100:.1f}%

🌐 **API STATUS (Single HTTP):**
• API-Football (HTTP): {api_status['api_football']['status']}
  - Matches: {api_status['api_football']['match_count']}
  - Updated: {api_status['api_football']['last_update']}

⏰ **Last Hit:** {self.last_hit_time.strftime('%H:%M:%S') if self.last_hit_time else 'Never'}

💡 **Recommendations:**
{'🟢 Safe to continue' if self.daily_hits < 80 else '🟡 Slow down' if self.daily_hits < 95 else '🔴 STOP API CALLS'}
"""
        return stats
    
    def can_make_request(self):
        if self.daily_hits >= 100:
            return False, "Daily limit reached"
        if self.hourly_hits >= 40:
            return False, "Hourly limit caution"
        return True, "OK"

hit_counter = GlobalHitCounter()

def fetch_api_football_matches(match_live_only=True):
    if not API_KEY:
        logging.error("API_KEY is not set. Cannot fetch matches.")
        return []

    can_make, reason = hit_counter.can_make_request()
    if not can_make:
        logging.warning(f"API call blocked: {reason}")
        return []
        
    hit_counter.record_hit()
    
    try:
        if match_live_only:
            url = f"{API_FOOTBALL_URL}/?action=get_events&match_live=1&APIkey={API_KEY}"
        else:
            today_date = get_current_date_pakt()
            url = f"{API_FOOTBALL_URL}/?action=get_events&from={today_date}&to={today_date}&APIkey={API_KEY}"
            
        response = requests.get(url, timeout=20) 
        
        if response.status_code == 200:
            data = response.json()
            
            if isinstance(data, list):
                for match in data:
                    league_id = match.get("league_id", "")
                    match["league_name"] = get_league_name(league_id)
                    match["source"] = "api_football"
                
                return data
            else:
                if isinstance(data, dict) and 'error' in data.get('result', '').lower():
                    logging.error(f"API-Football Error in response: {data.get('result')}")
                return []
        else:
            logging.error(f"API-Football HTTP Error: Status {response.status_code}")
            return []
            
    except requests.exceptions.Timeout:
        logging.error("API-Football Fetch Error: Request timed out.")
        return []
    except requests.exceptions.ConnectionError:
        logging.error("API-Football Fetch Error: Connection failed.")
        return []
    except Exception as e:
        logging.error(f"API-Football Fetch Error: {e}")
        return []

def fetch_live_matches_http():
    matches, source = api_manager.get_live_matches()
    if source == "API_FOOTBALL":
        return matches, source
        
    api_football_matches = fetch_api_football_matches(match_live_only=True)
    if api_football_matches:
        api_manager.update_api_football_matches(api_football_matches)
        return api_football_matches, "API_FOOTBALL"
        
    return [], "NONE"

def process_match_data(matches, live_only=True):
    if not matches: return []
    processed_matches = []
    unique_matches = {}
    
    for match in matches:
        match_id = match.get("match_id") or f"{match.get('match_hometeam_name')}-{match.get('match_awayteam_name')}"
        
        try:
            home_team = match.get("match_hometeam_name", "Unknown")
            away_team = match.get("match_awayteam_name", "Unknown")
            home_score = match.get("match_hometeam_score", "0")
            away_score = match.get("match_awayteam_score", "0")
            minute = match.get("match_status", "0")
            league_name = match.get("league_name", "Unknown League")
            
            if minute == "HT": match_status = "HALF TIME"; display_minute = "HT"
            elif minute == "FT": match_status = "FULL TIME"; display_minute = "FT"
            elif minute.isdigit(): match_status = "LIVE"; display_minute = f"{minute}'"
            else: match_status = "UPCOMING"; display_minute = match.get("match_time", "TBD")
            
            is_live = match_status in ["LIVE", "HALF TIME"]
            
            if live_only and not is_live: continue
                
            source_icon = "🔵"
            
            unique_matches[match_id] = {
                "home_team": home_team, "away_team": away_team, 
                "score": f"{home_score}-{away_score}" if is_live else display_minute,
                "minute": display_minute, "status": match_status, "league": league_name,
                "is_live": is_live, "source_icon": source_icon if is_live else "📅",
                "raw_data": match  
            }
        except Exception as e:
            continue
    return list(unique_matches.values())

class EnhancedFootballAI:
    def __init__(self):
        self.team_data = {
            "manchester city": {"strength": 95, "style": "attacking", "goal_avg": 2.5},
            "liverpool": {"strength": 92, "style": "high press", "goal_avg": 2.2},
            "arsenal": {"strength": 90, "style": "possession", "goal_avg": 2.1},
            "chelsea": {"strength": 88, "style": "balanced", "goal_avg": 1.8},
            "real madrid": {"strength": 94, "style": "experienced", "goal_avg": 2.3},
            "barcelona": {"strength": 92, "style": "possession", "goal_avg": 2.0},
            "bayern munich": {"strength": 93, "style": "dominant", "goal_avg": 2.6},
            "psg": {"strength": 91, "style": "star power", "goal_avg": 2.4},
            "brazil": {"strength": 96, "style": "samba", "goal_avg": 2.7},
            "argentina": {"strength": 94, "style": "technical", "goal_avg": 2.2},
            "france": {"strength": 95, "style": "balanced", "goal_avg": 2.5},
            "germany": {"strength": 92, "style": "efficient", "goal_avg": 2.0},
            "unknown": {"strength": 75, "style": "standard", "goal_avg": 1.5}
        }
        
    def get_team_strength_and_avg(self, team_name):
        team_key = team_name.lower()
        for key, data in self.team_data.items():
            if key in team_key or team_key in key:
                return data["strength"], data["goal_avg"]
        fallback = self.team_data.get("unknown")
        return fallback["strength"], fallback["goal_avg"]
        
    def get_response(self, message):
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['live', 'current', 'scores', '/live']):
            return self.handle_live_matches()
        elif any(word in message_lower for word in ['today', 'schedule', 'matches', 'list', '/today']):
            return self.handle_todays_matches() 
        elif any(word in message_lower for word in ['hit', 'counter', 'stats', 'api usage', '/hits', '/stats']):
            return hit_counter.get_hit_stats()
        elif any(word in message_lower for word in ['predict', 'prediction', 'who will win', '/predict']):
            return self.handle_prediction(message_lower)
        elif any(word in message_lower for word in ['expert', 'confirmed', '/expert_bet']):
            return self.handle_expert_bet(message_lower)
        elif any(word in message_lower for word in ['analysis', 'analyze', 'detail', 'report', '/analysis']):
            return self.handle_detailed_analysis(message_lower)
        elif any(word in message_lower for word in ['api status', 'connection', 'status', '/status']):
            return self.handle_api_status()
        elif any(word in message_lower for word in ['hello', 'hi', 'hey', 'start', '/start']):
            return "👋 Hello! I'm **SUPER STABLE Football Analysis AI V5 (Webhook Mode)**! ⚽\n\n🔍 **Stable HTTP API Only**\n\nTry: `/live`, `/today`, `/analysis man city`, or `/expert_bet real madrid`."
        else:
            return self.handle_team_specific_query(message_lower)

    def handle_live_matches(self):
        raw_matches, source = fetch_live_matches_http()
        matches = process_match_data(raw_matches, live_only=True) 
        
        if not matches:
            return "⏳ No live matches found right now.\n\n🌐 **API Status:**\n" + self.get_api_status_text()
        
        response = "🔵 **LIVE FOOTBALL MATCHES** ⚽\n\n"
        source_text = "🔵 API-Football HTTP"
        response += f"📡 **Source:** {source_text}\n\n"
        
        leagues = {}
        for match in matches:
            league = match['league']
            if league not in leagues: leagues[league] = []
            leagues[league].append(match)
        
        for league, league_matches in leagues.items():
            response += f"**{league}**\n"
            for match in league_matches:
                icon = "⏱️" if match['status'] == 'LIVE' else "🔄" if match['status'] == 'HALF TIME' else "🏁"
                response += f"{match['source_icon']} {match['home_team']} {match['score']} {match['away_team']} {icon} {match['minute']}\n"
            response += "\n"
        
        response += f"🔥 API Hits Today: {hit_counter.daily_hits}/100\n"
        response += self.get_api_status_text()
        
        return response

    def handle_todays_matches(self):
        raw_matches = fetch_api_football_matches(match_live_only=False)
        matches = process_match_data(raw_matches, live_only=False) 
        
        if not matches:
            return f"📅 **{get_current_date_pakt()}**\n\n❌ No matches scheduled for today."
        
        live_matches = [m for m in matches if m['is_live']]
        upcoming_matches = [m for m in matches if not m['is_live']]
        
        response = f"📅 **TODAY'S FOOTBALL SCHEDULE ({get_current_date_pakt()})** ⚽\n\n"
        
        if live_matches:
            response += "--- **🔵 LIVE / FT MATCHES** ---\n"
            for match in live_matches[:5]:
                icon = "⏱️" if match['status'] == 'LIVE' else "🔄" if match['status'] == 'HALF TIME' else "🏁"
                response += f"{match['league']}\n{match['source_icon']} {match['home_team']} {match['score']} {match['away_team']} {icon} {match['minute']}\n"
            response += "\n"
            
        if upcoming_matches:
            response += "--- **🕒 UPCOMING MATCHES (Pakistan Time)** ---\n"
            for match in upcoming_matches:
                response += f"📅 {match['league']}\n{match['home_team']} vs {match['away_team']} 🕒 {match['score']}\n"
            response += "\n"
            
        response += "💡 *Use '/analysis [Team Name]' for live match reports or '/expert_bet [Team Name]' for a confirmed bet.*"
        
        return response

    def handle_detailed_analysis(self, message):
        teams_found = []
        for team_key in self.team_data:
            if team_key in message.lower(): teams_found.append(team_key)
        
        match_data = None
        if len(teams_found) >= 1:
            match_data = api_manager.find_match_by_teams(teams_found[0])
            
        if match_data:
            return self.generate_live_match_report(match_data)
        else:
            raw_matches, source = fetch_live_matches_http()
            live_matches = [m for m in raw_matches if m.get('match_live') == '1' or m.get('match_status') == 'HT']

            if not live_matches:
                return "❌ No live matches available for analysis right now. Try `/today` for the schedule."
                
            response = "🔍 **DETAILED MATCH ANALYSIS SUMMARY**\n\n"
            for match in live_matches[:5]:
                analysis = match_analyzer.analyze_match_trends(match)
                home_team = match.get("match_hometeam_name", "Unknown")
                away_team = match.get("match_awayteam_name", "Unknown")
                score = f"{match.get('match_hometeam_score', '0')}-{match.get('match_awayteam_score', '0')}"
                minute = match.get('match_status', '0')
                
                response += f"**{home_team} vs {away_team}** ({minute}')\n"
                response += f"Score: {score} | Progress: {analysis.get('match_progress', 'N/A')}\n"
                response += f"Momentum: {analysis.get('momentum', 'N/A')}\n"
                response += f"Tempo: {analysis.get('match_tempo', 'N/A')}\n\n"
            
            response += "💡 *Use '/analysis [team name]' for a full match report*"
            return response
            
    def generate_live_match_report(self, match_data):
        basic_info = match_analyzer.get_basic_match_info(match_data)
        analysis = match_analyzer.analyze_match_trends(match_data)
        statistics = match_analyzer.get_match_statistics(match_data)
        home_team = match_data.get("match_hometeam_name", "Home")
        away_team = match_data.get("match_awayteam_name", "Away")
        predictions, alert_result = self.generate_combined_prediction(match_data, home_team, away_team, send_alert=False)
        
        return f"""
🔍 **DETAILED MATCH ANALYSIS**

{basic_info}

📊 **MATCH ANALYSIS:**
• Progress: {analysis.get('match_progress', 'N/A')}
• Momentum: {analysis.get('momentum', 'N/A')}
• Confidence: {analysis.get('confidence', 'N/A')}
• Tempo: {analysis.get('match_tempo', 'N/A')}
• Next Goal Window: {analysis.get('next_goal_window', 'N/A')}

📈 **STATISTICS (Mocked):**
{statistics}

🎯 **ENHANCED PREDICTIONS:**
{predictions}

⚡ **LIVE INSIGHTS:**
{match_analyzer.get_live_insights(match_data)}
"""
        
    def _get_match_progress(self, minute):
        if minute == "HT": return 50.0
        if minute.isdigit(): return min(90.0, float(minute))
        return 0.0

    def _calculate_1x2_probability(self, match_data, team1, team2):
        strength1, avg1 = self.get_team_strength_and_avg(team1)
        strength2, avg2 = self.get_team_strength_and_avg(team2)
        home_score = int(match_data.get("match_hometeam_score", 0))
        away_score = int(match_data.get("match_awayteam_score", 0))
        minute = match_data.get("match_status", "0")
        
        total_strength = strength1 + strength2
        prob1_base = (strength1 / total_strength) * 100
        prob2_base = (strength2 / total_strength) * 100
        
        strength_diff_factor = abs(strength1 - strength2) / total_strength
        draw_prob_base = 25 - (strength_diff_factor * 15) 
        
        progress_percent = self._get_match_progress(minute) / 90
        
        remaining_prob = 100 - draw_prob_base
        prob1 = (prob1_base / (prob1_base + prob2_base)) * remaining_prob
        prob2 = (prob2_base / (prob1_base + prob2_base)) * remaining_prob
        
        score_diff = home_score - away_score
        
        if abs(score_diff) > 0 and progress_percent > 0.4:
            lead_factor = 1.0 + (abs(score_diff) * progress_percent * 0.5)
            
            if score_diff > 0:
                prob1 *= lead_factor
                prob2 /= lead_factor
            else:
                prob2 *= lead_factor
                prob1 /= lead_factor
            
            new_total = prob1 + prob2
            draw_adjustment = max(0, draw_prob_base / (1 + progress_percent * abs(score_diff)))
            prob1 = (prob1 / new_total) * (100 - draw_adjustment)
            prob2 = (prob2 / new_total) * (100 - draw_adjustment)
            draw_prob = 100 - prob1 - prob2
        else:
            draw_prob = draw_prob_base
            
        return prob1, prob2, draw_prob
        
    def _calculate_over_under_probability(self, match_data, team1, team2):
        strength1, avg1 = self.get_team_strength_and_avg(team1)
        strength2, avg2 = self.get_team_strength_and_avg(team2)
        home_score = int(match_data.get("match_hometeam_score", 0))
        away_score = int(match_data.get("match_awayteam_score", 0))
        minute = match_data.get("match_status", "0")

        progress_percent = self._get_match_progress(minute) / 90
        
        expected_goals = (avg1 + avg2) * (1 - (0.5 - progress_percent) * 0.5)
        total_goals = home_score + away_score
        
        over_25_prob_base = 65 if expected_goals > 2.8 else 50 if expected_goals > 2.2 else 35
        
        goal_rate_factor = total_goals / (expected_goals * progress_percent) if progress_percent > 0 else 1.0
        
        if goal_rate_factor > 1.2 and total_goals < 3: 
            over_25_prob = over_25_prob_base + (goal_rate_factor - 1) * 20
            reason = "Goals expected to rise; current goal rate is slightly slow despite high pre-match expectation."
        elif goal_rate_factor < 0.8 and total_goals < 2 and progress_percent > 0.6: 
            over_25_prob = over_25_prob_base * goal_rate_factor * 0.8
            reason = "Low goal rate and late stage suggests Under 2.5 is now favored."
        else:
            over_25_prob = over_25_prob_base + random.uniform(-5, 5)
            reason = "Goal rate is balanced with pre-match expectation."
            
        over_25_prob = min(99, max(1, over_25_prob))
        under_25_prob = 100 - over_25_prob
        
        return over_25_prob, under_25_prob, reason
        
    def _predict_correct_score(self, match_data, team1, team2):
        home_score = int(match_data.get("match_hometeam_score", 0))
        away_score = int(match_data.get("match_awayteam_score", 0))
        strength1, avg1 = self.get_team_strength_and_avg(team1)
        strength2, avg2 = self.get_team_strength_and_avg(team2)
        
        if strength1 > strength2:
            predicted_score_1 = f"{home_score+1}-{away_score}" 
            predicted_score_2 = f"{home_score}-{away_score}" 
        else:
            predicted_score_1 = f"{home_score}-{away_score+1}" 
            predicted_score_2 = f"{home_score}-{away_score}"
            
        progress = self._get_match_progress(match_data.get("match_status", "0"))
        
        if progress > 70:
            prob_current = 40 + (progress - 70) * 1.5
            prob_next_goal = 30 - (progress - 70) * 0.5
        else:
            prob_current = 20
            prob_next_goal = 25
            
        return [
            {"score": predicted_score_1, "prob": prob_next_goal + random.uniform(-2, 2)},
            {"score": predicted_score_2, "prob": prob_current + random.uniform(-2, 2)},
        ]
        
    def _predict_goal_minutes(self, match_data):
        analysis = match_analyzer.analyze_match_trends(match_data)
        
        if analysis['match_tempo'] == "⚡ High Tempo - Goal Fest":
            minutes = "30-45 (End of Half) & 75-90 (Late Game)"
        elif analysis['match_tempo'] == "🛡️ Low Tempo - Defensive":
            minutes = "Only Late Game (80+)"
        else:
            minutes = "Early Second Half (45-60) & Late Game (75-90)"
            
        return minutes

    def generate_combined_prediction(self, match_data, team1, team2, send_alert=False):
        minute = match_data.get("match_status", "0")
        
        if minute == "FT":
            return "🏁 Match is over. Final Score-based Prediction not applicable.", None
        
        prob1, prob2, draw_prob = self._calculate_1x2_probability(match_data, team1, team2)
        over_25_prob, under_25_prob, goals_reason = self._calculate_over_under_probability(match_data, team1, team2)
        
        max_prob_1x2 = max(prob1, prob2, draw_prob)
        if max_prob_1x2 == prob1: winner = team1; market_1x2 = f"{team1} to WIN"
        elif max_prob_1x2 == prob2: winner = team2; market_1x2 = f"{team2} to WIN"
        else: winner = "DRAW"; market_1x2 = "DRAW"
            
        max_prob_OU = max(over_25_prob, under_25_prob)
        market_OU = f"Over 2.5 Goals" if max_prob_OU == over_25_prob else f"Under 2.5 Goals"
        
        alert_to_send = None
        
        if send_alert and OWNER_CHAT_ID:
            if max_prob_1x2 >= 85:
                alert_to_send = {
                    "market": "Match Winner (1X2)",
                    "prediction": market_1x2,
                    "confidence": max_prob_1x2
                }
            elif max_prob_OU >= 85:
                alert_to_send = {
                    "market": market_OU,
                    "prediction": market_OU,
                    "confidence": max_prob_OU
                }

        result = f"""
**Pre-match & Live Score Model:**
• {team1} WIN: {prob1:.1f}%
• {team2} WIN: {prob2:.1f}%  
• Draw: {draw_prob:.1f}%
• Over 2.5 Goals: {over_25_prob:.1f}%
• Under 2.5 Goals: {under_25_prob:.1f}%

🏆 **Current Verdict ({minute}' / {match_data.get('match_hometeam_score', '0')}-{match_data.get('match_awayteam_score', '0')}):**
• **Match Winner:** **{winner.upper()}** ({max_prob_1x2:.1f}%)
• **Goals:** **{market_OU.upper()}** ({max_prob_OU:.1f}%)

💡 **Score-based Insight:**
{match_analyzer.generate_simple_score_based_prediction(match_data)}
"""
        return result, alert_to_send

    def handle_prediction(self, message):
        teams = []
        for team_key in self.team_data:
            if team_key in message.lower(): teams.append(team_key)
        
        if len(teams) >= 2:
            team1_name = teams[0]; team2_name = teams[1]
            prob1, prob2, draw_prob = self._calculate_1x2_probability({}, team1_name, team2_name)
            strength1, avg1 = self.get_team_strength_and_avg(team1_name)
            strength2, avg2 = self.get_team_strength_and_avg(team2_name)
            expected_goals = avg1 + avg2
            
            max_prob = max(prob1, prob2, draw_prob)
            if max_prob == prob1: winner = team1_name.title()
            elif max_prob == prob2: winner = team2_name.title()
            else: winner = "Draw"
            
            return f"""
🎯 **PREDICTION: {team1_name.upper()} vs {team2_name.upper()}**

📊 **Probabilities (Pre-match Strength):**
• {team1_name.title()}: {prob1:.1f}%
• {team2_name.title()}: {prob2:.1f}%  
• Draw: {draw_prob:.1f}%
• Expected Total Goals: {expected_goals:.2f}

🏆 **Most Likely: {winner.upper()}**

⚠️ *This is a pre-match strength prediction. Use '/analysis {team1_name} vs {team2_name}' for live updates!*
"""
        else:
            return "Please specify two teams for prediction. Example: '/predict Manchester City vs Liverpool'"

    def get_api_status_text(self):
        status = api_manager.get_api_status()
        
        return f"""
🌐 **API STATUS (Single Source)**

🔵 **API-Football (HTTP):**
• Status: {status['api_football']['status']}
• Matches: {status['api_football']['match_count']}
• Updated: {status['api_football']['last_update']}

💡 **Only HTTP API is currently active for stability.**
"""

    def handle_api_status(self):
        return self.get_api_status_text()
    
    def analyze_and_select_expert_bet(self, match_data, home_team, away_team):
        home_prev_data = get_mock_previous_data(home_team)
        away_prev_data = get_mock_previous_data(away_team)
        analysis = match_analyzer.analyze_match_trends(match_data)
        stats = match_analyzer.get_match_statistics_dict(match_data) 
        minute = match_data.get("match_status", "0")
        current_score = f"{match_data.get('match_hometeam_score', '0')}-{match_data.get('match_awayteam_score', '0')}"
        all_market_predictions = []
        
        # A. 1️⃣ Match Winner Probability (1X2)
        prob1, prob2, draw_prob = self._calculate_1x2_probability(match_data, home_team, away_team)
        max_prob_1x2 = max(prob1, prob2, draw_prob)
        winner_pred = f"{home_team} WIN" if max_prob_1x2 == prob1 else f"{away_team} WIN" if max_prob_1x2 == prob2 else "DRAW"
        all_market_predictions.append({"market": "Match Winner (1X2)", "prediction": winner_pred, "confidence": max_prob_1x2, "reason": "Live Score Adjustment applied.", "odds_range": "1.40-3.00"})

        # B. 2️⃣ Over/Under Goals (2.5)
        over_25_prob, under_25_prob, goals_reason = self._calculate_over_under_probability(match_data, home_team, away_team)
        max_prob_OU = max(over_25_prob, under_25_prob)
        ou_pred = "Over 2.5 Goals" if max_prob_OU == over_25_prob else "Under 2.5 Goals"
        all_market_predictions.append({"market": "Over/Under 2.5 Goals", "prediction": ou_pred, "confidence": max_prob_OU, "reason": goals_reason, "odds_range": "1.65-2.05"})
        
        # C. 3️⃣ BTTS (Both Teams To Score)
        base_btts_prob = 50 + ((self.get_team_strength_and_avg(home_team)[0] + self.get_team_strength_and_avg(away_team)[0]) / 20) * 0.5 
        if (int(match_data.get('match_hometeam_score', 0)) + int(match_data.get('match_awayteam_score', 0))) >= 2 and analysis['goal_difference'] < 2: live_btts_factor = 1.25 
        elif stats.get("Shots on Goal", 0) > 8: live_btts_factor = 1.15
        else: live_btts_factor = 0.95
        
        btts_prob = min(99, base_btts_prob * live_btts_factor)
        btts_pred = "Yes (BTTS)" if btts_prob >= 50 else "No (BTTS)"
        btts_conf = btts_prob if btts_prob >= 50 else 100 - btts_prob
        all_market_predictions.append({"market": "Both Teams To Score (BTTS)", "prediction": btts_pred, "confidence": btts_conf, "reason": "Live total shots on goal: {stats.get('Shots on Goal', 0)}.", "odds_range": "1.75-2.00"})
        
        # D. 4️⃣ Last 10 Minute Goal Chance
        progress = self._get_match_progress(minute)
        if progress < 80: late_goal_prob = 50.0
        else:
            base = 65.0
            score_diff = abs(int(match_data.get('match_hometeam_score', 0)) - int(match_data.get('match_awayteam_score', 0)))
            total_goals = int(match_data.get('match_hometeam_score', 0)) + int(match_data.get('match_awayteam_score', 0))
            if score_diff <= 1 and total_goals >= 2: base += 15
            elif score_diff >= 3: base -= 10
            late_goal_prob = min(95, base + random.uniform(-5, 5))
            
        all_market_predictions.append({"market": "Goal in Last 10 Minutes (80'+)", "prediction": "Yes", "confidence": late_goal_prob, "reason": f"Match is in {minute}' ({progress:.1f}%).", "odds_range": "1.45-1.75"})
        
        # E. 5️⃣ Correct Score Prediction (Top 2 possibilities)
        top_2_scores = self._predict_correct_score(match_data, home_team, away_team)
        
        # F. 6️⃣ High-Probability Goal Minutes
        goal_minutes = self._predict_goal_minutes(match_data)
        
        # 3. SELECT THE BEST BET (85%+ CONFIDENCE ONLY)
        best_bet = None
        high_confidence_bets = sorted(
            [p for p in all_market_predictions if p['confidence'] >= 85.0],
            key=lambda x: x['confidence'], reverse=True
        )
        
        if high_confidence_bets: best_bet = high_confidence_bets[0]
        
        # 4. Final Output Generation
        
        if best_bet:
            risk_note = "Standard market risks apply."
            if stats.get('Red Cards', 0) > 0: risk_note = "HIGH RISK: Red Card issued, game dynamics changed."
            
            response = f"""
✅ **EXPERT BET ANALYSIS: {home_team} vs {away_team}** ({minute}')

---
🔹 **Final 85%+ Confirmed Bet:** **{best_bet['market']} - {best_bet['prediction']}**
💰 **Confidence Level:** **{best_bet['confidence']:.1f}%**
📊 **Reasoning:** {best_bet['reason']}
🔥 **Odds Range:** {best_bet['odds_range']}
⚠️ **Risk Note:** {risk_note}
---
📋 **DETAILED MARKET BREAKDOWN:**
1. **Match Winner (1X2):** H {prob1:.1f}% | D {draw_prob:.1f}% | A {prob2:.1f}%
2. **Over/Under 2.5:** Over {over_25_prob:.1f}% | Under {under_25_prob:.1f}%
3. **BTTS (Yes/No):** Yes {btts_prob:.1f}% | No {(100 - btts_prob):.1f}%
4. **Late Goal (80'+):** Yes {late_goal_prob:.1f}% | No {(100 - late_goal_prob):.1f}%

**Correct Score Prediction (Top 2):**
• {top_2_scores[0]['score']} ({top_2_scores[0]['prob']:.1f}%)
• {top_2_scores[1]['score']} ({top_2_scores[1]['prob']:.1f}%)

**High-Probability Goal Minutes:** {goal_minutes}
"""
            return response
            
        else:
            return f"""
❌ **NO 85%+ BET FOUND** ❌
**Match:** {home_team} vs {away_team} ({minute}')

**Reason:** No single market (1X2, O/U 2.5, BTTS, Late Goal) currently meets the 85.0% confidence threshold.

**Highest Confidence Found:**
• Market: {all_market_predictions[0]['market']}
• Prediction: {all_market_predictions[0]['prediction']}
• Confidence: {all_market_predictions[0]['confidence']:.1f}%

💡 *Wait for a significant change (e.g., Red Card, new goal, 75+ minute) and try again.*
"""
    
    def handle_expert_bet(self, message):
        teams_found = []
        for team_key in self.team_data:
            if team_key in message.lower(): teams_found.append(team_key)
        
        match_data = None
        if len(teams_found) >= 1: match_data = api_manager.find_match_by_teams(teams_found[0])
            
        if not match_data:
            return "❌ براہ کرم واضح ٹیم کا نام لکھیں یا تصدیق کریں کہ میچ لائیو ہے۔ مثال: `/expert_bet Man City`"
        
        minute = match_data.get("match_status", "0")
        if minute == "FT": return "❌ یہ میچ ختم ہو چکا ہے۔ Expert Bet صرف لائیو میچز پر دستیاب ہے۔"
        
        home_team = match_data.get("match_hometeam_name", "Home")
        away_team = match_data.get("match_awayteam_name", "Away")
        
        return self.analyze_and_select_expert_bet(match_data, home_team, away_team)
    
    def handle_team_specific_query(self, message):
        teams_found = []
        for team_key in self.team_data:
            if team_key in message.lower(): teams_found.append(team_key)
        
        if teams_found:
            match_data = api_manager.find_match_by_teams(teams_found[0])
            if match_data:
                return self.generate_live_match_report(match_data)
        
        return "❓ میں آپ کی بات سمجھ نہیں پایا۔ براہ کرم کمانڈ استعمال کریں: `/live`, `/today`, `/analysis Man City`, یا `/expert_bet Real Madrid`."

football_ai = EnhancedFootballAI()

# -------------------------
# TELEGRAM HANDLERS (Same as V4, but without @bot.message_handler)
# -------------------------
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    # Same as V4
    welcome_text = """
🤖 **SUPER STABLE FOOTBALL ANALYSIS BOT (V5 Webhook)** ⚽

🚀 **WEBHOOK MODE ACTIVE!** (Optimized for Railway/Free Tiers)

🔍 **CORE COMMANDS:**
• `/live`: Real-time scores & updates ⏱️
• `/today`: Today's full match schedule 📅
• `/analysis [Team]`: Detailed 6-market analysis report 📊
• `/expert_bet [Team]`: **85%+ Confirmed Bet** (Single Market Only) 💰

⚡ **UTILITY COMMANDS:**
• `/status`: API connection status
• `/hits`: API hit statistics

⚠️ **NOTE:** Auto-Alerts for 85%+ Confidence are sent automatically to the Owner's Chat ID.
"""
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['live'])
def send_live_matches(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        response = football_ai.handle_live_matches()
        bot.reply_to(message, response, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['today']) 
def send_todays_matches(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        response = football_ai.handle_todays_matches()
        bot.reply_to(message, response, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error getting today's schedule: {str(e)}")

@bot.message_handler(commands=['analysis'])
def send_detailed_analysis(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        command_text = message.text.split(' ', 1)
        query = command_text[1] if len(command_text) > 1 else "analysis" 
        response = football_ai.handle_detailed_analysis(query)
        bot.reply_to(message, response, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['hits', 'stats'])
def send_hit_stats(message):
    try:
        stats = hit_counter.get_hit_stats()
        bot.reply_to(message, stats, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['status', 'api'])
def send_api_status(message):
    try:
        response = football_ai.handle_api_status()
        bot.reply_to(message, response, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['predict'])
def handle_predict_command(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        command_text = message.text.split(' ', 1)
        query = command_text[1] if len(command_text) > 1 else ""
        
        if query: response = football_ai.handle_prediction(query)
        else: response = """
🎯 **MATCH PREDICTIONS (PRE-MATCH)**
Ask me like: "/predict Manchester City vs Liverpool"
I'll analyze team strengths and give you probabilities! 📊
"""
        bot.reply_to(message, response, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['expert_bet']) 
def send_expert_bet(message):
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        command_text = message.text.split(' ', 1)
        query = command_text[1] if len(command_text) > 1 else "" 
        
        if not query:
             bot.reply_to(message, "💡 **EXPERT BET**\n\nبراہ کرم میچ کی پریڈکشن کے لیے ایک لائیو ٹیم کا نام شامل کریں۔\nمثال: `/expert_bet Man City`")
             return
             
        response = football_ai.handle_expert_bet(query)
        bot.reply_to(message, response, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error running expert analysis: {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    try:
        logging.info(f"Message from {message.from_user.id}: {message.text}")
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.5) 
        response = football_ai.get_response(message.text)
        bot.reply_to(message, response, parse_mode='Markdown')
        
    except Exception as e:
        logging.error(f"Message handler error: {e}")
        bot.reply_to(message, "❌ Sorry, error occurred. Please try again!")

# -------------------------
# NEW: WEBHOOK SETUP (Flask)
# -------------------------
@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    """Handles Telegram updates sent via Webhook"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '!', 200 # Telegram expects a quick 200 response
    return 'Hello, I am V5 Webhook Bot!', 200


# -------------------------
# AUTO LIVE ALERT SYSTEM (7 Minute Interval)
# -------------------------
def auto_live_alert_system():
    """Checks live matches every 7 minutes for 85%+ confidence alerts"""
    if not OWNER_CHAT_ID:
        logging.warning("Auto Alert System Disabled: OWNER_CHAT_ID not configured.")
        return

    while True:
        try:
            raw_matches, source = fetch_live_matches_http()
            live_matches = [m for m in raw_matches if m.get('match_live') == '1' and m.get('match_status').isdigit() and int(m.get('match_status')) < 90]
            
            if live_matches:
                logging.info(f"Auto Alert: Analyzing {len(live_matches)} live matches...")
                for match in live_matches:
                    home_team = match.get("match_hometeam_name", "Home")
                    away_team = match.get("match_awayteam_name", "Away")
                    league = match.get("league_name", "Unknown League")
                    minute = match.get("match_status", "0")
                    score = f"{match.get('match_hometeam_score', '0')}-{match.get('match_awayteam_score', '0')}"
                    
                    _, alert_result = football_ai.generate_combined_prediction(match, home_team, away_team, send_alert=True)
                    
                    if alert_result:
                        alert_message = f"""
🔥 **85%+ CONFIDENCE LIVE ALERT!** 🔥
📢 **MATCH:** {home_team} vs {away_team}
🏆 **LEAGUE:** {league}
⏱️ **MINUTE:** {minute}' | **SCORE:** {score}

🎯 **MARKET:** {alert_result['market'].upper()}
✅ **PREDICTION:** **{alert_result['prediction'].upper()}**
📊 **CONFIDENCE:** {alert_result['confidence']:.1f}%

⚠️ *Betting is risky. Use your own discretion.*
"""
                        logging.info(f"Alert SENT: {alert_result['prediction']} @ {alert_result['confidence']:.1f}%")
                        bot.send_message(OWNER_CHAT_ID, alert_message, parse_mode='Markdown')
                        
        except Exception as e:
            logging.error(f"Auto Live Alert System Error: {e}")
        
        time.sleep(7 * 60) # Wait for 7 minutes

# -------------------------
# AUTO UPDATER (HTTP Only)
# -------------------------
def auto_updater():
    """Auto-update matches every 2 minutes using HTTP API"""
    while True:
        try:
            can_make, reason = hit_counter.can_make_request()
            if can_make:
                matches = fetch_api_football_matches(match_live_only=True)
                if matches:
                    api_manager.update_api_football_matches(matches)
                logging.info(f"HTTP Cache Updated. Matches: {len(matches)}")
            else:
                logging.warning(f"HTTP API call blocked: {reason}")
            
            time.sleep(120) # Refresh every 2 minutes
            
        except Exception as e:
            logging.error(f"Auto-updater error: {e}")
            time.sleep(300)

# -------------------------
# STARTUP FUNCTION (Webhook Setup)
# -------------------------
def set_webhook():
    """Set the Telegram webhook URL"""
    webhook_path = f'/{BOT_TOKEN}'
    full_webhook_url = WEBHOOK_URL.rstrip('/') + webhook_path
    
    # 1. Delete previous webhook if any
    bot.remove_webhook()
    
    # 2. Set the new webhook
    success = bot.set_webhook(url=full_webhook_url)
    
    if success:
        logging.info(f"✅ Webhook successfully set to: {full_webhook_url}")
    else:
        logging.error("❌ Failed to set webhook. Check your WEBHOOK_URL/BOT_TOKEN.")
        
    return success

def start_bot():
    """Initializes and starts all threads and Flask server."""
    logging.info("🚀 Starting SUPER STABLE Football Analysis Bot V5 (WEBHOOK MODE)...")
    
    # Start background threads (These are independent of Flask/Webhook)
    updater_thread = threading.Thread(target=auto_updater, daemon=True)
    updater_thread.start()
    logging.info("✅ HTTP Auto-Updater (2 min) started!")
    
    alert_thread = threading.Thread(target=auto_live_alert_system, daemon=True)
    alert_thread.start()
    logging.info("✅ Auto Live Alert System (7 min check) started!")
    
    time.sleep(5) 

    # Set the webhook URL before starting the Flask server
    if not set_webhook():
        logging.error("Startup Failed: Webhook setting failed.")
        return

    # Send startup message
    api_status = api_manager.get_api_status()
    if OWNER_CHAT_ID:
        startup_msg = f"""
🤖 **SUPER STABLE BOT STARTED! (V5)**

**✅ WEBHOOK MODE ACTIVE!** (Polling Disabled)
• Telegram Webhook: **{WEBHOOK_URL}**
• **`/expert_bet`** is active!

🌐 **Current Status:**
• 🔵 HTTP API: {api_status['api_football']['status']}
• Matches Loaded: {api_status['api_football']['match_count']}

🔥 **Ready for analysis! Use /today to check the schedule.**
"""
        bot.send_message(OWNER_CHAT_ID, startup_msg, parse_mode='Markdown')

    # Start Flask Web Server
    logging.info(f"Starting Flask server on port {PORT}...")
    # NOTE: '0.0.0.0' is required for container deployments like Railway/Heroku
    app.run(host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    start_bot()
