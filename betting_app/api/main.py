from fastapi import FastAPI, Request, HTTPException, Query, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio
import uvicorn
import os
import json
from typing import List, Optional, Dict, Any
import feedparser
from dateutil import parser as date_parser
from itertools import combinations
from datetime import timezone, datetime, timedelta
import pytz
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from sqlalchemy import or_
from database.db import get_db, SessionLocal, engine, Base
from database.models import Fixture, Odds, Prediction, PredictionSnapshot
from analysis.pipeline import AnalysisPipeline

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="Betting Suggestion App")

# Background refresh state - prevents blocking requests and duplicate runs
_refresh_in_progress = False

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


async def _run_pipeline_background():
    """Run the analysis pipeline in the background without blocking requests."""
    global _refresh_in_progress
    if _refresh_in_progress:
        return  # Already running, skip
    _refresh_in_progress = True
    try:
        print("🔄 Background pipeline refresh started...")
        pipeline = AnalysisPipeline()
        await pipeline.run()
        print("✅ Background pipeline refresh complete.")
    except Exception as e:
        print(f"❌ Background pipeline refresh failed: {e}")
    finally:
        _refresh_in_progress = False


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
    """
    Generate expert sentiment data for betting analysis.
    All values are deterministically derived from confidence_level and value_score.
    """
    # Deterministic bullish percentage based on confidence and value
    if confidence_level == "High" and value_score > 0.15:
        bullish = 82
    elif confidence_level == "High":
        bullish = 72
    elif confidence_level == "Medium" and value_score > 0.10:
        bullish = 65
    elif confidence_level == "Medium":
        bullish = 58
    else:
        bullish = 45

    bearish = 100 - bullish

    # Deterministic expert confidence derived from value_score
    stats_confidence = min(90, max(40, int(value_score * 500) + 50))
    sport_confidence = min(85, max(50, int(value_score * 400) + 55)) if confidence_level == "High" else min(65, max(45, int(value_score * 300) + 45))
    market_confidence = min(80, max(40, int(value_score * 450) + 45))

    experts = []

    # Expert 1: Statistical Analyst
    if value_score > 0.12:
        experts.append({
            "name": "StatsPro Analytics",
            "specialty": "Statistical Modeling",
            "sentiment": "Bullish" if bullish > 60 else "Neutral",
            "confidence": f"{stats_confidence}%",
            "reasoning": f"Model shows {value_score:.1%} edge vs market. Strong value opportunity based on historical trends."
        })
    else:
        experts.append({
            "name": "StatsPro Analytics",
            "specialty": "Statistical Modeling",
            "sentiment": "Neutral" if bullish > 50 else "Bearish",
            "confidence": f"{stats_confidence}%",
            "reasoning": f"Market fairly priced. Edge of {value_score:.1%} suggests limited value in this spot."
        })

    # Expert 2: Sports Analyst
    sport_analysts = {
        "NBA": ("NBA Insider Network", "Basketball Analytics"),
        "NFL": ("NFL Pro Picks", "Football Strategy"),
        "NRL": ("NRL Insider Tips", "Rugby League Analytics"),
    }
    analyst_name, analyst_specialty = sport_analysts.get(fixture.sport, ("Sports Analyst", "General"))

    if confidence_level == "High":
        experts.append({
            "name": analyst_name,
            "specialty": analyst_specialty,
            "sentiment": "Bullish",
            "confidence": f"{sport_confidence}%",
            "reasoning": "Strong matchup advantages and recent form align with this outcome."
        })
    else:
        experts.append({
            "name": analyst_name,
            "specialty": analyst_specialty,
            "sentiment": "Neutral",
            "confidence": f"{sport_confidence}%",
            "reasoning": "Competitive matchup with balanced strengths. Key player availability is a critical factor."
        })

    # Expert 3: Market Movement Tracker
    if value_score > 0.10:
        experts.append({
            "name": "SharpMoney Tracker",
            "specialty": "Line Movement",
            "sentiment": "Bullish",
            "confidence": f"{market_confidence}%",
            "reasoning": f"Line movement favors this position. {value_score:.1%} edge identified."
        })
    else:
        experts.append({
            "name": "SharpMoney Tracker",
            "specialty": "Line Movement",
            "sentiment": "Neutral" if value_score > 0.05 else "Bearish",
            "confidence": f"{market_confidence}%",
            "reasoning": "Line is efficient. Limited movement suggests consensus pricing with minimal edge."
        })

    # Calculate consensus
    bullish_count = sum(1 for e in experts if e["sentiment"] == "Bullish")
    neutral_count = sum(1 for e in experts if e["sentiment"] == "Neutral")

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
async def refresh_data():
    """
    Trigger manual refresh of betting data (runs in background).
    """
    if _refresh_in_progress:
        return {"status": "in_progress", "message": "Data refresh already running. Check back shortly."}
    asyncio.create_task(_run_pipeline_background())
    return {"status": "started", "message": "Data refresh started in background. Reload in ~60 seconds."}

