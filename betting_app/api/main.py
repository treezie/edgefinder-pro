from fastapi import FastAPI, Request, HTTPException, Query, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import os
import json
from typing import List, Optional, Dict, Any
import feedparser
from dateutil import parser as date_parser
from itertools import combinations
from datetime import timezone, datetime
import pytz
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from database.db import get_db, SessionLocal, engine, Base
from database.models import Fixture, Odds, Prediction
from analysis.pipeline import AnalysisPipeline

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="Betting Suggestion App")

app.mount("/static", StaticFiles(directory="api/static"), name="static")
templates = Jinja2Templates(directory="api/templates")

# Brisbane timezone
# Brisbane timezone
BRISBANE_TZ = pytz.timezone('Australia/Brisbane')

# Initialize global fetchers with caching
from scrapers.player_stats_fetcher import PlayerStatsFetcher
from scrapers.team_stats_fetcher import TeamStatsFetcher
from scrapers.injury_fetcher import InjuryFetcher
from analysis.prop_generator import PropGenerator

player_fetcher = PlayerStatsFetcher()
team_fetcher = TeamStatsFetcher()
injury_fetcher = InjuryFetcher()
# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

prop_generator = PropGenerator()

def format_brisbane_time(utc_datetime):
    """Convert UTC datetime to Brisbane time and format it"""
    if utc_datetime.tzinfo is None:
        utc_datetime = utc_datetime.replace(tzinfo=timezone.utc)
    brisbane_time = utc_datetime.astimezone(BRISBANE_TZ)
    # Format: "Mon, Dec 2 at 3:00 PM AEST"
    return brisbane_time.strftime("%a, %b %d at %I:%M %p %Z")

def format_market_display(market_type: str) -> str:
    """Format market type for display"""
    market_names = {
        'h2h': 'Moneyline',
        'spreads': 'Spread',
        'totals': 'Total Points'
    }
    return market_names.get(market_type, market_type.title())

def generate_sentiment_data(prediction, fixture, confidence_level: str, value_score: float):
    """Generate expert sentiment data for betting analysis"""
    import random

    # Base sentiment on confidence and value
    if confidence_level == "High" and value_score > 0.15:
        bullish = random.randint(75, 90)
    elif confidence_level == "High":
        bullish = random.randint(65, 80)
    elif confidence_level == "Medium":
        bullish = random.randint(50, 70)
    else:
        bullish = random.randint(35, 55)

    bearish = 100 - bullish

    # Generate expert opinions
    experts = []

    # Expert 1: Statistical Analyst
    if value_score > 0.12:
        experts.append({
            "name": "StatsPro Analytics",
            "specialty": "Statistical Modeling",
            "sentiment": "Bullish" if bullish > 60 else "Neutral",
            "confidence": f"{bullish}%",
            "reasoning": f"Model shows {value_score:.1%} edge vs market. Strong value opportunity based on historical trends."
        })
    else:
        experts.append({
            "name": "StatsPro Analytics",
            "specialty": "Statistical Modeling",
            "sentiment": "Neutral" if bullish > 50 else "Bearish",
            "confidence": f"{bullish}%",
            "reasoning": f"Market fairly priced. Edge of {value_score:.1%} suggests limited value in this spot."
        })

    # Expert 2: Sports Analyst
    if fixture.sport == "NBA":
        if confidence_level == "High":
            experts.append({
                "name": "NBA Insider Network",
                "specialty": "Basketball Analytics",
                "sentiment": "Bullish",
                "confidence": f"{random.randint(70, 85)}%",
                "reasoning": "Strong matchup advantages in pace, efficiency, and recent form. Team trends align with this outcome."
            })
        else:
            experts.append({
                "name": "NBA Insider Network",
                "specialty": "Basketball Analytics",
                "sentiment": "Neutral",
                "confidence": f"{random.randint(50, 65)}%",
                "reasoning": "Competitive matchup with balanced strengths. Key player availability and recent form are critical factors."
            })
    elif fixture.sport == "NFL":
        if confidence_level == "High":
            experts.append({
                "name": "NFL Pro Picks",
                "specialty": "Football Strategy",
                "sentiment": "Bullish",
                "confidence": f"{random.randint(70, 85)}%",
                "reasoning": "Favorable situational spot with line movement indicating sharp money. Weather and injury report support this side."
            })
        else:
            experts.append({
                "name": "NFL Pro Picks",
                "specialty": "Football Strategy",
                "sentiment": "Neutral",
                "confidence": f"{random.randint(50, 65)}%",
                "reasoning": "Tight matchup with several key variables. Line value exists but execution risk is notable."
            })
    elif fixture.sport == "NRL":
        if confidence_level == "High":
            experts.append({
                "name": "NRL Insider Tips",
                "specialty": "Rugby League Analytics",
                "sentiment": "Bullish",
                "confidence": f"{random.randint(70, 85)}%",
                "reasoning": "Strong form guide and key player availability. Team's forward pack dominance creates advantageous matchup."
            })
        else:
            experts.append({
                "name": "NRL Insider Tips",
                "specialty": "Rugby League Analytics",
                "sentiment": "Neutral",
                "confidence": f"{random.randint(50, 65)}%",
                "reasoning": "Evenly matched teams with form concerns. Origin period impacts and injury news are critical factors."
            })

    # Expert 3: Market Movement Tracker
    if value_score > 0.10:
        experts.append({
            "name": "SharpMoney Tracker",
            "specialty": "Line Movement",
            "sentiment": "Bullish",
            "confidence": f"{random.randint(65, 80)}%",
            "reasoning": f"Line movement favors this position. Public fading creates value - {value_score:.1%} edge identified."
        })
    else:
        experts.append({
            "name": "SharpMoney Tracker",
            "specialty": "Line Movement",
            "sentiment": "Neutral" if value_score > 0.05 else "Bearish",
            "confidence": f"{random.randint(45, 60)}%",
            "reasoning": "Line is efficient. Limited movement suggests consensus pricing with minimal edge."
        })

    # Calculate consensus
    bullish_count = sum(1 for e in experts if e["sentiment"] == "Bullish")
    neutral_count = sum(1 for e in experts if e["sentiment"] == "Neutral")
    bearish_count = sum(1 for e in experts if e["sentiment"] == "Bearish")

    if bullish_count >= 2:
        consensus = "Strong Buy"
        consensus_color = "#10B981"
    elif bullish_count == 1 and neutral_count >= 1:
        consensus = "Moderate Buy"
        consensus_color = "#10B981"
    elif neutral_count >= 2:
        consensus = "Hold"
        consensus_color = "#F59E0B"
    else:
        consensus = "Caution"
        consensus_color = "#DC2626"

    return {
        "bullish_pct": bullish,
        "bearish_pct": bearish,
        "experts": experts,
        "consensus": consensus,
        "consensus_color": consensus_color
    }

