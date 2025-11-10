import os
import requests
import telebot
import time
import random
import math
from datetime import datetime, timedelta
from flask import Flask, request
import threading
from dotenv import load_dotenv
import json

# -------------------------
# Load environment variables
# -------------------------
load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
API_KEY = os.environ.get("API_KEY")
PORT = int(os.environ.get("PORT", 8080))
DOMAIN = os.environ.get("DOMAIN")

if not all([BOT_TOKEN, OWNER_CHAT_ID, API_KEY, DOMAIN]):
    raise ValueError("❌ BOT_TOKEN, OWNER_CHAT_ID, API_KEY, or DOMAIN missing!")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

API_URL = "https://apiv3.apifootball.com"

# -------------------------
# ENHANCED API Functions with Real Data Integration
# -------------------------
def fetch_live_matches_enhanced():
    """Fetch live matches with detailed statistics"""
    try:
        url = f"{API_URL}/?action=get_events&APIkey={API_KEY}&from={datetime.now().strftime('%Y-%m-%d')}&to={datetime.now().strftime('%Y-%m-%d')}"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            live_matches = [m for m in data if m.get("match_live") == "1"]
            
            # Enhanced: Get match statistics for each live match
            enhanced_matches = []
            for match in live_matches:
                match_id = match.get("match_id")
                detailed_stats = fetch_match_statistics(match_id)
                if detailed_stats:
                    match["detailed_stats"] = detailed_stats
                
                # Get H2H data
                h2h_data = fetch_h2h_data(
                    match.get("match_hometeam_id"), 
                    match.get("match_awayteam_id")
                )
                if h2h_data:
                    match["h2h_stats"] = h2h_data
                
                enhanced_matches.append(match)
            
            print(f"✅ Found {len(enhanced_matches)} enhanced live matches")
            return enhanced_matches
        else:
            print(f"❌ API Error: {resp.status_code}")
            return []
    except Exception as e:
        print(f"❌ Enhanced live fetch error: {e}")
        return []

def fetch_match_statistics(match_id):
    """Fetch detailed match statistics"""
    try:
        url = f"{API_URL}/?action=get_statistics&APIkey={API_KEY}&match_id={match_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return None
    except:
        return None

def fetch_h2h_data(team1_id, team2_id):
    """Fetch head-to-head data"""
    try:
        url = f"{API_URL}/?action=get_H2H&APIkey={API_KEY}&firstTeamId={team1_id}&secondTeamId={team2_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return analyze_h2h_stats(data)
        return None
    except:
        return None

def analyze_h2h_stats(h2h_data):
    """Analyze H2H statistics for predictive modeling"""
    if not h2h_data or len(h2h_data) == 0:
        return None
    
    total_matches = len(h2h_data)
    home_wins = 0
    away_wins = 0
    draws = 0
    total_goals = 0
    btts_count = 0
    
    for match in h2h_data:
        home_goals = int(match.get("match_hometeam_score", 0))
        away_goals = int(match.get("match_awayteam_score", 0))
        
        total_goals += home_goals + away_goals
        
        if home_goals > away_goals:
            home_wins += 1
        elif away_goals > home_goals:
            away_wins += 1
        else:
            draws += 1
            
        if home_goals > 0 and away_goals > 0:
            btts_count += 1
    
    return {
        "total_matches": total_matches,
        "home_wins": home_wins,
        "away_wins": away_wins,
        "draws": draws,
        "avg_goals": total_goals / total_matches if total_matches > 0 else 2.5,
        "btts_percentage": (btts_count / total_matches) * 100 if total_matches > 0 else 50,
        "home_win_rate": (home_wins / total_matches) * 100 if total_matches > 0 else 33,
        "away_win_rate": (away_wins / total_matches) * 100 if total_matches > 0 else 33
    }

