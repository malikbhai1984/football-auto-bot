import telebot
import requests
import json
import time
import threading
import os
import random
from flask import Flask, request, abort
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
import logging
# --- Set up basic logging for Gunicorn/Flask errors ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. Environment and Configuration ---
load_dotenv()

# Get Environment Variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
API_KEY = os.getenv('API_KEY')
OWNER_CHAT_ID = os.getenv('OWNER_CHAT_ID')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

# Basic checks
if not BOT_TOKEN or not API_KEY or not WEBHOOK_URL:
    logger.error("❌ Error: BOT_TOKEN, API_KEY, or WEBHOOK_URL not set.")
    exit(1)

# Telegram Bot Initialization
bot = telebot.TeleBot(BOT_TOKEN, parse_mode='Markdown')

# Flask App Initialization
app = Flask(__name__)

# Constants
LEAGUE_CONFIG = {
    "Premier League": 140, 
    "La Liga": 140, 
    # ... other leagues
}

# --- 2. Global State and Utility Classes ---

class GlobalHitCounter:
    """Tracks daily API hits (Mock limit: 100)"""
    def __init__(self):
        self.daily_hits = 0
        self.last_reset_date = datetime.now(pytz.utc).date()

    def increment(self):
        now_date = datetime.now(pytz.utc).date()
        if now_date > self.last_reset_date:
            self.daily_hits = 0
            self.last_reset_date = now_date
        self.daily_hits += 1
        return self.daily_hits

    def get_hit_stats(self):
        return f"🔥 API Hits Today: {self.daily_hits}/100\nLast Reset: {self.last_reset_date.strftime('%Y-%m-%d')}"

hit_counter = GlobalHitCounter()

class HTTPAPIManager:
    """Manages API data caching and fetching via HTTP/HTTPS"""
    def __init__(self):
        self.match_cache = {}
        self.last_fetch_time = None
        self.api_status = True

    def fetch_api_football_matches(self, match_live_only=False):
        """Fetches matches from API-Football and updates cache."""
        global API_KEY
        
        if hit_counter.daily_hits >= 100:
            logger.warning("🛑 API Limit Reached for today. Serving from cache.")
            return self.match_cache.get('today_matches', []), 'Cache'

        url = "https://v3.football.api-sports.io/fixtures"
        headers = {
            'x-apisports-key': API_KEY
        }
        
        today = datetime.now(pytz.utc).strftime('%Y-%m-%d')
        
        try:
            params = {
                'date': today,
                'status': 'TBD-PST' if not match_live_only else 'LIVE-HT-ET-BT'
            }
            hit_counter.increment()
            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if data and data.get('response'):
                self.api_status = True
                self.match_cache['today_matches'] = data['response']
                self.last_fetch_time = datetime.now(pytz.utc)
                return data['response'], 'API-Football HTTP'
            else:
                logger.info("API returned empty response.")
                self.api_status = True
                return [], 'API-Football HTTP'
                
        except requests.exceptions.RequestException as e:
            logger.error(f"API Fetch Error: {e}")
            self.api_status = False
            return self.match_cache.get('today_matches', []), 'Cache (Error)'
            
    def find_match_by_teams(self, team_name):
        matches, _ = self.fetch_api_football_matches(match_live_only=False)
        team_name_lower = team_name.lower()
        
        for match in matches:
            home = match['teams']['home']['name'].lower()
            away = match['teams']['away']['name'].lower()
            
            if team_name_lower in home or team_name_lower in away:
                return match
        return None

    def get_api_status_text(self):
        status = "✅ Connected" if self.api_status else "❌ Disconnected"
        last_fetch = self.last_fetch_time.strftime("%H:%M:%S UTC") if self.last_fetch_time else "N/A"
        return f"🌐 API Status: {status}\n🕒 Last Successful Fetch: {last_fetch}"
        
api_manager = HTTPAPIManager()

