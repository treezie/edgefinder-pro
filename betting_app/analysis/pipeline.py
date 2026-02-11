import asyncio
import time
from sqlalchemy.orm import Session
from database.db import SessionLocal, engine, Base
from database.models import Fixture, Odds, Sentiment, Prediction
from scrapers.mock_scraper import MockScraper
from scrapers.history_fetcher import HistoricalFetcher
from scrapers.sentiment_fetcher import SentimentFetcher
from scrapers.expert_analysis_fetcher import ExpertAnalysisFetcher
from scrapers.nfl_scraper import NFLScraper
from scrapers.nrl_scraper import NRLScraper
from scrapers.odds_api_fetcher import OddsAPIFetcher
# Horse racing removed - not being used in the app
from scrapers.team_stats_fetcher import TeamStatsFetcher
from scrapers.weather_fetcher import WeatherFetcher
from scrapers.player_stats_fetcher import PlayerStatsFetcher

class AnalysisPipeline:
    def __init__(self):
        # Ensure database schema exists
        Base.metadata.create_all(bind=engine)
        # self.db removed to ensure concurrency safety (sessions created per task)
        # We'll create fetchers per sport dynamically
        self.history_fetchers = {}
        self.sentiment_fetchers = {}
        self.expert_analyzer = ExpertAnalysisFetcher()
        self.team_stats_fetcher = TeamStatsFetcher()
        self.weather_fetcher = WeatherFetcher()
        self.player_stats_fetcher = PlayerStatsFetcher()
        self.scrapers = {
            "NFL": NFLScraper(),
            "NRL": NRLScraper(),
            "NBA": OddsAPIFetcher(api_key=None) # API key effectively loaded from env variables inside class or handled
        }

    async def run(self):
        start_time = time.time()
        print("="*60)
        print("🚀 Starting analysis pipeline (Concurrent Mode)...")
        print("="*60)

        # Process NFL, NBA, and NRL concurrently
        sports = ["NFL", "NBA", "NRL"]
        await asyncio.gather(*(self._process_sport(sport) for sport in sports))

        total_time = time.time() - start_time
        print("\n" + "="*60)
        print(f"✅ Analysis complete in {total_time:.1f} seconds")
        print(f"   Predictions saved to database")
        print("="*60)

    async def _process_sport(self, sport: str):
        sport_start = time.time()
        print(f"\n📊 Processing {sport}...")

        # Create fetchers for this sport if not exists
        if sport not in self.history_fetchers:
            self.history_fetchers[sport] = HistoricalFetcher(sport)
        if sport not in self.sentiment_fetchers:
            self.sentiment_fetchers[sport] = SentimentFetcher(sport)

        # CLEAR STALE DATA (Blocking DB call, relatively fast)
        try:
            from datetime import datetime
            
            with SessionLocal() as db:
                upcoming_fixtures = db.query(Fixture).filter(
                    Fixture.sport == sport,
                    Fixture.start_time > datetime.utcnow()
                ).all()
                
                fixture_ids = [f.id for f in upcoming_fixtures]
                
                if fixture_ids:
                    db.query(Odds).filter(Odds.fixture_id.in_(fixture_ids)).delete(synchronize_session=False)
                    db.query(Prediction).filter(Prediction.fixture_id.in_(fixture_ids)).delete(synchronize_session=False)
                    db.commit()
                    print(f"   🧹 Cleared stale data for {len(fixture_ids)} upcoming {sport} fixtures")
        except Exception as e:
            print(f"   ⚠️ Error clearing stale data: {e}")

        # NETWORK I/O (Async - No DB lock)
        try:
            # Use the appropriate scraper for this sport
            if sport in self.scrapers:
                scraper = self.scrapers[sport]
            else:
                scraper = MockScraper(sport)
            
            odds_data = await asyncio.wait_for(scraper.fetch_odds(), timeout=300.0)
            print(f"   ✅ Fetched {len(odds_data)} entries for {sport}")
        except Exception as e:
            print(f"   ❌ Error fetching {sport} odds: {e}")
            return

        # Group odds by fixture and market for analysis
        grouped_odds = self._group_odds(odds_data)
        print(f"   Processing {len(grouped_odds)} betting opportunities for {sport}...")

        # Process fixtures concurrently with a semaphore
        semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent games per sport to respect API limits

        async def process_with_semaphore(item_data):
            async with semaphore:
                await self._analyze_fixture(sport, item_data)

        # Run tasks
        tasks = [process_with_semaphore(items) for items in grouped_odds.values()]
        await asyncio.gather(*tasks)
        
        print(f"   ✅ Finished {sport} in {time.time() - sport_start:.1f}s")

    async def _analyze_fixture(self, sport, items):
        """
        Analyzes a single fixture.
        CRITICAL: Do NOT hold a DB session open while awaiting network calls.
        """
        try:
            first_item = items[0]
            
            # --- PHASE 1: PRE-FETCH DATA (Network I/O - NO DB SESSION) ---
            # Gather all necessary data concurrently before touching the DB
            
            record_data = first_item.get("record")
            is_home = (first_item["selection"] == first_item["home_team"])
            opponent = first_item["away_team"] if is_home else first_item["home_team"]

            # Define tasks
            task_history = self.history_fetchers[sport].get_team_stats(first_item["selection"], record_data)
            task_sentiment = self.sentiment_fetchers[sport].analyze_sentiment(first_item["fixture_name"], first_item.get("headlines", []))
            task_expert = self.expert_analyzer.get_comprehensive_analysis(
                team_name=first_item["selection"],
                opponent=opponent,
                sport=sport,
                record=record_data,
                is_home=is_home
            )
            task_team_stats = self.team_stats_fetcher.get_team_stats(first_item["selection"], sport)
            task_players = self.player_stats_fetcher.get_top_players(first_item["selection"], sport, limit=3)
            
            task_weather = None
            if sport == "NFL":
                task_weather = self.weather_fetcher.get_game_weather(first_item["home_team"], first_item["start_time"])
            
            # H2H Opponent stats (needed for calculation logic later)
            task_opp_stats = None
            if first_item.get("market_type") == "h2h":
                task_opp_stats = self.history_fetchers[sport].get_team_stats(opponent)

            # Execute concurrent network fetches
            results = await asyncio.gather(
                task_history, 
                task_sentiment, 
                task_expert, 
                task_team_stats, 
                task_players, 
                task_weather if task_weather else asyncio.sleep(0),
                task_opp_stats if task_opp_stats else asyncio.sleep(0)
            )
            
            stats, sentiment, expert_analysis, team_stats, key_players, weather_data, opp_stats = results
            
            if not task_weather: weather_data = None
            if not task_opp_stats: opp_stats = None

            # --- PHASE 2: CALCULATIONS (CPU Bound - Fast, safe) ---
            
            win_rate = stats["win_rate"]
            sent_score = sentiment["sentiment_score"]
            
            base_prob = win_rate
            if opp_stats:
                opp_win_rate = opp_stats["win_rate"]
                total_strength = win_rate + opp_win_rate
                if total_strength > 0:
                    base_prob = win_rate / total_strength
                else:
                    base_prob = 0.5

            sentiment_adj = sent_score * 0.05
            expert_adj = (expert_analysis["confidence_score"] / 100) * 0.15
            
            home_adj = 0
            if is_home and expert_analysis["h2h_analysis"]["home_field_advantage"] > 50:
                home_adj = (expert_analysis["h2h_analysis"]["home_field_advantage"] - 50) / 1000

            true_prob = base_prob + sentiment_adj + expert_adj + home_adj
            true_prob = max(0.01, min(0.99, true_prob))

            all_prices = [item.get("price") for item in items if item.get("price")]
            best_price = max(all_prices) if all_prices else None
            avg_price = sum(all_prices) / len(all_prices) if all_prices else None
            best_bookmaker = next((item["bookmaker"] for item in items if item.get("price") == best_price), "Unknown")

            value = 0.0
            if best_price is not None:
                if 1.01 <= best_price <= 50.0:
                    value = (true_prob * best_price) - 1

            if value > 2.0: return # Reject bad data

            # Reasoning Generation (String building)
            reasoning_lines = []
            reasoning_lines.append(f"**{first_item['selection']}** ({record_data})")
            
            if len(items) > 1 and avg_price:
                reasoning_lines.append(f"Win Probability: {true_prob*100:.1f}% | Best Odds: {best_price} ({best_bookmaker})")
                reasoning_lines.append(f"Avg Odds: {avg_price:.2f} across {len(items)} bookmakers")
            else:
                reasoning_lines.append(f"Win Probability: {true_prob*100:.1f}% | Odds: {best_price} ({best_bookmaker})")

            betting_trends = expert_analysis["betting_trends"]
            reasoning_lines.append(f"\n**Betting Trends:** Type: {betting_trends['trend_strength']}")
            
            reasoning_lines.append("\n**Analysis:**")
            for point in expert_analysis["reasoning_points"][:3]:
                reasoning_lines.append(f"  {point}")

            injury_analysis = expert_analysis["injury_analysis"]
            if injury_analysis["impact"] != "Minimal":
                out_players = [p for p in injury_analysis.get("injured_players", []) if p.get("status") == "OUT"]
                if out_players:
                    reasoning_lines.append(f"\n**Injury Report:** {len(out_players)} OUT")
                    for p in out_players[:3]: 
                         reasoning_lines.append(f"  • {p.get('name', p.get('position'))} (OUT)")

            if team_stats.get("available"):
                reasoning_lines.append(f"\n**stats (ESPN):** PPG: {team_stats.get('points_per_game', 0):.1f}")

            if weather_data and weather_data.get("available"):
                reasoning_lines.append(f"\n**Weather:** {weather_data.get('conditions')} at {weather_data.get('stadium')}")

            if key_players:
                reasoning_lines.append(f"\n**Key Players:**")
                for p in key_players:
                    reasoning_lines.append(f"  • {p['name']} ({p['position']})")

            if value > 0:
                reasoning_lines.append(f"\n**Value:** {value:.2f} edge")

            reasoning_text = "\n".join(reasoning_lines)

            confidence = "Low"
            if best_price:
                if value > 0.12 and true_prob > 0.45: confidence = "High"
                elif value > 0.05 and true_prob > 0.40: confidence = "Medium"
            else:
                if true_prob > 0.65: confidence = "High"
                elif true_prob > 0.50: confidence = "Medium"

            is_adj_rec = (value > 0.03 if best_price else true_prob > 0.55)

            # --- PHASE 3: DATABASE WRITES (Blocking, but grouped and fast) ---
            # Now we open the session, do all writes, and close immediately.
            
            with SessionLocal() as db:
                # 1. Get/Create Fixture
                fixture = (
                    db.query(Fixture)
                    .filter_by(
                        home_team=first_item["home_team"],
                        away_team=first_item["away_team"],
                        start_time=first_item["start_time"],
                    )
                    .first()
                )
                if not fixture:
                    fixture = Fixture(
                        fixture_name=first_item["fixture_name"],
                        sport=first_item["sport"],
                        league=first_item["league"],
                        home_team=first_item["home_team"],
                        away_team=first_item["away_team"],
                        start_time=first_item["start_time"],
                    )
                    db.add(fixture)
                    db.flush() 
                    db.refresh(fixture)

                # 2. Add Odds
                for item in items:
                    odds_entry = Odds(
                        fixture_id=fixture.id,
                        bookmaker=item["bookmaker"],
                        market_type=item["market_type"],
                        selection=item["selection"],
                        price=item.get("price"),
                        point=item.get("point"),
                    )
                    db.add(odds_entry)
                
                # 3. Add/Update Prediction
                existing_prediction = (
                    db.query(Prediction)
                    .filter_by(
                        fixture_id=fixture.id,
                        market_type=first_item["market_type"],
                        selection=first_item["selection"]
                    )
                    .first()
                )

                if existing_prediction:
                    existing_prediction.model_probability = true_prob
                    existing_prediction.value_score = value
                    existing_prediction.confidence_level = confidence
                    existing_prediction.reasoning = reasoning_text
                    existing_prediction.is_recommended = is_adj_rec
                else:
                    prediction = Prediction(
                        fixture_id=fixture.id,
                        market_type=first_item["market_type"],
                        selection=first_item["selection"],
                        model_probability=true_prob,
                        value_score=value,
                        confidence_level=confidence,
                        reasoning=reasoning_text,
                        is_recommended=is_adj_rec,
                    )
                    db.add(prediction)
                
                # Commit everything at once
                db.commit()

        except Exception as e:
            print(f"   ❌ Error analyzing {items[0]['selection']}: {e}")
            # No rollback needed manually as 'with SessionLocal' handles cleanup on exception (if configured)
            # but standard Session context manager rolls back on error.
            
    def _group_odds(self, odds_data):
        """Group odds data by fixture, market and selection"""
        from collections import defaultdict
        grouped_data = defaultdict(list)

        for item in odds_data:
            key = (item.get("fixture_name", "Unknown"), item.get("market_type", "h2h"), item["selection"])
            grouped_data[key].append(item)
            
        return grouped_data

if __name__ == "__main__":
    pipeline = AnalysisPipeline()
    asyncio.run(pipeline.run())