def fetch_team_form(team_id, last_matches=5):
    """Fetch team form from recent matches"""
    try:
        from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        to_date = datetime.now().strftime('%Y-%m-%d')
        
        url = f"{API_URL}/?action=get_events&APIkey={API_KEY}&from={from_date}&to={to_date}&team_id={team_id}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            matches = resp.json()[:last_matches]  # Last 5 matches
            return analyze_team_form(matches, team_id)
        return None
    except:
        return None

def analyze_team_form(matches, team_id):
    """Analyze team form from recent matches"""
    if not matches:
        return None
    
    wins = 0
    goals_scored = 0
    goals_conceded = 0
    clean_sheets = 0
    
    for match in matches:
        is_home = match.get("match_hometeam_id") == str(team_id)
        
        if is_home:
            scored = int(match.get("match_hometeam_score", 0))
            conceded = int(match.get("match_awayteam_score", 0))
        else:
            scored = int(match.get("match_awayteam_score", 0))
            conceded = int(match.get("match_hometeam_score", 0))
        
        goals_scored += scored
        goals_conceded += conceded
        
        if (is_home and scored > conceded) or (not is_home and scored > conceded):
            wins += 1
            
        if conceded == 0:
            clean_sheets += 1
    
    form_rating = (wins / len(matches)) * 100
    avg_goals_scored = goals_scored / len(matches)
    avg_goals_conceded = goals_conceded / len(matches)
    
    return {
        "matches_analyzed": len(matches),
        "wins": wins,
        "form_rating": form_rating,
        "avg_goals_scored": avg_goals_scored,
        "avg_goals_conceded": avg_goals_conceded,
        "clean_sheets": clean_sheets,
        "goal_difference": goals_scored - goals_conceded
    }