class MatchAnalysis:
    # ... (All methods inside MatchAnalysis remain the SAME as V6) ...
    def analyze_match_trends(self, match_data):
        """Generates mock analysis trends based on score/minute."""
        status = match_data['fixture']['status']['short']
        minute_str = match_data['fixture']['status']['elapsed']
        
        home_score = match_data['goals']['home']
        away_score = match_data['goals']['away']
        
        if status in ['FT', 'AET', 'PEN']: return {"match_progress": "Finished", "momentum": "N/A", "confidence": "N/A", "match_tempo": "N/A", "next_goal_window": "N/A", "goal_difference": 0}
        
        if minute_str: minute = int(minute_str)
        else: minute = 0

        goal_diff = abs(home_score - away_score)
        total_goals = home_score + away_score
        
        if total_goals >= 3 and minute < 60:
            momentum = "High Attacking Pressure"
            tempo = "⚡ High Tempo - Goal Fest"
            next_goal_window = "Next 10 Minutes"
        elif total_goals == 0 and minute > 30 and minute < 70:
            momentum = "Stalemate / Midfield Battle"
            tempo = "🛡️ Low Tempo - Defensive"
            next_goal_window = "Second Half (60-90)"
        else:
            momentum = "Balanced / Current Leader Defense"
            tempo = "Medium Tempo"
            next_goal_window = "End of Half (40-45) or (75-90)"

        confidence = f"{90 - (minute / 2)}" 
        progress = f"{minute/90*100:.1f}%"
        
        return {
            "match_progress": progress,
            "momentum": momentum,
            "confidence": f"{confidence:.1f}%",
            "match_tempo": tempo,
            "next_goal_window": next_goal_window,
            "goal_difference": goal_diff
        }

    def get_match_statistics(self, match_data):
        stats = self.get_match_statistics_dict(match_data)
        response = ""
        for k, v in stats.items():
            response += f"• {k}: {v}\n"
        return response

    def get_match_statistics_dict(self, match_data):
        minute_str = match_data['fixture']['status']['elapsed']
        if minute_str: minute = int(minute_str)
        else: minute = 0
        
        total_shots = max(10, 15 + random.randint(-5, 5))
        shots_on_goal = int(total_shots / 3)
        possession = f"{50 + random.randint(-5, 5)}% - {50 - random.randint(-5, 5)}%"
        
        return {
            "Total Shots": total_shots,
            "Shots on Goal": shots_on_goal,
            "Possession": possession,
            "Corners": random.randint(5, 12),
            "Red Cards": 0,
            "Free Kicks": random.randint(15, 25)
        }

    def get_basic_match_info(self, match_data):
        home = match_data['teams']['home']['name']
        away = match_data['teams']['away']['name']
        score = f"{match_data['goals']['home']}-{match_data['goals']['away']}"
        minute = match_data['fixture']['status']['elapsed'] if match_data['fixture']['status']['elapsed'] else '0'
        league = match_data['league']['name']
        
        return f"⚽ **{home} vs {away}**\n🏆 {league} | Score: {score} | Minute: {minute}'\n"

    def get_live_insights(self, match_data):
        home_score = match_data['goals']['home']
        away_score = match_data['goals']['away']
        minute_str = match_data['fixture']['status']['elapsed']
        
        if minute_str: minute = int(minute_str)
        else: minute = 0

        total_goals = home_score + away_score
        
        if minute > 75 and total_goals <= 1:
            return "💡 **Insight:** High probability of late attacking substitutions. Defensive lines are thinning. Look for a late goal (80'+)."
        elif minute < 40 and total_goals == 0:
            return "💡 **Insight:** Low-scoring first half expected. Check for increased tempo right after half-time (45-60')."
        elif home_score == away_score and total_goals > 2:
            return "💡 **Insight:** Very balanced match, high chance of a late draw or a last-minute goal from the team with higher shots on target."
        else:
            return "💡 **Insight:** Standard match tempo. Focus on the next 15 minutes window for a likely score change."
            
    def generate_simple_score_based_prediction(self, match_data):
        home_score = match_data['goals']['home']
        away_score = match_data['goals']['away']
        minute_str = match_data['fixture']['status']['elapsed']
        
        if minute_str: minute = int(minute_str)
        else: minute = 0
        
        total_goals = home_score + away_score
        
        if minute >= 60:
            if home_score > away_score:
                return f"{match_data['teams']['home']['name']} is likely to win unless a late equalizer occurs. Focus on Under 3.5 goals."
            elif away_score > home_score:
                return f"{match_data['teams']['away']['name']} is holding the lead. Focus on Under 3.5 goals."
            elif total_goals >= 2:
                return "Very tight game! BTTS YES is highly probable."
        
        return "The game is open. Look for the next goal market."