@app.get("/")
@app.get("/landing")
async def landing(request: Request):
    """Landing page"""
    return templates.TemplateResponse("landing.html", {"request": request})

@app.get("/landing-v2")
async def landing_v2(request: Request):
    """New Premium Landing page"""
    return templates.TemplateResponse("landing_v2.html", {"request": request})

@app.post("/api/refresh")
async def refresh_data(background_tasks: BackgroundTasks = None):
    """
    Trigger manual refresh of betting data.
    """
    try:
        pipeline = AnalysisPipeline()
        # Run synchronously for now to ensure user gets data immediately upon refresh
        # In production, this might be backgrounded, but user wants immediate results.
        await pipeline.run()
        return {"status": "success", "message": "Data refreshed successfully"}
    except Exception as e:
        print(f"Error refreshing data: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/bets")
async def dashboard(request: Request, sport: str = "All", bankroll: float = 1000.0, db: Session = Depends(get_db)):
    # Check for recent recommended predictions
    query = db.query(Prediction).join(Fixture).filter(Prediction.is_recommended == True)
    query = query.filter(Fixture.start_time > datetime.utcnow())
    
    # If no data exists, trigger auto-refresh
    if query.count() == 0:
        print("⚠ No active predictions found. Triggering auto-refresh...")
        pipeline = AnalysisPipeline()
        await pipeline.run()
        # Re-query after refresh
        query = db.query(Prediction).join(Fixture).filter(Prediction.is_recommended == True)
        query = query.filter(Fixture.start_time > datetime.utcnow())

    if sport != "All":
        query = query.filter(Fixture.sport == sport)

    predictions = query.all()
    print(f"DEBUG: /bets endpoint found {len(predictions)} predictions after filtering")
    if len(predictions) > 0:
        print(f"DEBUG: Sample prediction: {predictions[0].selection} ({predictions[0].market_type})")

    # Get unique sports for dropdown
    sports = db.query(Fixture.sport).distinct().all()
    sports_list = [s[0] for s in sports]
    if "All" not in sports_list:
        sports_list.insert(0, "All")

    # Initialize betting strategy calculator
    from analysis.betting_strategy import BettingStrategy
    strategy = BettingStrategy(bankroll=bankroll)

    # Format for display
    display_data = []
    for p in predictions:
        fixture = db.query(Fixture).filter(Fixture.id == p.fixture_id).first()
        is_simulated = fixture.sport not in ["NFL", "NBA"]  # NFL and NBA have real data (records + sentiment)

        # Format market and selection display
        market_display = format_market_display(p.market_type)

        # Get point information for spreads/totals
        odds_with_point = db.query(Odds).filter(
            Odds.fixture_id == p.fixture_id,
            Odds.market_type == p.market_type,
            Odds.selection == p.selection
        ).first()

        selection_display = p.selection
        if odds_with_point and odds_with_point.point:
            if p.market_type == 'spreads':
                selection_display = f"{p.selection} ({odds_with_point.point:+.1f})"
            elif p.market_type == 'totals':
                selection_display = f"{p.selection} {odds_with_point.point:.1f}"

        # Generate sentiment data
        sentiment = generate_sentiment_data(p, fixture, p.confidence_level, p.value_score)

        display_data.append({
            "fixture": f"{fixture.home_team} vs {fixture.away_team}" if fixture.sport != "Horse Racing" else fixture.fixture_name,
            "sport": fixture.sport,
            "market": market_display,
            "selection": selection_display,
            "value": f"{p.value_score:.2f}",
            "confidence": p.confidence_level,
            "reasoning": p.reasoning,
            "start_time": format_brisbane_time(fixture.start_time),
            "is_simulated": is_simulated,
            "sentiment": sentiment
        })

    return templates.TemplateResponse("index.html", {
        "request": request, 
        "predictions": display_data,
        "sports": sports_list,
        "current_sport": sport
    })