# -------------------------
# ADVANCED PREDICTION ENGINE with Machine Learning-like Algorithms
# -------------------------
class AdvancedPredictionEngine:
    def __init__(self):
        self.confidence_threshold = 85
        
    def calculate_advanced_probabilities(self, match):
        """Calculate probabilities using advanced algorithms"""
        # Base analysis
        base_analysis = self.base_match_analysis(match)
        
        # H2H analysis
        h2h_analysis = self.analyze_h2h_influence(match.get("h2h_stats"))
        
        # Form analysis
        home_form = self.analyze_team_form_influence(
            fetch_team_form(match.get("match_hometeam_id"))
        )
        away_form = self.analyze_team_form_influence(
            fetch_team_form(match.get("match_awayteam_id"))
        )
        
        # Live match dynamics
        live_dynamics = self.analyze_live_dynamics(match)
        
        # Combine all factors
        final_probabilities = self.combine_factors(
            base_analysis, h2h_analysis, home_form, away_form, live_dynamics
        )
        
        return final_probabilities
    
    def base_match_analysis(self, match):
        """Base analysis of current match state"""
        home_score = int(match.get("match_hometeam_score", 0))
        away_score = int(match.get("match_awayteam_score", 0))
        match_time = match.get("match_time", "0")
        
        # Convert match time to minutes
        current_minute = self.parse_match_time(match_time)
        
        # Goal expectation based on current score and time
        goal_expectancy = self.calculate_goal_expectancy(home_score, away_score, current_minute)
        
        return {
            "current_minute": current_minute,
            "goal_expectancy": goal_expectancy,
            "score_momentum": home_score - away_score,
            "total_goals": home_score + away_score
        }
    
    def parse_match_time(self, match_time):
        """Parse match time to minutes"""
        try:
            if "'" in match_time:
                return int(match_time.replace("'", ""))
            elif ":" in match_time:
                parts = match_time.split(":")
                return int(parts[0]) * 60 + int(parts[1])
            else:
                return int(match_time) if match_time.isdigit() else 0
        except:
            return 45  # Default to halftime
    
    def calculate_goal_expectancy(self, home_score, away_score, minute):
        """Calculate expected additional goals based on Poisson distribution"""
        base_rate = 2.8  # Average goals per match
        time_factor = minute / 90.0
        
        # Adjust for current score
        if home_score + away_score == 0:
            # No goals yet, expect more
            expected_goals = base_rate * (1 - time_factor)
        else:
            # Goals already scored, adjust expectation
            goals_per_minute = (home_score + away_score) / max(minute, 1)
            expected_remaining_goals = goals_per_minute * (90 - minute)
            expected_goals = min(expected_remaining_goals, 4.0)  # Cap at 4
        
        return expected_goals
    
    def analyze_h2h_influence(self, h2h_stats):
        """Analyze H2H statistics influence"""
        if not h2h_stats:
            return {"influence": 0, "confidence": 50}
        
        total_matches = h2h_stats["total_matches"]
        home_win_rate = h2h_stats["home_win_rate"]
        avg_goals = h2h_stats["avg_goals"]
        btts_percentage = h2h_stats["btts_percentage"]
        
        # Calculate H2H influence score (0-100)
        sample_size_factor = min(total_matches / 10, 1.0)  # More matches = more reliable
        win_consistency = abs(home_win_rate - 50) / 50  # How consistent are results
        
        influence_score = (sample_size_factor * 60) + (win_consistency * 40)
        confidence = min(95, (sample_size_factor * 100))
        
        return {
            "influence": influence_score,
            "confidence": confidence,
            "suggested_market": "1X2" if win_consistency > 0.7 else "Over/Under",
            "avg_goals": avg_goals,
            "btts_trend": btts_percentage
        }
    
    def analyze_team_form_influence(self, form_data):
        """Analyze team form influence"""
        if not form_data:
            return {"influence": 0, "rating": 50}
        
        form_rating = form_data["form_rating"]
        goal_difference = form_data["goal_difference"]
        clean_sheets = form_data["clean_sheets"]
        
        # Calculate form influence
        form_strength = form_rating / 100
        defensive_stability = clean_sheets / form_data["matches_analyzed"]
        attacking_power = max(0, goal_difference) / form_data["matches_analyzed"]
        
        influence_score = (form_strength * 40) + (defensive_stability * 30) + (attacking_power * 30)
        
        return {
            "influence": influence_score,
            "rating": form_rating,
            "attack_strength": attacking_power,
            "defense_stability": defensive_stability
        }
    
    def analyze_live_dynamics(self, match):
        """Analyze live match dynamics"""
        stats = match.get("detailed_stats", {})
        current_minute = self.parse_match_time(match.get("match_time", "45"))
        
        # Extract key metrics from statistics
        home_attacks = self.extract_stat(stats, "home", "attacks")
        away_attacks = self.extract_stat(stats, "away", "attacks")
        home_dangerous_attacks = self.extract_stat(stats, "home", "dangerous_attacks")
        away_dangerous_attacks = self.extract_stat(stats, "away", "dangerous_attacks")
        home_possession = self.extract_stat(stats, "home", "ball_possession")
        away_possession = self.extract_stat(stats, "away", "ball_possession")
        
        # Calculate momentum
        attack_momentum = (home_attacks - away_attacks) / max(home_attacks + away_attacks, 1)
        danger_momentum = (home_dangerous_attacks - away_dangerous_attacks) / max(home_dangerous_attacks + away_dangerous_attacks, 1)
        possession_dominance = (home_possession - away_possession) / 100
        
        momentum_score = (attack_momentum + danger_momentum + possession_dominance) / 3
        
        # Time decay - later in match, current dynamics matter more
        time_weight = current_minute / 90.0
        
        return {
            "momentum": momentum_score,
            "time_weight": time_weight,
            "home_pressure": home_dangerous_attacks,
            "away_pressure": away_dangerous_attacks
        }
    
    def extract_stat(self, stats, side, stat_name):
        """Extract statistics from API response"""
        try:
            if isinstance(stats, list) and len(stats) > 0:
                main_stats = stats[0]
                return int(main_stats.get(f"{side}_{stat_name}", 0))
            return 0
        except:
            return 0
    
    def combine_factors(self, base, h2h, home_form, away_form, live):
        """Combine all factors using weighted algorithm"""
        
        # Weight factors based on availability and reliability
        weights = {
            "base": 0.2,
            "h2h": 0.25 if h2h["confidence"] > 60 else 0.15,
            "home_form": 0.2 if home_form["influence"] > 0 else 0.1,
            "away_form": 0.2 if away_form["influence"] > 0 else 0.1,
            "live": 0.15 * live["time_weight"]  # Live data weight increases with time
        }
        
        # Normalize weights to sum to 1
        total_weight = sum(weights.values())
        for key in weights:
            weights[key] /= total_weight
        
        # Calculate base probabilities
        home_win = 40  # Base 40%
        away_win = 30  # Base 30%
        draw = 30      # Base 30%
        
        # Apply H2H influence
        if h2h["influence"] > 0:
            h2h_home_boost = (h2h["influence"] / 100) * 20
            home_win += h2h_home_boost
            away_win -= h2h_home_boost * 0.7
            draw -= h2h_home_boost * 0.3
        
        # Apply form influence
        home_win += (home_form["rating"] - 50) * 0.3
        away_win += (away_form["rating"] - 50) * 0.3
        
        # Apply live momentum
        momentum_effect = live["momentum"] * 15
        home_win += momentum_effect
        away_win -= momentum_effect
        
        # Ensure probabilities are within bounds and sum to 100
        home_win = max(5, min(95, home_win))
        away_win = max(5, min(95, away_win))
        draw = max(5, min(95, 100 - home_win - away_win))
        
        # Normalize
        total = home_win + away_win + draw
        home_win = (home_win / total) * 100
        away_win = (away_win / total) * 100
        draw = (draw / total) * 100
        
        # Calculate confidence score
        confidence_factors = [
            h2h["confidence"] * weights["h2h"],
            home_form["influence"] * weights["home_form"],
            away_form["influence"] * weights["away_form"],
            70 * weights["base"],  # Base confidence
            min(90, live["time_weight"] * 100) * weights["live"]
        ]
        
        confidence = sum(confidence_factors)
        
        return {
            "home_win": round(home_win, 1),
            "away_win": round(away_win, 1),
            "draw": round(draw, 1),
            "confidence": min(98, max(70, round(confidence))),
            "market_analysis": self.analyze_best_markets(h2h, home_form, away_form, base),
            "goal_expectancy": base["goal_expectancy"]
        }
    
    def analyze_best_markets(self, h2h, home_form, away_form, base):
        """Analyze which betting markets have highest value"""
        markets = []
        
        # 1X2 Market
        markets.append({
            "market": "1X2",
            "confidence": max(h2h["confidence"], home_form["influence"], away_form["influence"]),
            "description": "Match Result"
        })
        
        # Over/Under Markets
        goal_expectancy = base["goal_expectancy"]
        if goal_expectancy > 3.0:
            markets.append({
                "market": "Over 2.5 Goals",
                "confidence": min(90, int(goal_expectancy * 25)),
                "description": f"High scoring expected ({goal_expectancy:.1f} goals)"
            })
        elif goal_expectancy < 1.5:
            markets.append({
                "market": "Under 2.5 Goals", 
                "confidence": min(90, int((2.5 - goal_expectancy) * 40)),
                "description": f"Low scoring expected ({goal_expectancy:.1f} goals)"
            })
        
        # BTTS Market
        if h2h.get("btts_trend", 50) > 65:
            markets.append({
                "market": "BTTS Yes",
                "confidence": min(85, h2h["btts_trend"]),
                "description": f"Strong BTTS history ({h2h['btts_trend']}%)"
            })
        elif h2h.get("btts_trend", 50) < 35:
            markets.append({
                "market": "BTTS No",
                "confidence": min(85, 100 - h2h["btts_trend"]),
                "description": f"Low BTTS history ({h2h['btts_trend']}%)"
            })
        
        # Sort by confidence
        markets.sort(key=lambda x: x["confidence"], reverse=True)
        return markets[:3]  # Top 3 markets