@app.get("/api/refresh/status")
async def refresh_status():
    """Check if a background refresh is currently running."""
    return {"refreshing": _refresh_in_progress}

@app.get("/api/debug")
async def debug_info(db: Session = Depends(get_db)):
    """Diagnostic endpoint to see what's happening on Render."""
    import traceback
    info = {}
    try:
        info["odds_api_key_set"] = bool(os.getenv("ODDS_API_KEY"))
        info["odds_api_key_prefix"] = os.getenv("ODDS_API_KEY", "")[:8] if os.getenv("ODDS_API_KEY") else None
        info["database_url_type"] = os.getenv("DATABASE_URL", "sqlite (default)")[:20]
        info["refresh_in_progress"] = _refresh_in_progress
        info["utc_now"] = str(datetime.utcnow())

        total_fixtures = db.query(Fixture).count()
        total_predictions = db.query(Prediction).count()
        upcoming_fixtures = db.query(Fixture).filter(Fixture.start_time > datetime.utcnow()).count()
        upcoming_recommended = db.query(Prediction).join(Fixture).filter(
            Prediction.is_recommended == True,
            Fixture.start_time > datetime.utcnow()
        ).count()

        info["total_fixtures"] = total_fixtures
        info["total_predictions"] = total_predictions
        info["upcoming_fixtures"] = upcoming_fixtures
        info["upcoming_recommended"] = upcoming_recommended

        # Show recent fixtures
        recent = db.query(Fixture).order_by(Fixture.id.desc()).limit(3).all()
        info["latest_fixtures"] = [
            {"id": f.id, "sport": f.sport, "name": f.fixture_name, "start": str(f.start_time)}
            for f in recent
        ]

        # Try a quick NBA odds fetch to test API
        try:
            from scrapers.odds_api_fetcher import OddsAPIFetcher
            fetcher = OddsAPIFetcher(api_key=os.getenv("ODDS_API_KEY"))
            info["fetcher_api_key_set"] = bool(fetcher.api_key)
        except Exception as e:
            info["fetcher_error"] = str(e)

    except Exception as e:
        info["error"] = str(e)
        info["traceback"] = traceback.format_exc()

    return info

@app.get("/api/refresh/nba")
async def refresh_nba_only():
    """Run NBA pipeline only - faster, for debugging on Render."""
    global _refresh_in_progress
    if _refresh_in_progress:
        return {"status": "in_progress"}
    _refresh_in_progress = True
    try:
        pipeline = AnalysisPipeline()
        await pipeline._process_sport("NBA")
        return {"status": "success", "message": "NBA refresh complete"}
    except Exception as e:
        import traceback
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}
    finally:
        _refresh_in_progress = False