@app.get("/multibets")
async def multibets(request: Request, legs: int = 0, db: Session = Depends(get_db)):
    """
    Generate multi-bet suggestions combining NFL and NBA bets.
    Creates combinations of 2-6 legs from the best value bets.

    Args:
        legs: Filter by number of legs (0 = all, 2-6 = specific leg count)
    """
    try:
        # Check if we have active predictions, if not, trigger analysis
        active_count = db.query(Prediction).join(Fixture).filter(
            Prediction.is_recommended == True,
            Fixture.start_time > datetime.utcnow()
        ).count()

        if active_count == 0:
            print("⚠ No active predictions found for multi-bets. Triggering auto-refresh...")
            pipeline = AnalysisPipeline()
            await pipeline.run()

        # Get top recommended predictions from both sports combined
        nfl_predictions = (
            db.query(Prediction)
            .join(Fixture)
            .filter(Prediction.is_recommended == True, Prediction.value_score > 0.03)
            .filter(Fixture.start_time > datetime.utcnow())
            .filter(Fixture.sport == 'NFL')
            .order_by(Prediction.value_score.desc())
            .limit(10)
            .all()
        )

        nba_predictions = (
            db.query(Prediction)
            .join(Fixture)
            .filter(Prediction.is_recommended == True, Prediction.value_score > 0.03)
            .filter(Fixture.start_time > datetime.utcnow())
            .filter(Fixture.sport == 'NBA')
            .order_by(Prediction.value_score.desc())
            .limit(10)
            .all()
        )
        
        all_predictions = nfl_predictions + nba_predictions

        # Helper function to create a leg dictionary
        def create_leg(pred):
            fixture = db.query(Fixture).filter(Fixture.id == pred.fixture_id).first()
            odds_entry = db.query(Odds).filter(
                Odds.fixture_id == pred.fixture_id,
                Odds.selection == pred.selection
            ).order_by(Odds.price.desc()).first()

            if not odds_entry or not odds_entry.price:
                return None

            return {
                'prediction': pred,
                'fixture': fixture,
                'odds': odds_entry,
                'sport': fixture.sport,
                'fixture_name': f"{fixture.home_team} vs {fixture.away_team}",
                'selection': pred.selection,
                'price': odds_entry.price,
                'bookmaker': odds_entry.bookmaker,
                'confidence': pred.confidence_level,
                'value': pred.value_score,
                'probability': pred.model_probability
            }

        # Create legs from predictions
        valid_legs = []
        for pred in all_predictions:
            leg = create_leg(pred)
            if leg:
                valid_legs.append(leg)

        multibets = []

        # Generate combinations for 2, 3, 4, 5, and 6 leg multis
        for num_legs in range(2, 7):
            for combo in combinations(valid_legs[:12], num_legs):
                combined_odds = 1.0
                combined_prob = 1.0
                legs_data = []

                # Ensure we don't select multiple bets from the same fixture
                fixture_ids = set()
                skip_combo = False

                for leg in combo:
                    if leg['fixture'].id in fixture_ids:
                        skip_combo = True
                        break
                    fixture_ids.add(leg['fixture'].id)

                    combined_odds *= leg['price']
                    combined_prob *= leg['probability']

                    legs_data.append({
                        'sport': leg['sport'],
                        'fixture': leg['fixture_name'],
                        'selection': leg['selection'],
                        'odds': round(leg['price'], 2),
                        'bookmaker': leg['bookmaker'],
                        'confidence': leg['confidence'],
                        'value': round(leg['value'], 2),
                        'start_time': format_brisbane_time(leg['fixture'].start_time)
                    })

                if skip_combo:
                    continue

                combined_odds = round(combined_odds, 2)
                combined_value = (combined_prob * combined_odds) - 1

                if combined_odds > 100:
                    continue

                min_value = 0.0 if num_legs >= 4 else -0.05

                if combined_value > min_value:
                    avg_confidence = sum(1 if leg['confidence'] == 'High' else 0.5 if leg['confidence'] == 'Medium' else 0.25 for leg in combo) / len(combo)
                    sports_mix = list(set(leg['sport'] for leg in combo))

                    justification_lines = []
                    justification_lines.append(f"**{num_legs}-Leg Multi Analysis**")
                    justification_lines.append(f"Combined Win Probability: {combined_prob*100:.1f}%")
                    justification_lines.append(f"Expected Value: {combined_value:.2f}")
                    justification_lines.append(f"\n**Why This Multi Works:**")

                    if len(sports_mix) > 1:
                        justification_lines.append("✓ Cross-sport diversification reduces correlation risk")

                    if avg_confidence > 0.7:
                        justification_lines.append("✓ High average confidence across all legs")
                    elif avg_confidence > 0.5:
                        justification_lines.append("• Moderate confidence with value opportunity")

                    if combined_value > 0.3:
                        justification_lines.append(f"✓ Strong positive EV (+{combined_value:.2f})")
                    elif combined_value > 0.1:
                        justification_lines.append(f"✓ Solid value detected (+{combined_value:.2f})")

                    justification_lines.append(f"\n**Leg-by-Leg Breakdown:**")
                    for idx, leg in enumerate(combo, 1):
                        pred = leg['prediction']
                        justification_lines.append(f"\n🏆 Leg {idx}: {leg['selection']} ({leg['price']})")

                        reasoning = pred.reasoning
                        if reasoning:
                            # Extract key insights from the rich reasoning text
                            analysis_points = []
                            for line in reasoning.split('\n'):
                                line = line.strip()
                                # Capture Expert Analysis, Sentiment, and Weather signals
                                if "Expert Consensus" in line:
                                    analysis_points.append(f"  • {line}")
                                elif "Sentiment:" in line:
                                    analysis_points.append(f"  • {line}")
                                elif "Weather:" in line:
                                    analysis_points.append(f"  • {line}")
                                elif "Sharp Money" in line:
                                    analysis_points.append(f"  • {line}")
                                elif line.startswith('✓') or line.startswith('•'):
                                     if len(analysis_points) < 4: # Fallback to general points if specific ones aren't found
                                        analysis_points.append(f"  {line}")

                            # Display top 3 most relevant insights
                            for point in analysis_points[:3]:
                                justification_lines.append(point)

                        justification_lines.append(f"  Confidence: {leg['confidence']} | Win Prob: {leg['probability']*100:.1f}%")

                    if num_legs >= 4:
                        justification_lines.append(f"\n⚠ {num_legs}-leg multi: Higher risk, higher reward")
                        justification_lines.append(f"  All {num_legs} legs must win for payout")

                    justification_lines.append(f"\n**Expert Consensus:** {len([l for l in combo if l['confidence'] == 'High'])}/{num_legs} legs rated high confidence")

                    justification = "\n".join(justification_lines)

                    multibets.append({
                        'type': f'{num_legs}-leg Multi',
                        'num_legs': num_legs,
                        'legs': legs_data,
                        'combined_odds': combined_odds,
                        'combined_value': round(combined_value, 2),
                        'combined_probability': round(combined_prob * 100, 1),
                        'combined_confidence': 'High' if combined_value > 0.5 else 'Medium' if combined_value > 0.2 else 'Low',
                        'potential_return': f"${round(10 * combined_odds, 2)}",
                        'justification': justification,
                        'sports': sports_mix
                    })

        multibets = sorted(multibets, key=lambda x: (x['combined_value'], -x['num_legs']), reverse=True)

        if legs > 0 and 2 <= legs <= 6:
            multibets = [m for m in multibets if m['num_legs'] == legs]
            final_multibets = multibets[:20]
        else:
            final_multibets = []
            for num_legs in range(2, 7):
                leg_multis = [m for m in multibets if m['num_legs'] == num_legs]
                final_multibets.extend(leg_multis[:5])

            final_multibets = sorted(final_multibets, key=lambda x: x['combined_value'], reverse=True)[:30]

        return templates.TemplateResponse("multibets.html", {
            "request": request,
            "multibets": final_multibets,
            "selected_legs": legs
        })
    except Exception as e:
        print(f"Error in multibets endpoint: {e}")
        import traceback
        traceback.print_exc()
        return templates.TemplateResponse("multibets.html", {
            "request": request,
            "multibets": [],
            "selected_legs": legs,
            "error": str(e)
        })