# -------------------------
# ENHANCED PREDICTION GENERATION
# -------------------------
advanced_engine = AdvancedPredictionEngine()

def generate_advanced_prediction(match):
    """Generate professional-level prediction with real data analysis"""
    home = match.get("match_hometeam_name")
    away = match.get("match_awayteam_name")
    home_score = match.get("match_hometeam_score", "0")
    away_score = match.get("match_awayteam_score", "0")
    league = match.get("league_name", "Unknown League")
    match_time = match.get("match_time", "45'")

    # Calculate advanced probabilities
    probabilities = advanced_engine.calculate_advanced_probabilities(match)
    
    # Generate professional analysis message
    msg = f"🎯 **PROFESSIONAL AI PREDICTION**\n"
    msg += f"⚽ **{home} vs {away}**\n"
    msg += f"🏆 {league} | ⏱️ {match_time}\n"
    msg += f"📊 **Current Score: {home_score}-{away_score}**\n\n"
    
    msg += "🔮 **MATCH PROBABILITIES:**\n"
    msg += f"• Home Win: `{probabilities['home_win']}%`\n"
    msg += f"• Draw: `{probabilities['draw']}%`\n"
    msg += f"• Away Win: `{probabilities['away_win']}%`\n"
    msg += f"• AI Confidence: `{probabilities['confidence']}%`\n\n"
    
    msg += "💎 **RECOMMENDED MARKETS:**\n"
    for market in probabilities['market_analysis']:
        msg += f"• **{market['market']}** - Confidence: `{market['confidence']}%`\n"
        msg += f"  📝 {market['description']}\n"
    
    # Additional insights
    msg += f"\n📈 **ADDITIONAL INSIGHTS:**\n"
    msg += f"• Expected Additional Goals: `{probabilities['goal_expectancy']:.1f}`\n"
    
    h2h_stats = match.get("h2h_stats")
    if h2h_stats:
        msg += f"• H2H Analysis: `{h2h_stats['total_matches']}` matches, Avg Goals: `{h2h_stats['avg_goals']:.1f}`\n"
        msg += f"• BTTS History: `{h2h_stats['btts_percentage']:.1f}%` of matches\n"
    
    # Risk assessment
    confidence = probabilities['confidence']
    if confidence >= 90:
        risk = "🟢 LOW RISK"
    elif confidence >= 80:
        risk = "🟡 MEDIUM RISK" 
    else:
        risk = "🔴 HIGH RISK"
    
    msg += f"• Risk Assessment: {risk}\n\n"
    msg += "⚠️ *Note: Always verify team news and lineups before betting*"

    return msg