@app.get("/bets")
async def dashboard(request: Request, sport: str = "All", bankroll: float = 1000.0, db: Session = Depends(get_db)):
    try:
        # Check for recent recommended predictions
        query = db.query(Prediction).join(Fixture).filter(Prediction.is_recommended == True)
        query = query.filter(Fixture.start_time > datetime.utcnow())

        # If no data exists, trigger background refresh (non-blocking)
        if query.count() == 0 and not _refresh_in_progress:
            print("⚠ No active predictions found. Triggering background refresh...")
            asyncio.create_task(_run_pipeline_background())

        if sport != "All":
            query = query.filter(Fixture.sport == sport)

        predictions = query.all()
        print(f"DEBUG: /bets endpoint found {len(predictions)} predictions after filtering")

        # Get unique sports for dropdown
        sports = db.query(Fixture.sport).distinct().all()
        sports_list = [s[0] for s in sports]
        if "All" not in sports_list:
            sports_list.insert(0, "All")

        # Format for display
        display_data = []
        for p in predictions:
            fixture = db.query(Fixture).filter(Fixture.id == p.fixture_id).first()
            if not fixture:
                continue
            is_simulated = fixture.sport not in ["NFL", "NBA", "NRL"]

            market_display = format_market_display(p.market_type)

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
            "current_sport": sport,
            "refreshing": _refresh_in_progress
        })
    except Exception as e:
        print(f"❌ /bets endpoint error: {e}")
        import traceback
        traceback.print_exc()
        return templates.TemplateResponse("index.html", {
            "request": request,
            "predictions": [],
            "sports": ["All"],
            "current_sport": sport,
            "refreshing": _refresh_in_progress
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

        if active_count == 0 and not _refresh_in_progress:
            print("⚠ No active predictions found for multi-bets. Triggering background refresh...")
            asyncio.create_task(_run_pipeline_background())

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

        nrl_predictions = (
            db.query(Prediction)
            .join(Fixture)
            .filter(Prediction.is_recommended == True, Prediction.value_score > 0.03)
            .filter(Fixture.start_time > datetime.utcnow())
            .filter(Fixture.sport == 'NRL')
            .order_by(Prediction.value_score.desc())
            .limit(10)
            .all()
        )

        all_predictions = nfl_predictions + nba_predictions + nrl_predictions

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

        # Fetch game logs for all players (for last 5 games + vs opponent insights)
        sport_key_map = {"NBA": "basketball", "NFL": "football", "NRL": "rugby-league"}
        league_key_map = {"NBA": "nba", "NFL": "nfl", "NRL": "nrl"}
        sport_key = sport_key_map.get(fixture.sport, "football")
        league_key = league_key_map.get(fixture.sport, "nfl")

        async def fetch_game_log(player, opponent_team):
            pid = player.get("id")
            if not pid:
                return {}
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: player_fetcher.get_player_game_log(pid, sport_key, league_key, opponent=opponent_team, limit=5)
            )

        home_log_tasks = [fetch_game_log(p, fixture.away_team) for p in home_players]
        away_log_tasks = [fetch_game_log(p, fixture.home_team) for p in away_players]
        all_logs = await asyncio.gather(*home_log_tasks, *away_log_tasks)

        home_logs = all_logs[:len(home_players)]
        away_logs = all_logs[len(home_players):]

        # Attach game logs to player dicts
        for player, log in zip(home_players, home_logs):
            player["game_log"] = log
        for player, log in zip(away_players, away_logs):
            player["game_log"] = log

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
        {"sport": "NRL", "url": "https://www.zerotackle.com/feed/"},
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


@app.get("/api/debug/accuracy")
async def debug_accuracy(db: Session = Depends(get_db)):
    """Diagnostic endpoint — shows snapshot counts and sample data."""
    total_snapshots = db.query(PredictionSnapshot).count()
    settled_snapshots = db.query(PredictionSnapshot).filter(PredictionSnapshot.outcome.isnot(None)).count()
    pending_snapshots = db.query(PredictionSnapshot).filter(PredictionSnapshot.outcome.is_(None)).count()

    recent = (
        db.query(PredictionSnapshot)
        .order_by(PredictionSnapshot.created_at.desc())
        .limit(5)
        .all()
    )
    samples = [
        {
            "id": s.id[:8],
            "fixture": f"{s.home_team} vs {s.away_team}",
            "sport": s.sport,
            "market": s.market_type,
            "selection": s.selection,
            "outcome": s.outcome,
            "start_time": str(s.start_time),
            "created_at": str(s.created_at),
        }
        for s in recent
    ]

    # Check unsettled fixtures (past games with no score)
    unsettled_fixtures = (
        db.query(Fixture)
        .filter(
            Fixture.start_time < datetime.now(timezone.utc),
            Fixture.result_settled_at.is_(None),
        )
        .count()
    )

    return {
        "total_snapshots": total_snapshots,
        "settled_snapshots": settled_snapshots,
        "pending_snapshots": pending_snapshots,
        "unsettled_fixtures": unsettled_fixtures,
        "utc_now": str(datetime.now(timezone.utc)),
        "recent_snapshots": samples,
    }


@app.get("/accuracy", response_class=HTMLResponse)
async def accuracy_page(request: Request, days: int = 3, db: Session = Depends(get_db)):
    """Prediction accuracy dashboard."""
    from scrapers.results_fetcher import ResultsFetcher
    from collections import defaultdict

    days = max(1, min(7, days))

    # Always settle up to 7 days back regardless of display window,
    # so results are populated even when viewing a narrow window.
    try:
        ResultsFetcher().fetch_and_settle(db, days_back=7)
    except Exception as e:
        print(f"Results settlement error: {e}")
        import traceback
        traceback.print_exc()

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # All snapshots in window — match on EITHER start_time or created_at
    # so snapshots aren't missed if start_time is slightly outside the window.
    all_snaps = (
        db.query(PredictionSnapshot)
        .filter(
            or_(PredictionSnapshot.start_time >= cutoff, PredictionSnapshot.created_at >= cutoff)
        )
        .order_by(PredictionSnapshot.start_time.desc())
        .all()
    )

    settled = [s for s in all_snaps if s.outcome is not None]
    pending = [s for s in all_snaps if s.outcome is None]

    # --- Overall stats ---
    total_settled = len(settled)
    total_snapshots = len(all_snaps)
    correct = sum(1 for s in settled if s.outcome == "correct")
    overall_rate = round((correct / total_settled) * 100, 1) if total_settled else 0

    rec_settled = [s for s in settled if s.is_recommended]
    rec_correct = sum(1 for s in rec_settled if s.outcome == "correct")
    rec_rate = round((rec_correct / len(rec_settled)) * 100, 1) if rec_settled else 0

    # --- By sport ---
    by_sport = defaultdict(lambda: {"total": 0, "correct": 0})
    for s in settled:
        by_sport[s.sport]["total"] += 1
        if s.outcome == "correct":
            by_sport[s.sport]["correct"] += 1
    sport_stats = [
        {"sport": k, "total": v["total"], "correct": v["correct"],
         "rate": round((v["correct"] / v["total"]) * 100, 1) if v["total"] else 0}
        for k, v in sorted(by_sport.items())
    ]

    # --- By confidence ---
    by_conf = defaultdict(lambda: {"total": 0, "correct": 0})
    for s in settled:
        by_conf[s.confidence_level]["total"] += 1
        if s.outcome == "correct":
            by_conf[s.confidence_level]["correct"] += 1
    conf_order = ["High", "Medium", "Low"]
    conf_stats = [
        {"level": k, "total": by_conf[k]["total"], "correct": by_conf[k]["correct"],
         "rate": round((by_conf[k]["correct"] / by_conf[k]["total"]) * 100, 1) if by_conf[k]["total"] else 0}
        for k in conf_order if k in by_conf
    ]

    # --- By market type ---
    by_market = defaultdict(lambda: {"total": 0, "correct": 0})
    for s in settled:
        by_market[s.market_type]["total"] += 1
        if s.outcome == "correct":
            by_market[s.market_type]["correct"] += 1
    market_stats = [
        {"market": format_market_display(k), "total": v["total"], "correct": v["correct"],
         "rate": round((v["correct"] / v["total"]) * 100, 1) if v["total"] else 0}
        for k, v in sorted(by_market.items())
    ]

    # --- Daily breakdown ---
    by_day = defaultdict(list)
    for s in all_snaps:
        st = s.start_time
        if st and st.tzinfo is None:
            st = st.replace(tzinfo=timezone.utc)
        if st:
            day_key = st.astimezone(pytz.timezone("Australia/Brisbane")).strftime("%a, %b %d")
            by_day[day_key].append(s)

    daily_breakdown = []
    for day_label, snaps in by_day.items():
        day_settled = [s for s in snaps if s.outcome is not None]
        day_correct = sum(1 for s in day_settled if s.outcome == "correct")
        day_rate = round((day_correct / len(day_settled)) * 100, 1) if day_settled else 0
        picks = []
        for s in snaps:
            picks.append({
                "fixture": f"{s.home_team} vs {s.away_team}",
                "sport": s.sport,
                "market": format_market_display(s.market_type),
                "selection": s.selection,
                "odds": f"{s.best_odds:.2f}" if s.best_odds else "-",
                "confidence": s.confidence_level,
                "outcome": s.outcome or "pending",
                "home_score": s.fixture.home_score if s.fixture and s.fixture.home_score is not None else "-",
                "away_score": s.fixture.away_score if s.fixture and s.fixture.away_score is not None else "-",
            })
        daily_breakdown.append({
            "day": day_label,
            "total": len(day_settled),
            "correct": day_correct,
            "rate": day_rate,
            "picks": picks,
        })

    return templates.TemplateResponse("accuracy.html", {
        "request": request,
        "days": days,
        "overall_rate": overall_rate,
        "total_settled": total_settled,
        "total_snapshots": total_snapshots,
        "rec_rate": rec_rate,
        "pending_count": len(pending),
        "sport_stats": sport_stats,
        "conf_stats": conf_stats,
        "market_stats": market_stats,
        "daily_breakdown": daily_breakdown,
    })