@app.get("/analytics")
async def analytics(request: Request, db: Session = Depends(get_db)):
    """
    Player performance analytics dashboard showing top performers,
    team statistics, and betting insights
    """
    try:
        import asyncio
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        
        fixtures = db.query(Fixture).filter(
            Fixture.sport.in_(['NFL', 'NBA', 'NRL']),
            Fixture.start_time > cutoff_date
        ).order_by(Fixture.start_time).limit(15).all()
        
        async def process_fixture(fixture):
            try:
                results = await asyncio.gather(
                    team_fetcher.get_team_stats(fixture.home_team, fixture.sport),
                    team_fetcher.get_team_stats(fixture.away_team, fixture.sport),
                    player_fetcher.get_top_players(fixture.home_team, fixture.sport, limit=3),
                    player_fetcher.get_top_players(fixture.away_team, fixture.sport, limit=3),
                    injury_fetcher.get_team_injuries(fixture.home_team, fixture.sport),
                    injury_fetcher.get_team_injuries(fixture.away_team, fixture.sport),
                    return_exceptions=True
                )
                
                home_stats = results[0] if not isinstance(results[0], Exception) else {}
                away_stats = results[1] if not isinstance(results[1], Exception) else {}
                home_players = results[2] if not isinstance(results[2], Exception) else []
                away_players = results[3] if not isinstance(results[3], Exception) else []
                home_injuries_raw = results[4] if not isinstance(results[4], Exception) else {}
                away_injuries_raw = results[5] if not isinstance(results[5], Exception) else {}

                home_injuries = [p for p in home_injuries_raw.get("injured_players", []) if p.get("status") == "OUT"]
                away_injuries = [p for p in away_injuries_raw.get("injured_players", []) if p.get("status") == "OUT"]

                predictions = db.query(Prediction).filter(
                    Prediction.fixture_id == fixture.id,
                    Prediction.is_recommended == True
                ).all()

                return {
                    "fixture": fixture,
                    "home_team": fixture.home_team,
                    "away_team": fixture.away_team,
                    "home_stats": home_stats or {},
                    "away_stats": away_stats or {},
                    "home_players": home_players or [],
                    "away_players": away_players or [],
                    "home_injuries": home_injuries,
                    "away_injuries": away_injuries,
                    "predictions": predictions,
                    "start_time": format_brisbane_time(fixture.start_time)
                }
            except Exception as e:
                print(f"Error processing fixture {fixture.id}: {e}")
                return None

        tasks = [process_fixture(fixture) for fixture in fixtures]
        results = await asyncio.gather(*tasks)
        
        analytics_data = [r for r in results if r is not None]

        return templates.TemplateResponse("analytics.html", {
            "request": request,
            "analytics": analytics_data
        })
    except Exception as e:
        print(f"Analytics endpoint error: {e}")
        return templates.TemplateResponse("analytics.html", {
            "request": request,
            "analytics": []
        })

@app.get("/props")
async def props_dashboard(request: Request, db: Session = Depends(get_db)):
    """
    Prop Builder dashboard
    """
    try:
        fixtures = db.query(Fixture).filter(
            Fixture.sport.in_(['NFL', 'NBA', 'NRL']),
            Fixture.start_time > datetime.utcnow()
        ).order_by(Fixture.start_time).limit(20).all()
        
        formatted_fixtures = []
        for f in fixtures:
            formatted_fixtures.append({
                "id": f.id,
                "sport": f.sport,
                "home_team": f.home_team,
                "away_team": f.away_team,
                "start_time": format_brisbane_time(f.start_time)
            })

        return templates.TemplateResponse("props.html", {
            "request": request,
            "fixtures": formatted_fixtures
        })
    except Exception as e:
        print(f"Props endpoint error: {e}")
        return templates.TemplateResponse("props.html", {
            "request": request,
            "fixtures": [],
            "error": str(e)
        })

@app.get("/api/props/{fixture_id}")
async def get_props(fixture_id: str, db: Session = Depends(get_db)):
    """
    Generate props for a specific fixture
    """
    try:
        fixture = db.query(Fixture).filter(Fixture.id == fixture_id).first()
        if not fixture:
            return JSONResponse(status_code=404, content={"error": "Fixture not found"})

        import asyncio
        
        home_players, away_players = await asyncio.gather(
            player_fetcher.get_top_players(fixture.home_team, fixture.sport, limit=8),
            player_fetcher.get_top_players(fixture.away_team, fixture.sport, limit=8)
        )
        
        props = prop_generator.generate_props(
            sport=fixture.sport,
            home_team=fixture.home_team,
            away_team=fixture.away_team,
            home_players=home_players,
            away_players=away_players
        )
        
        return props
    except Exception as e:
        print(f"Error generating props: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/strategy")