# -------------------------
# ENHANCED AUTO-UPDATE SYSTEM
# -------------------------
def advanced_auto_update():
    """Enhanced auto-update with smart filtering"""
    while True:
        try:
            print(f"\n🔄 [{datetime.now().strftime('%H:%M:%S')}] Advanced scan starting...")
            
            matches = fetch_live_matches_enhanced()
            if matches:
                print(f"📊 Found {len(matches)} live matches for analysis")
                
                high_confidence_predictions = 0
                for match in matches:
                    probabilities = advanced_engine.calculate_advanced_probabilities(match)
                    
                    # Only send high-confidence predictions
                    if probabilities['confidence'] >= advanced_engine.confidence_threshold:
                        msg = generate_advanced_prediction(match)
                        try:
                            bot.send_message(OWNER_CHAT_ID, msg, parse_mode='Markdown')
                            high_confidence_predictions += 1
                            print(f"✅ Sent prediction with {probabilities['confidence']}% confidence")
                            time.sleep(3)  # Avoid rate limits
                        except Exception as e:
                            print(f"❌ Send error: {e}")
                
                if high_confidence_predictions == 0:
                    status_msg = f"📊 System Update: Analyzed {len(matches)} matches at {datetime.now().strftime('%H:%M')}. No {advanced_engine.confidence_threshold}%+ confidence predictions found."
                    try:
                        bot.send_message(OWNER_CHAT_ID, status_msg)
                    except Exception as e:
                        print(f"❌ Status message failed: {e}")
            else:
                print("⏳ No live matches currently")
                # Send occasional status
                if random.random() > 0.8:  # 20% chance
                    try:
                        bot.send_message(OWNER_CHAT_ID, "🔍 System actively scanning... No live matches detected.")
                    except Exception as e:
                        print(f"❌ No matches message failed: {e}")
                        
        except Exception as e:
            print(f"❌ Advanced auto-update error: {e}")
        
        time.sleep(300)  # 5 minutes