match_analyzer = MatchAnalysis()

# --- Utility Functions (Same as V6) ---

def fetch_live_matches_http():
    global API_KEY
    if hit_counter.daily_hits >= 100:
        return api_manager.match_cache.get('today_matches', []), 'Cache'

    url = "https://v3.football.api-sports.io/fixtures"
    headers = {
        'x-apisports-key': API_KEY
    }
    params = {
        'status': 'LIVE-HT-ET-BT'
    }
    
    try:
        hit_counter.increment()
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data and data.get('response'):
            live_matches = data['response']
            cached_matches = api_manager.match_cache.get('today_matches', [])
            
            live_ids = {m['fixture']['id'] for m in live_matches}
            new_cache = [m for m in cached_matches if m['fixture']['id'] not in live_ids]
            new_cache.extend(live_matches)
            api_manager.match_cache['today_matches'] = new_cache
            api_manager.last_fetch_time = datetime.now(pytz.utc)
            api_manager.api_status = True
            
            return live_matches, 'API-Football HTTP'
        else:
            api_manager.api_status = True
            return [], 'API-Football HTTP'
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Live Fetch Error: {e}")
        api_manager.api_status = False
        return [m for m in api_manager.match_cache.get('today_matches', []) if m['fixture']['status']['short'] in ['LIVE', 'HT', 'ET', 'BT']], 'Cache (Error)'

def get_current_date_pakt():
    pkt_tz = pytz.timezone('Asia/Karachi')
    return datetime.now(pkt_tz).strftime('%d %b, %Y')

def process_match_data(raw_matches, live_only=False):
    processed = []
    
    for match in raw_matches:
        status = match['fixture']['status']['short']
        minute = match['fixture']['status']['elapsed']
        
        if live_only and status not in ['LIVE', 'HT', 'ET', 'BT']: continue
        if not live_only and status in ['FT', 'AET', 'PEN']: continue
        
        is_live = status in ['LIVE', 'HT', 'ET', 'BT']
        
        try:
            utc_dt = datetime.fromisoformat(match['fixture']['date'].replace('Z', '+00:00'))
            pkt_tz = pytz.timezone('Asia/Karachi')
            pkt_dt = utc_dt.astimezone(pkt_tz)
        except:
             # Handle invalid date format fallback
             pkt_dt = datetime.now(pytz.timezone('Asia/Karachi'))

        score_text = f"{match['goals']['home']}-{match['goals']['away']}" if is_live else pkt_dt.strftime('%H:%M PKT')
        icon = "🟢" if is_live else "🟠"
        
        processed.append({
            'league': match['league']['name'],
            'home_team': match['teams']['home']['name'],
            'away_team': match['teams']['away']['name'],
            'score': score_text,
            'status': status,
            'minute': minute if is_live else '0',
            'is_live': is_live,
            'source_icon': icon
        })
    return processed

# --- 3. EnhancedFootballAI Class (Logic is SAME as V6) ---