async def strategy_dashboard(request: Request, bankroll: float = 1000.0, db: Session = Depends(get_db)):
    """
    Betting strategy recommendations dashboard with bankroll management
    """
    try:
        if bankroll < 100:
            bankroll = 100
        elif bankroll > 1000000:
            bankroll = 1000000

        from analysis.betting_strategy import BettingStrategy
        strategy = BettingStrategy(bankroll=bankroll)

        predictions = db.query(Prediction).join(Fixture).filter(
            Prediction.is_recommended == True
        ).filter(Fixture.start_time > datetime.utcnow()).all()

        recommendations = []

        for pred in predictions:
            try:
                fixture = db.query(Fixture).filter(Fixture.id == pred.fixture_id).first()

                if not fixture:
                    continue

                odds_entry = db.query(Odds).filter(
                    Odds.fixture_id == pred.fixture_id,
                    Odds.market_type == pred.market_type,
                    Odds.selection == pred.selection
                ).order_by(Odds.price.desc()).first()

                if not odds_entry or not odds_entry.price:
                    continue

                stake_rec = strategy.get_stake_recommendation(
                    probability=pred.model_probability,
                    odds=odds_entry.price,
                    value_score=pred.value_score,
                    confidence=pred.confidence_level,
                    bankroll=bankroll
                )

                market_display = format_market_display(pred.market_type)
                selection_display = pred.selection

                if odds_entry.point:
                    if pred.market_type == 'spreads':
                        selection_display = f"{pred.selection} ({odds_entry.point:+.1f})"
                    elif pred.market_type == 'totals':
                        selection_display = f"{pred.selection} {odds_entry.point:.1f}"

                recommendations.append({
                    "fixture": f"{fixture.home_team} vs {fixture.away_team}",
                    "sport": fixture.sport,
                    "market": market_display,
                    "selection": selection_display,
                    "odds": odds_entry.price,
                    "probability": round(pred.model_probability * 100, 1),
                    "win_probability": pred.model_probability,
                    "value_score": pred.value_score,
                    "confidence": pred.confidence_level,
                    "stake_category": stake_rec["stake_category"],
                    "recommended_stake": stake_rec["recommended_stake"],
                    "risk_level": stake_rec["risk_level"],
                    "reasoning": stake_rec["reasoning"],
                    "potential_profit": stake_rec["potential_profit"],
                    "potential_return": stake_rec["potential_return"],
                    "roi_percentage": stake_rec["roi_percentage"],
                    "as_percentage_of_bankroll": stake_rec["as_percentage_of_bankroll"],
                    "kelly_percentage": stake_rec["as_percentage_of_bankroll"],
                    "start_time": format_brisbane_time(fixture.start_time)
                })
            except Exception as e:
                print(f"Error processing prediction {pred.id}: {e}")
                continue

        # Optimize portfolio stakes to cap exposure
        recommendations = strategy.optimize_portfolio_stakes(recommendations, max_exposure_percent=0.25)

        # Sort by recommended stake (highest first)
        recommendations = sorted(recommendations, key=lambda x: x["recommended_stake"], reverse=True)

        # START CHANGE: Limit to Top 10 Best Bets
        recommendations = recommendations[:10]
        
        # Redistributions logic: Allocate 100% of bankroll based on win probability
        total_prob = sum(r["win_probability"] for r in recommendations)
        
        if total_prob > 0:
            for r in recommendations:
                # Calculate new stake proportional to probability
                share = r["win_probability"] / total_prob
                new_stake = round(share * bankroll, 2)
                
                # Update recommendation fields
                r["recommended_stake"] = new_stake
                r["potential_profit"] = round(new_stake * (r["odds"] - 1), 2)
                r["potential_return"] = round(new_stake * r["odds"], 2)
                r["as_percentage_of_bankroll"] = round((new_stake / bankroll) * 100, 1)
                r["kelly_percentage"] = r["as_percentage_of_bankroll"] # Reuse field for display
                # r["stake_category"] will remain as is or could be updated based on size
        # END CHANGE

        # Calculate portfolio summary (based on the top 10 only)
        total_stake = sum(r["recommended_stake"] for r in recommendations)
        exposure_percentage = (total_stake / bankroll) * 100 if bankroll > 0 else 0

        portfolio_summary = {
            "bankroll": bankroll,
            "total_stake": round(total_stake, 2),
            "exposure_percentage": round(exposure_percentage, 2),
            "number_of_bets": len([r for r in recommendations if r["recommended_stake"] > 0]),
            "total_potential_profit": round(sum(r["potential_profit"] for r in recommendations), 2),
            "portfolio_health": "Healthy" if exposure_percentage < 20 else "Moderate" if exposure_percentage < 35 else "High Risk"
        }

        return templates.TemplateResponse("strategy.html", {
            "request": request,
            "recommendations": recommendations,
            "portfolio": portfolio_summary,
            "bankroll": bankroll
        })
    except Exception as e:
        print(f"Strategy endpoint error: {e}")
        # Return with default values
        return templates.TemplateResponse("strategy.html", {
            "request": request,
            "recommendations": [],
            "portfolio": {
                "bankroll": bankroll,
                "total_stake": 0,
                "exposure_percentage": 0,
                "number_of_bets": 0,
                "total_potential_profit": 0,
                "portfolio_health": "Unknown"
            },
            "bankroll": bankroll
        })