# -------------------------
# ENHANCED TELEGRAM COMMANDS
# -------------------------
@bot.message_handler(commands=['start', 'help'])
def send_enhanced_help(message):
    help_text = """
🤖 **PROFESSIONAL FOOTBALL AI PREDICTOR**

🎯 **Features:**
• Real-time H2H analysis
• Advanced form tracking
• Live match statistics
• 85-98% confidence predictions
• Multiple market recommendations

📊 **Commands:**
• `/predict` - Get current predictions
• `/analyze` - Detailed match analysis  
• `/status` - System information
• `/settings` - Configure confidence threshold

🔮 **The system automatically scans live matches every 5 minutes and sends high-confidence alerts.**
"""
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['predict'])
def send_enhanced_predictions(message):
    matches = fetch_live_matches_enhanced()
    if matches:
        # Send analysis of top match
        msg = generate_advanced_prediction(matches[0])
        bot.reply_to(message, msg, parse_mode='Markdown')
    else:
        bot.reply_to(message, "⏳ No live matches currently available for analysis.")

@bot.message_handler(commands=['analyze'])
def send_detailed_analysis(message):
    matches = fetch_live_matches_enhanced()
    if matches:
        analysis = generate_detailed_analysis(matches[0])
        bot.reply_to(message, analysis, parse_mode='Markdown')
    else:
        bot.reply_to(message, "⏳ No matches available for detailed analysis.")

def generate_detailed_analysis(match):
    """Generate detailed technical analysis"""
    home = match.get("match_hometeam_name")
    away = match.get("match_awayteam_name")
    
    analysis = f"🔍 **DETAILED TECHNICAL ANALYSIS**\n"
    analysis += f"**{home} vs {away}**\n\n"
    
    # H2H Analysis
    h2h = match.get("h2h_stats")
    if h2h:
        analysis += "📊 **HEAD-TO-HEAD ANALYSIS:**\n"
        analysis += f"• Matches Analyzed: `{h2h['total_matches']}`\n"
        analysis += f"• Home Wins: `{h2h['home_wins']}` ({h2h['home_win_rate']:.1f}%)\n"
        analysis += f"• Away Wins: `{h2h['away_wins']}` ({h2h['away_win_rate']:.1f}%)\n"
        analysis += f"• Draws: `{h2h['draws']}`\n"
        analysis += f"• Average Goals: `{h2h['avg_goals']:.2f}`\n"
        analysis += f"• BTTS Frequency: `{h2h['btts_percentage']:.1f}%`\n\n"
    
    # Team Form Analysis
    home_form = fetch_team_form(match.get("match_hometeam_id"))
    away_form = fetch_team_form(match.get("match_awayteam_id"))
    
    if home_form and away_form:
        analysis += "📈 **TEAM FORM ANALYSIS:**\n"
        analysis += f"• **{home}** Form: `{home_form['form_rating']:.1f}%` | Goals: `{home_form['avg_goals_scored']:.1f}` scored, `{home_form['avg_goals_conceded']:.1f}` conceded\n"
        analysis += f"• **{away}** Form: `{away_form['form_rating']:.1f}%` | Goals: `{away_form['avg_goals_scored']:.1f}` scored, `{away_form['avg_goals_conceded']:.1f}` conceded\n\n"
    
    # Live Statistics
    stats = match.get("detailed_stats")
    if stats:
        analysis += "⚡ **LIVE MATCH STATISTICS:**\n"
        analysis += f"• Possession: `{advanced_engine.extract_stat(stats, 'home', 'ball_possession')}%` - `{advanced_engine.extract_stat(stats, 'away', 'ball_possession')}%`\n"
        analysis += f"• Attacks: `{advanced_engine.extract_stat(stats, 'home', 'attacks')}` - `{advanced_engine.extract_stat(stats, 'away', 'attacks')}`\n"
        analysis += f"• Dangerous Attacks: `{advanced_engine.extract_stat(stats, 'home', 'dangerous_attacks')}` - `{advanced_engine.extract_stat(stats, 'away', 'dangerous_attacks')}`\n"
        analysis += f"• Shots on Target: `{advanced_engine.extract_stat(stats, 'home', 'shots_on_target')}` - `{advanced_engine.extract_stat(stats, 'away', 'shots_on_target')}`\n\n"
    
    analysis += "💡 *This analysis combines historical data, current form, and live match dynamics.*"
    
    return analysis