class EnhancedFootballAI:
    def __init__(self):
        self.team_data = {
            "manchester city": {"strength": 95, "style": "attacking", "goal_avg": 2.5},
            "liverpool": {"strength": 92, "style": "high press", "goal_avg": 2.2},
            "arsenal": {"strength": 90, "style": "possession", "goal_avg": 2.1},
            # ... other teams
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
        
        # --- Command Handling (Same as V6) ---
        if any(word in message_lower for word in ['live', 'current', 'scores', '/live']):
            return self.handle_live_matches()
        # ... (other handlers remain the same) ...
        elif any(word in message_lower for word in ['today', 'schedule', 'matches', 'list', '/today']):
            return self.handle_todays_matches() 
        elif any(word in message_lower for word in ['hit', 'counter', 'stats', 'api usage', '/hits', '/stats']):
            return hit_counter.get_hit_stats()
        elif any(word in message_lower for word in ['expert', 'confirmed', '/expert_bet']):
            return self.handle_expert_bet(message_lower)
        elif any(word in message_lower for word in ['analysis', 'analyze', 'detail', 'report', '/analysis']):
            return self.handle_detailed_analysis(message_lower)
        elif any(word in message_lower for word in ['api status', 'connection', 'status', '/status']):
            return self.handle_api_status()
        elif any(word in message_lower for word in ['hello', 'hi', 'hey', 'start', '/start']):
            return "👋 Hello! I'm **SUPER STABLE Football Analysis AI V7**! ⚽\n\n🔍 **Stable HTTP API Only**\n\nTry: `/live`, `/today`, `/analysis man city`, or `/expert_bet real madrid`."
        else:
            return self.handle_team_specific_query(message_lower)

    # --- Match Handlers (Same as V6) ---
    def handle_live_matches(self):
        raw_matches, source = fetch_live_matches_http()
        matches = process_match_data(raw_matches, live_only=True) 
        # ... (rest of the handle_live_matches function, same as V6) ...
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
                response += f"{match['source_icon']} {match['home_team']} {match['score']} {match['away_team']} {icon} {match['minute']}'\n"
            response += "\n"
        
        response += f"🔥 API Hits Today: {hit_counter.daily_hits}/100\n"
        response += self.get_api_status_text()
        
        return response

    def handle_todays_matches(self):
        raw_matches, _ = api_manager.fetch_api_football_matches(match_live_only=False)
        matches = process_match_data(raw_matches, live_only=False) 
        # ... (rest of the handle_todays_matches function, same as V6) ...
        if not matches:
            return f"📅 **{get_current_date_pakt()}**\n\n❌ No matches scheduled for today."
        
        live_matches = [m for m in matches if m['is_live']]
        upcoming_matches = [m for m in matches if not m['is_live']]
        
        response = f"📅 **TODAY'S FOOTBALL SCHEDULE ({get_current_date_pakt()})** ⚽\n\n"
        
        if live_matches:
            response += "--- **🔵 LIVE / FT MATCHES** ---\n"
            for match in live_matches[:5]:
                icon = "⏱️" if match['status'] == 'LIVE' else "🔄" if match['status'] == 'HALF TIME' else "🏁"
                response += f"{match['league']}\n{match['source_icon']} {match['home_team']} {match['score']} {match['away_team']} {icon} {match['minute']}'\n"
            response += "\n"
            
        if upcoming_matches:
            response += "--- **🕒 UPCOMING MATCHES (Pakistan Time)** ---\n"
            for match in upcoming_matches:
                response += f"📅 {match['league']}\n{match['home_team']} vs {match['away_team']} 🕒 {match['score']}\n"
            response += "\n"
            
        response += "💡 *Use '/analysis [Team Name]' for live match reports or '/expert_bet [Team Name]' for a confirmed bet.*"
        
        return response
        
    def handle_detailed_analysis(self, message):
        # ... (handle_detailed_analysis function, same as V6) ...
        teams_found = []
        for team_key in self.team_data:
            if team_key in message.lower(): teams_found.append(team_key)
        
        match_data = None
        if len(teams_found) >= 1:
            match_data = api_manager.find_match_by_teams(teams_found[0])
            
        if match_data:
            return self.generate_live_match_report(match_data)
        else:
            raw_matches, _ = fetch_live_matches_http()
            live_matches = [m for m in raw_matches if m['fixture']['status']['short'] in ['LIVE', 'HT', 'ET', 'BT']]

            if not live_matches:
                return "❌ No live matches available for analysis right now. Try `/today` for the schedule."
                
            response = "🔍 **DETAILED MATCH ANALYSIS SUMMARY**\n\n"
            for match in live_matches[:5]:
                analysis = match_analyzer.analyze_match_trends(match)
                home_team = match['teams']['home']['name']
                away_team = match['teams']['away']['name']
                score = f"{match['goals']['home']}-{match['goals']['away']}"
                minute = match['fixture']['status']['elapsed']
                
                response += f"**{home_team} vs {away_team}** ({minute}')\n"
                response += f"Score: {score} | Progress: {analysis.get('match_progress', 'N/A')}\n"
                response += f"Momentum: {analysis.get('momentum', 'N/A')}\n"
                response += f"Tempo: {analysis.get('match_tempo', 'N/A')}\n\n"
            
            response += "💡 *Use '/analysis [team name]' for a full match report*"
            return response

    def generate_live_match_report(self, match_data):
        # ... (generate_live_match_report function, same as V6) ...
        basic_info = match_analyzer.get_basic_match_info(match_data)
        analysis = match_analyzer.analyze_match_trends(match_data)
        statistics = match_analyzer.get_match_statistics(match_data)
        home_team = match_data['teams']['home']['name']
        away_team = match_data['teams']['away']['name']
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
    
    # --- Prediction Logic (Crucial Multi O/U Logic - SAME as V6) ---
    def _get_match_progress(self, minute):
        if minute == "HT": return 50.0
        if minute is None or not str(minute).isdigit(): return 0.0
        return min(90.0, float(minute))

    def _calculate_1x2_probability(self, match_data, team1, team2):
        # ... (Same calculation logic as V6) ...
        strength1, avg1 = self.get_team_strength_and_avg(team1)
        strength2, avg2 = self.get_team_strength_and_avg(team2)
        home_score = match_data['goals']['home']
        away_score = match_data['goals']['away']
        minute = match_data['fixture']['status']['elapsed']
        
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
        
    def _calculate_over_under_probability_all(self, match_data, team1, team2):
        """Calculates Over/Under probabilities for lines 0.5, 1.5, 2.5, 3.5, 4.5"""
        strength1, avg1 = self.get_team_strength_and_avg(team1)
        strength2, avg2 = self.get_team_strength_and_avg(team2)
        home_score = match_data['goals']['home']
        away_score = match_data['goals']['away']
        minute = match_data['fixture']['status']['elapsed']

        progress_percent = self._get_match_progress(minute) / 90
        
        expected_goals_full_time = (avg1 + avg2) * (1 - (0.5 - progress_percent) * 0.5)
        total_goals = home_score + away_score
        
        def poisson_prob_over(expected_lambda, current_goals, line_goal):
            goals_needed = int(line_goal + 0.5) 
            target_remaining_goals = max(0, goals_needed - current_goals)
            remaining_lambda = expected_lambda * (1 - progress_percent)
            
            if remaining_lambda <= 0.1 and target_remaining_goals > 0: return 1.0
            
            if current_goals >= goals_needed:
                if goals_needed == 0: return 99.0 
                return 95.0 + random.uniform(0, 4.9)

            if target_remaining_goals == 0:
                 return 99.0 + random.uniform(0, 0.9)

            if target_remaining_goals == 1:
                prob = 100 - (100 * (remaining_lambda / (remaining_lambda + 1)))
            elif target_remaining_goals > 1:
                prob = remaining_lambda ** target_remaining_goals * 10 
            else:
                prob = 50.0

            match_tempo_factor = total_goals / (expected_goals_full_time * progress_percent) if progress_percent > 0.1 else 1.0
            
            if goals_needed >= 3:
                prob *= max(0.8, min(1.3, match_tempo_factor))
                
            prob = max(1.0, min(99.0, prob))
            return prob

        all_probs = []
        for line in [0.5, 1.5, 2.5, 3.5, 4.5]:
            over_prob = poisson_prob_over(expected_goals_full_time, total_goals, line)
            under_prob = 100.0 - over_prob
            
            if over_prob >= under_prob:
                best_pred = f"Over {line} Goals"
                confidence = over_prob
            else:
                best_pred = f"Under {line} Goals"
                confidence = under_prob
                
            all_probs.append({
                "line": line,
                "over_prob": over_prob,
                "under_prob": under_prob,
                "best_pred": best_pred,
                "confidence": confidence
            })
            
        return all_probs

    def generate_combined_prediction(self, match_data, team1, team2, send_alert=False):
        minute = match_data['fixture']['status']['elapsed']
        
        if match_data['fixture']['status']['short'] in ['FT', 'AET', 'PEN']:
            return "🏁 Match is over. Final Score-based Prediction not applicable.", None
        
        prob1, prob2, draw_prob = self._calculate_1x2_probability(match_data, team1, team2)
        all_ou_probs = self._calculate_over_under_probability_all(match_data, team1, team2)
        best_ou_market = max(all_ou_probs, key=lambda x: x['confidence'])
        
        max_prob_1x2 = max(prob1, prob2, draw_prob)
        if max_prob_1x2 == prob1: winner = team1; market_1x2 = f"{team1} to WIN"
        elif max_prob_1x2 == prob2: winner = team2; market_1x2 = f"{team2} to WIN"
        else: winner = "DRAW"; market_1x2 = "DRAW"
            
        alert_to_send = None
        
        if send_alert and OWNER_CHAT_ID:
            if max(max_prob_1x2, best_ou_market['confidence']) >= 85: # Check for 1X2 or Best O/U for alert
                alert_to_send = {
                    "market": best_ou_market['best_pred'] if best_ou_market['confidence'] > max_prob_1x2 else market_1x2,
                    "prediction": best_ou_market['best_pred'] if best_ou_market['confidence'] > max_prob_1x2 else market_1x2,
                    "confidence": max(max_prob_1x2, best_ou_market['confidence'])
                }

        ou_report = "\n"
        for p in all_ou_probs:
            ou_report += f"• O/U {p['line']} Goals: {p['over_prob']:.1f}% / {p['under_prob']:.1f}% ({p['best_pred']} - {p['confidence']:.1f}%)\n"

        result = f"""
**Pre-match & Live Score Model:**
• {team1} WIN: {prob1:.1f}%
• {team2} WIN: {prob2:.1f}%  
• Draw: {draw_prob:.1f}%

**Detailed Goal Predictions:**
{ou_report}

🏆 **Current Verdict ({minute}' / {match_data['goals']['home']}-{match_data['goals']['away']}):**
• **Match Winner:** **{winner.upper()}** ({max_prob_1x2:.1f}%)
• **Goals (Best O/U):** **{best_ou_market['best_pred'].upper()}** ({best_ou_market['confidence']:.1f}%)

💡 **Score-based Insight:**
{match_analyzer.generate_simple_score_based_prediction(match_data)}
"""
        return result, alert_to_send

    def analyze_and_select_expert_bet(self, match_data, home_team, away_team):
        # ... (analyze_and_select_expert_bet function, same as V6) ...
        analysis = match_analyzer.analyze_match_trends(match_data)
        stats = match_analyzer.get_match_statistics_dict(match_data) 
        minute = match_data['fixture']['status']['elapsed']
        all_market_predictions = []
        
        # A. 1️⃣ Match Winner Probability (1X2)
        prob1, prob2, draw_prob = self._calculate_1x2_probability(match_data, home_team, away_team)
        max_prob_1x2 = max(prob1, prob2, draw_prob)
        winner_pred = f"{home_team} WIN" if max_prob_1x2 == prob1 else f"{away_team} WIN" if max_prob_1x2 == prob2 else "DRAW"
        all_market_predictions.append({"market": "Match Winner (1X2)", "prediction": winner_pred, "confidence": max_prob_1x2, "reason": "Live Score Adjustment applied.", "odds_range": "1.40-3.00"})

        # B. 2️⃣ Multi Over/Under Goals (0.5, 1.5, 2.5, 3.5, 4.5)
        all_ou_probs = self._calculate_over_under_probability_all(match_data, home_team, away_team)
        best_ou_market = max(all_ou_probs, key=lambda x: x['confidence'])
        all_market_predictions.append({
            "market": f"Goals ({best_ou_market['line']})",
            "prediction": best_ou_market['best_pred'],
            "confidence": best_ou_market['confidence'],
            "reason": f"Best O/U found at line {best_ou_market['line']} based on live tempo.",
            "odds_range": "1.40-2.20"
        })
        
        # C. 3️⃣ BTTS 
        base_btts_prob = 50 + ((self.get_team_strength_and_avg(home_team)[0] + self.get_team_strength_and_avg(away_team)[0]) / 20) * 0.5 
        if (match_data['goals']['home'] + match_data['goals']['away']) >= 2 and analysis['goal_difference'] < 2: live_btts_factor = 1.25 
        elif stats.get("Shots on Goal", 0) > 8: live_btts_factor = 1.15
        else: live_btts_factor = 0.95
        
        btts_prob = min(99, base_btts_prob * live_btts_factor)
        btts_pred = "Yes (BTTS)" if btts_prob >= 50 else "No (BTTS)"
        btts_conf = btts_prob if btts_prob >= 50 else 100 - btts_prob
        all_market_predictions.append({"market": "Both Teams To Score (BTTS)", "prediction": btts_pred, "confidence": btts_conf, "reason": f"Live total shots on goal: {stats.get('Shots on Goal', 0)}.", "odds_range": "1.75-2.00"})
        
        # D. 4️⃣ Last 10 Minute Goal Chance
        progress = self._get_match_progress(minute)
        if progress < 80: late_goal_prob = 50.0
        else:
            base = 65.0
            score_diff = abs(match_data['goals']['home'] - match_data['goals']['away'])
            total_goals = match_data['goals']['home'] + match_data['goals']['away']
            if score_diff <= 1 and total_goals >= 2: base += 15
            elif score_diff >= 3: base -= 10
            late_goal_prob = min(95, base + random.uniform(-5, 5))
            
        all_market_predictions.append({"market": "Goal in Last 10 Minutes (80'+)", "prediction": "Yes", "confidence": late_goal_prob, "reason": f"Match is in {minute}' ({progress:.1f}%).", "odds_range": "1.45-1.75"})
        
        # E. F. Goal Minutes and Correct Score Mock (Internal methods)
        top_2_scores = self._predict_correct_score(match_data, home_team, away_team)
        goal_minutes = self._predict_goal_minutes(match_data)
        
        # 3. SELECT THE BEST BET (85%+ CONFIDENCE ONLY)
        best_bet = None
        high_confidence_bets = sorted(
            [p for p in all_market_predictions if p['confidence'] >= 85.0],
            key=lambda x: x['confidence'], reverse=True
        )
        
        if high_confidence_bets: best_bet = high_confidence_bets[0]
        
        # 4. Final Output Generation
        ou_details_report = "📊 **Detailed O/U Probabilities:**\n"
        for p in all_ou_probs:
            ou_details_report += f"• O/U {p['line']}: {p['over_prob']:.1f}% / {p['under_prob']:.1f}% (Best: {p['best_pred']} @ {p['confidence']:.1f}%)\n"

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
2. **BTTS (Yes/No):** Yes {btts_prob:.1f}% | No {(100 - btts_prob):.1f}%
4. **Late Goal (80'+):** Yes {late_goal_prob:.1f}% | No {(100 - late_goal_prob):.1f}%
{ou_details_report}

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

**Reason:** No single market (1X2, Goals, BTTS, Late Goal) currently meets the 85.0% confidence threshold.

**Highest Confidence Found:**
• Market: {all_market_predictions[0]['market']}
• Prediction: {all_market_predictions[0]['prediction']}
• Confidence: {all_market_predictions[0]['confidence']:.1f}%
---
{ou_details_report}

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
        
        if match_data['fixture']['status']['short'] in ['FT', 'AET', 'PEN']: return "❌ یہ میچ ختم ہو چکا ہے۔ Expert Bet صرف لائیو میچز پر دستیاب ہے۔"
        
        home_team = match_data['teams']['home']['name']
        away_team = match_data['teams']['away']['name']
        
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

    def handle_api_status(self):
        return api_manager.get_api_status_text()
        
    def get_api_status_text(self):
        return api_manager.get_api_status_text()

# Instantiate the AI
ai_assistant = EnhancedFootballAI()

# --- 4. Auto-Update/Alert Thread ---

def auto_updater_thread():
    """Fetches data regularly to keep the cache fresh and container awake."""
    logger.info("🚀 Auto-Updater thread started.")
    while True:
        try:
            # 1. Fetch data to keep cache fresh
            api_manager.fetch_api_football_matches(match_live_only=False)
            
            # 2. Alert logic (only runs 30% of the time to save API hits)
            if random.random() < 0.3:
                live_matches, _ = fetch_live_matches_http()
                
                for match in live_matches:
                    minute = match['fixture']['status']['elapsed']
                    if minute and int(minute) < 80:
                        home_team = match['teams']['home']['name']
                        away_team = match['teams']['away']['name']
                        
                        _, alert = ai_assistant.generate_combined_prediction(match, home_team, away_team, send_alert=True)
                        
                        if alert and OWNER_CHAT_ID:
                            alert_message = f"""
🚨 **LIVE ALERT: HIGH CONFIDENCE BET** 🚨
⚽ **Match:** {home_team} vs {away_team} ({minute}')
🎯 **Prediction:** **{alert['prediction']}**
💰 **Confidence:** **{alert['confidence']:.1f}%**
"""
                            try:
                                bot.send_message(OWNER_CHAT_ID, alert_message, parse_mode='Markdown')
                                logger.info(f"Alert sent for: {home_team} vs {away_team}")
                            except Exception as e:
                                logger.error(f"Error sending alert to owner: {e}")
                                    
        except Exception as e:
            logger.error(f"Auto-updater error: {e}")
        
        time.sleep(120) # Wait for 120 seconds (2 minutes)

# Start the auto-updater thread as soon as possible
updater_thread = threading.Thread(target=auto_updater_thread, daemon=True)
updater_thread.start()

# --- 5. Telegram Webhook Handlers ---

@app.before_request
def check_webhook_and_set():
    """Sets the webhook on the first request if it hasn't been set."""
    if not hasattr(check_webhook_and_set, 'webhook_set') or not check_webhook_and_set.webhook_set:
        try:
            # Try to remove old webhook first to avoid 409 Conflict
            bot.remove_webhook()
            
            # Set the new webhook
            s = bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
            if s:
                logger.info(f"✅ Webhook successfully set to: {WEBHOOK_URL}/{BOT_TOKEN}")
                check_webhook_and_set.webhook_set = True
            else:
                logger.error("❌ Webhook setup failed.")
        except Exception as e:
             logger.error(f"Webhook setup failed during before_request: {e}")

@app.route('/', methods=['GET'])
def index():
    # Simple endpoint to check if the app is alive
    return "Football Analysis Bot V7 is Running! Webhook Ready.", 200

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    """Webhook endpoint for Telegram updates."""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        
        if update.message:
            try:
                message_text = update.message.text
                chat_id = update.message.chat.id
                
                logger.info(f"Received message from {chat_id}: {message_text}")
                
                response_text = ai_assistant.get_response(message_text)
                
                # Send the response back
                bot.send_message(chat_id, response_text, parse_mode='Markdown')
                
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                bot.send_message(chat_id, "❌ **Error processing your request.** Please try a command like /live or /today.", parse_mode='Markdown')
                
        return 'OK', 200
    else:
        abort(403)

# --- 6. Startup ---
# We rely entirely on Gunicorn for starting the application.
# If you run this file directly for local testing, Gunicorn must be installed.
if __name__ == '__main__':
    # Local Test Run with Gunicorn (Requires gunicorn in requirements.txt)
    logger.info("Starting local Gunicorn server. For production, use 'gunicorn main:app'")
    # This runs the app locally if you execute 'python main.py'
    try:
        from gunicorn.app.wsgiapp import WSGIApplication
        
        class CustomWSGIApplication(WSGIApplication):
            def __init__(self, app_uri, options=None):
                self.options = options or {}
                super().__init__(app_uri)

            def load_config(self):
                config = {key: value for key, value in self.options.items()
                          if key in self.cfg.settings and value is not None}
                for key, value in config.items():
                    self.cfg.set(key.lower(), value)

        gunicorn_options = {
            'bind': f'0.0.0.0:{os.environ.get("PORT", 5000)}',
            'workers': 4, 
            'timeout': 60,
        }

        CustomWSGIApplication('main:app', gunicorn_options).run()
    except ImportError:
        logger.error("Gunicorn not installed. Please run: pip install gunicorn")
        app.run(host='0.0.0.0', port=os.environ.get("PORT", 5000))