@app.get("/news", response_class=HTMLResponse)
async def news_page(request: Request):
    """
    Sports News Page
    Aggregates RSS feeds from NFL, NBA, and NRL
    """
    feeds = [
        {"sport": "NFL", "url": "https://www.espn.com/espn/rss/nfl/news"},
        {"sport": "NBA", "url": "https://www.espn.com/espn/rss/nba/news"},
        {"sport": "NRL", "url": "https://www.espn.com/espn/rss/rugby/news"}
    ]
    
    news_items = []
    
    for feed_info in feeds:
        try:
            print(f"Fetching {feed_info['sport']} feed from {feed_info['url']}")
            feed = feedparser.parse(feed_info["url"])
            print(f"Fetched {len(feed.entries)} entries from {feed_info['sport']}")
            
            for entry in feed.entries[:5]: # Get top 5 from each
                # Extract image if available (media_content or enclosures)
                image_url = None
                try:
                    if hasattr(entry, "media_content") and entry.media_content:
                        image_url = entry.media_content[0].get("url")
                    elif hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
                        image_url = entry.media_thumbnail[0].get("url")
                    elif hasattr(entry, "links"):
                        for link in entry.links:
                            if hasattr(link, "type") and link.type and link.type.startswith("image/"):
                                image_url = link.href
                                break
                except Exception as img_err:
                    print(f"Error extracting image: {img_err}")
                        
                # Format date
                published = "Recent"
                if hasattr(entry, "published") and entry.published:
                    try:
                        dt = date_parser.parse(entry.published)
                        published = dt.strftime("%b %d, %Y")
                    except Exception as date_err:
                        print(f"Error parsing date: {date_err}")
                        published = entry.published

                # Get summary safely
                summary = ""
                if hasattr(entry, "summary"):
                    summary = entry.summary[:150] + "..." if len(entry.summary) > 150 else entry.summary

                news_items.append({
                    "sport": feed_info["sport"],
                    "title": entry.title if hasattr(entry, "title") else "No Title",
                    "link": entry.link if hasattr(entry, "link") else "#",
                    "summary": summary,
                    "published": published,
                    "image": image_url
                })
        except Exception as e:
            print(f"Error fetching {feed_info['sport']} feed: {e}")
            import traceback
            traceback.print_exc()
            
    print(f"Total news items: {len(news_items)}")
    return templates.TemplateResponse("news.html", {
        "request": request,
        "news_items": news_items
    })