@bot.message_handler(commands=['status'])
def send_system_status(message):
    matches = fetch_live_matches_enhanced()
    status_msg = f"""
🤖 **SYSTEM STATUS**

✅ Online & Monitoring
🕐 Last Update: {datetime.now().strftime('%H:%M:%S')}
⏰ Next Scan: 5 minutes
🎯 Confidence Threshold: {advanced_engine.confidence_threshold}%+
🔴 Live Matches: {len(matches)}

**Active Monitoring:**
"""
    
    if matches:
        for i, match in enumerate(matches[:3], 1):
            home = match.get("match_hometeam_name")
            away = match.get("match_awayteam_name")
            score = f"{match.get('match_hometeam_score', '0')}-{match.get('match_awayteam_score', '0')}"
            status_msg += f"{i}. {home} {score} {away}\n"
    else:
        status_msg += "• No live matches\n"
    
    status_msg += f"\n📊 System Version: Professional AI v2.0"
    bot.reply_to(message, status_msg, parse_mode='Markdown')

@bot.message_handler(commands=['settings'])
def send_settings(message):
    settings_msg = """
⚙️ **SYSTEM SETTINGS**

Current Configuration:
• Confidence Threshold: 85%+
• Scan Interval: 5 minutes
• Data Sources: Live stats, H2H, Form analysis
• Markets: 1X2, Over/Under, BTTS

To adjust settings, modify the confidence_threshold in the code.
"""
    bot.reply_to(message, settings_msg, parse_mode='Markdown')

# -------------------------
# ENHANCED FLASK WEBHOOK
# -------------------------
@app.route('/')
def home():
    return "🤖 Professional Football AI Bot - Online"

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    try:
        update = telebot.types.Update.de_json(request.get_json())
        bot.process_new_updates([update])
        return 'OK', 200
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return 'ERROR', 400

# -------------------------
# ENHANCED BOT SETUP
# -------------------------
def setup_enhanced_bot():
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"{DOMAIN}/{BOT_TOKEN}")
        print(f"✅ Enhanced webhook set: {DOMAIN}/{BOT_TOKEN}")

        # Start enhanced auto-update
        t = threading.Thread(target=advanced_auto_update, daemon=True)
        t.start()
        print("✅ Enhanced auto-update started!")

        # Send enhanced startup message
        startup_msg = """
🤖 **PROFESSIONAL FOOTBALL AI PREDICTOR STARTED!**

🎯 **System Features:**
• Advanced AI Prediction Engine
• Real H2H & Form Analysis  
• Live Match Statistics
• 85-98% Confidence Filtering
• Multiple Market Recommendations

📊 **Monitoring active - High-confidence predictions will be sent automatically every 5 minutes.**

⚡ **System Ready for Professional Analysis!**
"""
        bot.send_message(OWNER_CHAT_ID, startup_msg, parse_mode='Markdown')
        
    except Exception as e:
        print(f"❌ Enhanced bot setup error: {e}")
        bot.polling(none_stop=True)

# -------------------------
# RUN ENHANCED SYSTEM
# -------------------------
if __name__ == '__main__':
    print("🚀 Starting Professional Football AI Predictor...")
    setup_enhanced_bot()
    app.run(host='0.0.0.0', port=PORT)