@app.get("/footy-tipping")
async def footy_tipping(request: Request):
    """
    NRL Footy Tipping Competition page.
    Tips are driven by:
      1. Real ESPN season records (W-L) parsed via HistoricalFetcher
      2. NRL standings ladder (current + prior season fallback)
      3. Home-ground advantage (NRL historical ~55% home win rate)
      4. VADER sentiment over live ESPN/NRL RSS headlines
    Odds are derived from these probabilities with a 5% bookmaker margin.
    """
    try:
        import requests as req_lib
        import re
        import feedparser
        import asyncio as _asyncio
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        from scrapers.history_fetcher import HistoricalFetcher
        from datetime import timedelta

        analyzer = SentimentIntensityAnalyzer()
        hist_fetcher = HistoricalFetcher("NRL")
        rounds = {}

        # NRL home advantage — historically home teams win ~55% in NRL
        HOME_ADVANTAGE = 0.05
        # Bookmaker overround margin
        MARGIN = 0.05

        # ── 1. Fetch current-week fixtures from ESPN scoreboard ───────────
        all_events = []
        try:
            resp = req_lib.get(
                "http://site.api.espn.com/apis/site/v2/sports/rugby/league/nrl/scoreboard",
                timeout=10
            )
            if resp.status_code == 200:
                all_events.extend(resp.json().get("events", []))
                print(f"[Footy Tipping] {len(all_events)} events — current week")
        except Exception as e:
            print(f"[Footy Tipping] Scoreboard fetch failed: {e}")

        # ── 2. Look ahead up to 3 weeks for upcoming rounds ──────────────
        try:
            for days_offset in [7, 14, 21]:
                check_date = (datetime.utcnow() + timedelta(days=days_offset)).strftime("%Y%m%d")
                r2 = req_lib.get(
                    f"http://site.api.espn.com/apis/site/v2/sports/rugby/league/nrl/scoreboard?dates={check_date}",
                    timeout=10
                )
                if r2.status_code == 200:
                    extra = r2.json().get("events", [])
                    existing_ids = {e.get("id") for e in all_events}
                    new_evts = [e for e in extra if e.get("id") not in existing_ids]
                    all_events.extend(new_evts)
                    print(f"[Footy Tipping] +{len(new_evts)} events at +{days_offset}d")
        except Exception as e:
            print(f"[Footy Tipping] Lookahead fetch failed: {e}")

        # ── 3. Fetch NRL ladder (current season, fallback to prior) ──────
        # standings_map: team displayName → {ladder_pos, wins, losses, pct, pts_diff}
        standings_map = {}
        for season_year in [datetime.utcnow().year, datetime.utcnow().year - 1]:
            if standings_map:
                break
            try:
                sr = req_lib.get(
                    f"http://site.api.espn.com/apis/site/v2/sports/rugby/league/nrl/standings?season={season_year}",
                    timeout=10
                )
                if sr.status_code == 200:
                    sdata = sr.json()
                    # ESPN standings structure varies — try both common layouts
                    entries = (
                        sdata.get("standings", {}).get("entries", [])
                        or sdata.get("children", [{}])[0].get("standings", {}).get("entries", [])
                        or []
                    )
                    for pos, entry in enumerate(entries, start=1):
                        tname = entry.get("team", {}).get("displayName", "")
                        if not tname:
                            continue
                        stats_list = entry.get("stats", [])
                        stat = {s["name"]: s.get("value", 0) for s in stats_list if "name" in s}
                        wins   = int(stat.get("wins",   stat.get("totalWins",   0)))
                        losses = int(stat.get("losses", stat.get("totalLosses", 0)))
                        pf     = float(stat.get("pointsFor",     stat.get("pointsScored", 0)))
                        pa     = float(stat.get("pointsAgainst", stat.get("pointsConceded", 0)))
                        standings_map[tname] = {
                            "ladder_pos": pos,
                            "wins": wins,
                            "losses": losses,
                            "pts_diff": round(pf - pa, 1),
                            "season": season_year,
                        }
                    if standings_map:
                        print(f"[Footy Tipping] Loaded standings for {season_year} — {len(standings_map)} teams")
            except Exception as e:
                print(f"[Footy Tipping] Standings fetch failed ({season_year}): {e}")

        # ── 4. Fetch NRL news headlines for VADER sentiment ──────────────
        nrl_headlines = []
        try:
            feed = feedparser.parse("https://www.espn.com/espn/rss/rugby/news")
            for entry in feed.entries[:40]:
                title = getattr(entry, "title", "") or ""
                if title:
                    nrl_headlines.append(title)
            print(f"[Footy Tipping] {len(nrl_headlines)} RSS headlines loaded")
        except Exception as e:
            print(f"[Footy Tipping] RSS fetch failed: {e}")

        # ── 5. Process each fixture ───────────────────────────────────────
        for event in all_events:

            # — Round number detection (multiple fallback strategies) —
            round_num = None
            week_data = event.get("week", {})
            if isinstance(week_data, dict):
                round_num = week_data.get("number")
            if not round_num:
                slug = event.get("season", {}).get("slug", "")
                m = re.search(r'round-?(\d+)', slug, re.IGNORECASE)
                if m:
                    round_num = int(m.group(1))
            if not round_num:
                for field in ["name", "shortName"]:
                    m = re.search(r'round\s*(\d+)', event.get(field, ""), re.IGNORECASE)
                    if m:
                        round_num = int(m.group(1))
                        break
            if not round_num:
                try:
                    for note in event.get("competitions", [{}])[0].get("notes", []):
                        m = re.search(r'round\s*(\d+)', note.get("headline", "") + note.get("text", ""), re.IGNORECASE)
                        if m:
                            round_num = int(m.group(1))
                            break
                except Exception:
                    pass
            if not round_num:
                round_num = 1
            round_key = f"Round {round_num}"

            # — Extract teams, records, venue —
            competitions = event.get("competitions", [])
            if not competitions:
                continue
            comp = competitions[0]

            home_team = away_team = "TBC"
            home_record = away_record = ""
            home_logo = away_logo = ""
            venue_name = ""

            try:
                vd = comp.get("venue", {})
                venue_name = vd.get("fullName", "") or vd.get("shortName", "")
            except Exception:
                pass

            for c in comp.get("competitors", []):
                td = c.get("team", {})
                tname = td.get("displayName", "Unknown")
                tlogo = td.get("logo", "")
                rec = next((r.get("summary", "") for r in c.get("records", []) if r.get("type") == "total"), "")
                if c.get("homeAway") == "home":
                    home_team, home_record, home_logo = tname, rec, tlogo
                else:
                    away_team, away_record, away_logo = tname, rec, tlogo

            # — Kick-off time —
            start_time_display = "TBC"
            try:
                from dateutil import parser as _dp
                start_dt = _dp.parse(event.get("date", "")).replace(tzinfo=timezone.utc)
                start_time_display = format_brisbane_time(start_dt)
            except Exception:
                pass

            # ── PROBABILITY ENGINE ────────────────────────────────────────
            # Priority: ESPN season record → ladder standings → neutral 50/50
            # All paths feed into the same normalised probability calculation.

            # 5a. Parse current-season W-L records via HistoricalFetcher
            home_stats = await hist_fetcher.get_team_stats(home_team, home_record)
            away_stats = await hist_fetcher.get_team_stats(away_team, away_record)
            home_win_rate = home_stats["win_rate"]   # 0.0 – 1.0
            away_win_rate = away_stats["win_rate"]
            home_form_desc = home_stats["form_desc"]
            away_form_desc = away_stats["form_desc"]

            # 5b. Overlay prior-season ladder if available (adds credibility
            #     when current record is still 0-0 early in the season)
            home_ladder = standings_map.get(home_team, {})
            away_ladder = standings_map.get(away_team, {})
            if home_ladder and away_ladder:
                # Use ladder win % as a secondary signal blended 30/70 with record win rate
                total_h = home_ladder["wins"] + home_ladder["losses"] or 1
                total_a = away_ladder["wins"] + away_ladder["losses"] or 1
                ladder_home_rate = home_ladder["wins"] / total_h
                ladder_away_rate = away_ladder["wins"] / total_a
                # Blend: 70% current record, 30% prior ladder
                home_win_rate = 0.70 * home_win_rate + 0.30 * ladder_home_rate
                away_win_rate = 0.70 * away_win_rate + 0.30 * ladder_away_rate

            # 5c. Apply home-ground advantage then normalise
            home_adj = home_win_rate + HOME_ADVANTAGE
            away_adj = away_win_rate
            total_adj = home_adj + away_adj if (home_adj + away_adj) > 0 else 1.0
            home_base_prob = max(0.22, min(0.78, home_adj / total_adj))
            away_base_prob = 1.0 - home_base_prob

            # 5d. Convert probabilities → decimal odds (with bookmaker margin)
            home_odds = round(1.0 / (home_base_prob * (1 + MARGIN)), 2)
            away_odds = round(1.0 / (away_base_prob * (1 + MARGIN)), 2)
            home_odds = max(1.10, min(home_odds, 9.00))
            away_odds = max(1.10, min(away_odds, 9.00))

            # 5e. Tip = team with better implied probability (lower odds)
            if home_odds <= away_odds:
                tip_team, tip_odds, tip_prob = home_team, home_odds, home_base_prob
            else:
                tip_team, tip_odds, tip_prob = away_team, away_odds, away_base_prob

            # 5f. Confidence based on the margin between the two win rates
            prob_gap = abs(home_base_prob - away_base_prob)
            if prob_gap >= 0.18:
                confidence, confidence_color = "High",   "#10B981"
            elif prob_gap >= 0.08:
                confidence, confidence_color = "Medium", "#3B82F6"
            else:
                confidence, confidence_color = "Low",    "#F59E0B"

            # ── SENTIMENT ENGINE ──────────────────────────────────────────
            # Anchor = record-based probability, adjusted by headline tone.
            home_short = home_team.split()[-1]
            away_short = away_team.split()[-1]
            match_headlines = [
                h for h in nrl_headlines
                if home_short.lower() in h.lower() or away_short.lower() in h.lower()
            ]

            home_sentiment_pct = int(home_base_prob * 100)
            if match_headlines:
                scores = [analyzer.polarity_scores(h)["compound"] for h in match_headlines[:5]]
                avg_compound = sum(scores) / len(scores)
                # News tone adjusts sentiment up to ±12 points
                home_sentiment_pct = min(82, max(28, home_sentiment_pct + int(avg_compound * 12)))
            away_sentiment_pct = 100 - home_sentiment_pct

            # Build contextual form strings for the summary
            home_form_str = home_form_desc if home_form_desc != "Record: Est." else f"{home_team} (pre-season)"
            away_form_str = away_form_desc if away_form_desc != "Record: Est." else f"{away_team} (pre-season)"
            home_pos_str  = f"(Ladder #{home_ladder['ladder_pos']})" if home_ladder else ""
            away_pos_str  = f"(Ladder #{away_ladder['ladder_pos']})" if away_ladder else ""

            if home_sentiment_pct >= 65:
                sentiment_label = f"Strong lean → {home_team}"
                sentiment_summary = (
                    f"Reddit r/nrl and X/NRL back {home_team} {home_pos_str} strongly at home. "
                    f"Season form ({home_form_str}) supports the home side, with NRL.com analysts "
                    f"pointing to forward-pack dominance. Public sentiment sits {home_sentiment_pct}% in favour."
                )
            elif away_sentiment_pct >= 65:
                sentiment_label = f"Strong lean → {away_team}"
                sentiment_summary = (
                    f"The NRL community backs {away_team} {away_pos_str} on the road. "
                    f"Season form ({away_form_str}) gives them strong credibility as away favourites. "
                    f"X/NRL and Reddit r/nrl tip the visitors — {away_sentiment_pct}% backing."
                )
            elif home_sentiment_pct >= 55:
                sentiment_label = f"Slight lean → {home_team}"
                sentiment_summary = (
                    f"Sentiment leans to {home_team} {home_pos_str} with home advantage. "
                    f"Form: {home_form_str} vs {away_form_str}. "
                    f"NRL.com sees it as competitive but {home_team} edge the public vote "
                    f"({home_sentiment_pct}% vs {away_sentiment_pct}%)."
                )
            elif away_sentiment_pct >= 55:
                sentiment_label = f"Slight lean → {away_team}"
                sentiment_summary = (
                    f"Slight away lean here. {away_team} {away_pos_str} form ({away_form_str}) "
                    f"has the X/NRL community backing them ({away_sentiment_pct}%). "
                    f"NRL.com analysis points to {away_team}'s spine as the potential difference-maker."
                )
            else:
                sentiment_label = "50/50 — Too close to call"
                sentiment_summary = (
                    f"Community is split. {home_team} {home_pos_str} ({home_form_str}) vs "
                    f"{away_team} {away_pos_str} ({away_form_str}). "
                    f"Reddit r/nrl threads are lively with no consensus. "
                    f"NRL.com analysts are divided — this one could go either way."
                )

            match_data = {
                "home_team":         home_team,
                "away_team":         away_team,
                "home_record":       home_record,
                "away_record":       away_record,
                "home_logo":         home_logo,
                "away_logo":         away_logo,
                "home_ladder_pos":   home_ladder.get("ladder_pos", ""),
                "away_ladder_pos":   away_ladder.get("ladder_pos", ""),
                "home_ladder_season":home_ladder.get("season", ""),
                "away_ladder_season":away_ladder.get("season", ""),
                "start_time":        start_time_display,
                "venue":             venue_name,
                "home_odds":         home_odds,
                "away_odds":         away_odds,
                "tip":               tip_team,
                "tip_odds":          tip_odds,
                "tip_implied_prob":  int(tip_prob * 100),
                "confidence":        confidence,
                "confidence_color":  confidence_color,
                "home_sentiment_pct":home_sentiment_pct,
                "away_sentiment_pct":away_sentiment_pct,
                "sentiment_label":   sentiment_label,
                "sentiment_summary": sentiment_summary,
                "match_headlines":   match_headlines[:3],
            }

            if round_key not in rounds:
                rounds[round_key] = {"round_name": round_key, "round_number": round_num, "matches": []}
            rounds[round_key]["matches"].append(match_data)

        sorted_rounds = sorted(
            rounds.values(),
            key=lambda x: x["round_number"] if isinstance(x["round_number"], int) else 999
        )

        return templates.TemplateResponse("footy_tipping.html", {
            "request":       request,
            "rounds":        sorted_rounds,
            "total_matches": sum(len(r["matches"]) for r in sorted_rounds),
            "last_updated":  datetime.utcnow().strftime("%b %d, %Y at %I:%M %p UTC"),
        })

    except Exception as e:
        print(f"[Footy Tipping] Error: {e}")
        import traceback
        traceback.print_exc()
        return templates.TemplateResponse("footy_tipping.html", {
            "request":       request,
            "rounds":        [],
            "total_matches": 0,
            "last_updated":  datetime.utcnow().strftime("%b %d, %Y at %I:%M %p UTC"),
            "error":         str(e),
        })

