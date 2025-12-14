import asyncio
import time
from sqlalchemy.orm import Session
from database.db import SessionLocal, engine, Base
from database.models import Fixture, Odds, Sentiment, Prediction
from scrapers.mock_scraper import MockScraper
from scrapers.history_fetcher import HistoricalFetcher
from scrapers.sentiment_fetcher import SentimentFetcher
from scrapers.expert_analysis_fetcher import ExpertAnalysisFetcher
# Horse racing removed - not being used in the app
from scrapers.team_stats_fetcher import TeamStatsFetcher
from scrapers.weather_fetcher import WeatherFetcher
from scrapers.player_stats_fetcher import PlayerStatsFetcher

class AnalysisPipeline:
    def __init__(self):
        # Ensure database schema exists
        Base.metadata.create_all(bind=engine)
        self.db: Session = SessionLocal()
        # We'll create fetchers per sport dynamically
        self.history_fetchers = {}
        self.sentiment_fetchers = {}
        self.expert_analyzer = ExpertAnalysisFetcher()
        self.team_stats_fetcher = TeamStatsFetcher()
        self.weather_fetcher = WeatherFetcher()
        self.player_stats_fetcher = PlayerStatsFetcher()

    async def run(self):
        start_time = time.time()
        print("="*60)
        print("🚀 Starting analysis pipeline...")
        print("="*60)

        # Horse racing removed - not being used in the app
        # await self._process_horse_racing()

        # Process both NFL and NBA with real data
        sports = ["NFL", "NBA"]
        for sport in sports:
            sport_start = time.time()
            print(f"\n📊 Processing {sport}...")

            # Create fetchers for this sport if not exists
            if sport not in self.history_fetchers:
                self.history_fetchers[sport] = HistoricalFetcher(sport)
            if sport not in self.sentiment_fetchers:
                self.sentiment_fetchers[sport] = SentimentFetcher(sport)

            try:
                scraper = MockScraper(sport)
                # Add timeout for fetching odds (Increased to 300s for web scraping)
                odds_data = await asyncio.wait_for(scraper.fetch_odds(), timeout=300.0)
                print(f"   ✅ Fetched {len(odds_data)} entries for {sport} ({time.time() - sport_start:.1f}s)")
            except asyncio.TimeoutError:
                print(f"   ⚠️ Timeout fetching {sport} odds - skipping")
                continue
            except Exception as e:
                print(f"   ❌ Error fetching {sport} odds: {e}")
                continue

            # Group odds data by fixture and selection to consolidate
            from collections import defaultdict
            grouped_data = defaultdict(list)

            # Group odds by fixture and market for analysis
            grouped_odds = self._group_odds(odds_data)
            print(f"DEBUG: Processing {len(grouped_odds)} grouped betting opportunities for {sport}")

            for (fixture_name, market_type, selection), items in grouped_odds.items():
                first_item = items[0]
                
                
                # Create or get fixture
                fixture = (
                    self.db.query(Fixture)
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
                    self.db.add(fixture)
                    self.db.commit()
                    self.db.refresh(fixture)

                # Save all odds from different bookmakers
                for item in items:
                    odds_entry = Odds(
                        fixture_id=fixture.id,
                        bookmaker=item["bookmaker"],
                        market_type=item["market_type"],
                        selection=item["selection"],
                        price=item.get("price"),
                        point=item.get("point"),  # For spreads and totals
                    )
                    self.db.add(odds_entry)

                # Calculate best and average odds across all bookmakers
                all_prices = [item.get("price") for item in items if item.get("price")]
                best_price = max(all_prices) if all_prices else None
                avg_price = sum(all_prices) / len(all_prices) if all_prices else None
                best_bookmaker = next((item["bookmaker"] for item in items if item.get("price") == best_price), "Unknown")

                # Analyze with real data - using historical records and sentiment
                record_data = first_item.get("record")
                stats = await self.history_fetchers[sport].get_team_stats(first_item["selection"], record_data)
                win_rate = stats["win_rate"]
                form_desc = stats.get("form_desc", "")

                headlines = first_item.get("headlines", [])
                sentiment = await self.sentiment_fetchers[sport].analyze_sentiment(first_item["fixture_name"], headlines)
                sent_score = sentiment["sentiment_score"]

                # Get comprehensive expert analysis
                is_home = (first_item["selection"] == first_item["home_team"])
                opponent = first_item["away_team"] if is_home else first_item["home_team"]

                expert_analysis = await self.expert_analyzer.get_comprehensive_analysis(
                    team_name=first_item["selection"],
                    opponent=opponent,
                    sport=sport,
                    record=record_data,
                    is_home=is_home
                )

                # Fetch real team statistics from ESPN API
                team_stats = await self.team_stats_fetcher.get_team_stats(
                    first_item["selection"],
                    sport
                )

                # Fetch weather data for NFL games (outdoor stadiums only)
                weather_data = None
                if sport == "NFL":
                    weather_data = await self.weather_fetcher.get_game_weather(
                        first_item["home_team"],
                        first_item["start_time"]
                    )

                # Fetch key player statistics for this team
                key_players = await self.player_stats_fetcher.get_top_players(
                    first_item["selection"],
                    sport,
                    limit=3
                )

                # Calculate true probability with weighted factors
                base_prob = win_rate  # Default base probability from historical win rate
                
                # Normalize probability for H2H matchups (accounting for opponent strength)
                if first_item.get("market_type") == "h2h":
                    opponent_stats = await self.history_fetchers[sport].get_team_stats(opponent)
                    opp_win_rate = opponent_stats["win_rate"]
                    
                    # Bradley-Terry-like normalization: P(A) = WA / (WA + WB)
                    total_strength = win_rate + opp_win_rate
                    if total_strength > 0:
                        base_prob = win_rate / total_strength
                    else:
                        base_prob = 0.5 # Default if both have 0 win rate (rare with simulation)

                sentiment_adj = sent_score * 0.05  # Sentiment (5% weight)
                expert_adj = (expert_analysis["confidence_score"] / 100) * 0.15  # Expert analysis (15% weight)

                # Adjust for home/away
                if is_home and expert_analysis["h2h_analysis"]["home_field_advantage"] > 50:
                    home_adj = (expert_analysis["h2h_analysis"]["home_field_advantage"] - 50) / 1000  # Small boost
                else:
                    home_adj = 0
                
                true_prob = base_prob + sentiment_adj + expert_adj + home_adj
                true_prob = max(0.01, min(0.99, true_prob))

                # Calculate value using best odds available
                value = 0.0
                if best_price is not None:
                    # Validate odds are reasonable before calculating value
                    if best_price < 1.01 or best_price > 50.0:
                        continue

                    value = (true_prob * best_price) - 1

                    # Reject absurd value scores (indicates fake/bad data)
                    if value > 2.0:
                        continue

                # Build comprehensive reasoning with detailed expert analysis
                reasoning_lines = []
                reasoning_lines.append(f"**{first_item['selection']}** ({record_data})")

                # Show best odds and bookmaker comparison
                if len(items) > 1 and avg_price:
                    reasoning_lines.append(f"Win Probability: {true_prob*100:.1f}% | Best Odds: {best_price} ({best_bookmaker})")
                    reasoning_lines.append(f"Avg Odds: {avg_price:.2f} across {len(items)} bookmakers")
                else:
                    reasoning_lines.append(f"Win Probability: {true_prob*100:.1f}% | Odds: {best_price} ({best_bookmaker})")

                # Add betting trends and expert consensus
                betting_trends = expert_analysis["betting_trends"]
                reasoning_lines.append(f"\n**Betting Trends:**")
                reasoning_lines.append(f"  Public Betting: {betting_trends['public_betting_percentage']}% on this pick")
                reasoning_lines.append(f"  Expert Consensus: {betting_trends['expert_consensus']}% ({betting_trends['trend_strength']})")
                reasoning_lines.append(f"  Sharp Money: {betting_trends['sharp_money']}")

                # Add expert insights
                reasoning_lines.append("\n**Analysis:**")
                for point in expert_analysis["reasoning_points"][:4]:  # Top 4 points for more detail
                    reasoning_lines.append(f"  {point}")

                # Add form and momentum analysis
                form_analysis = expert_analysis["form_analysis"]
                reasoning_lines.append(f"\n**Recent Form:** {form_analysis['current_form']} ({form_analysis['last_5_games']} in L5)")
                reasoning_lines.append(f"  Momentum: {form_analysis['momentum']}")

                # Add injury impact with detailed player information - ONLY OUT players
                injury_analysis = expert_analysis["injury_analysis"]
                if injury_analysis["impact"] != "Minimal":
                    # Filter to only show players with OUT status
                    out_players = [p for p in injury_analysis.get("injured_players", []) if p.get("status") == "OUT"]

                    if out_players:
                        reasoning_lines.append(f"\n**Injury Report:** {len(out_players)} player{'s' if len(out_players) != 1 else ''} ruled OUT")

                        # List specific injured players - ONLY OUT status
                        for player_info in out_players:
                            # Show player name if available (real data), otherwise just position
                            if "name" in player_info:
                                reasoning_lines.append(f"  • {player_info['name']} ({player_info['position']}): OUT - {player_info['injury']}")
                            else:
                                reasoning_lines.append(f"  • {player_info['position']}: OUT - {player_info['injury']}")

                # Add team statistics (real data from ESPN)
                if team_stats.get("available") and team_stats.get("available") != False:
                    reasoning_lines.append(f"\n**Team Statistics (ESPN):**")
                    if sport == "NFL":
                        if team_stats.get("points_per_game", 0) > 0:
                            reasoning_lines.append(f"  Offense: {team_stats['points_per_game']:.1f} PPG, {team_stats.get('total_yards_per_game', 0):.1f} YPG")
                            reasoning_lines.append(f"  Passing: {team_stats.get('passing_yards_per_game', 0):.1f} YPG | Rushing: {team_stats.get('rushing_yards_per_game', 0):.1f} YPG")
                        if team_stats.get("points_against_per_game", 0) > 0:
                            reasoning_lines.append(f"  Defense: {team_stats['points_against_per_game']:.1f} PPG allowed")
                    elif sport == "NBA":
                        if team_stats.get("points_per_game", 0) > 0:
                            reasoning_lines.append(f"  Offense: {team_stats['points_per_game']:.1f} PPG, {team_stats.get('field_goal_pct', 0):.1f}% FG")
                            reasoning_lines.append(f"  3PT%: {team_stats.get('three_point_pct', 0):.1f}% | Assists: {team_stats.get('assists_per_game', 0):.1f} APG")
                            reasoning_lines.append(f"  Rebounds: {team_stats.get('rebounds_per_game', 0):.1f} RPG")

                # Add weather impact for NFL outdoor games
                if weather_data and weather_data.get("available"):
                    reasoning_lines.append(f"\n**Weather Conditions at {weather_data['stadium']}:**")
                    if weather_data.get("indoor"):
                        reasoning_lines.append(f"  {weather_data['conditions']} - {weather_data['impact']}")
                    else:
                        reasoning_lines.append(f"  Temperature: {weather_data['temperature']} | Wind: {weather_data.get('wind_description', 'N/A')}")
                        reasoning_lines.append(f"  Conditions: {weather_data['conditions']}")
                        reasoning_lines.append(f"  Impact: {weather_data['impact']}")

                # Add key players section
                if key_players and len(key_players) > 0:
                    reasoning_lines.append(f"\n**Key Players:**")
                    for player in key_players:
                        player_line = f"  • {player['name']}"
                        if player.get('jersey'):
                            player_line += f" (#{player['jersey']})"
                        player_line += f" - {player['position']}"
                        if player.get('stat_desc'):
                            player_line += f": {player['stat_desc']}"
                        reasoning_lines.append(player_line)

                # Add value assessment
                if best_price is not None:
                    if value > 0.1:
                        reasoning_lines.append(f"\n**Value:** Strong edge detected ({value:.2f})")
                    elif value > 0:
                        reasoning_lines.append(f"\n**Value:** Positive value ({value:.2f})")
                    else:
                        reasoning_lines.append(f"\n**Value:** No edge ({value:.2f})")

                # Add sentiment analysis with headlines
                if headlines:
                    reasoning_lines.append(f"\n**Recent Headlines ({len(headlines)}):**")
                    for headline in headlines[:2]:  # Show top 2 headlines
                        reasoning_lines.append(f"  • \"{headline}\"")
                    reasoning_lines.append(f"  Sentiment Score: {sent_score:.2f}")

                # Add sources
                sources_str = ", ".join(expert_analysis["sources_consulted"][:3])
                reasoning_lines.append(f"\n*Sources: {sources_str}*")

                reasoning_text = "\n".join(reasoning_lines)

                # Determine confidence based on multiple factors
                confidence = "Low"
                if best_price is not None:
                    # Balance value with probability
                    if value > 0.12 and true_prob > 0.45:
                        confidence = "High"
                    elif value > 0.05 and true_prob > 0.40:
                        confidence = "Medium"
                else:
                    if true_prob > 0.65:
                        confidence = "High"
                    elif true_prob > 0.50:
                        confidence = "Medium"

                # Calculate value (Edge)
                # Value = (True Probability * Decimal Odds) - 1
                # This value calculation is already done above, but the instruction implies it should be here.
                # Re-evaluating the instruction, it seems to be a misplaced snippet or a request to move/duplicate.
                # Given the context, the instruction seems to want to add a debug print and define `is_recommended`
                # before the database check, using the `value` and `true_prob` already calculated.

                # Determine if recommended
                # Recommended if positive EV > 3% OR high probability > 55%
                is_adj_rec = (value > 0.03 if best_price else true_prob > 0.55)

                # Check if prediction already exists for this fixture/market/selection
                existing_prediction = (
                    self.db.query(Prediction)
                    .filter_by(
                        fixture_id=fixture.id,
                        market_type=first_item["market_type"],
                        selection=first_item["selection"]
                    )
                    .first()
                )

                if existing_prediction:
                    # Update existing prediction with new data
                    existing_prediction.model_probability = true_prob
                    existing_prediction.value_score = value
                    existing_prediction.confidence_level = confidence
                    existing_prediction.reasoning = reasoning_text
                    existing_prediction.is_recommended = (value > 0.03 if best_price else true_prob > 0.55)
                else:
                    # Create new prediction
                    prediction = Prediction(
                        fixture_id=fixture.id,
                        market_type=first_item["market_type"],
                        selection=first_item["selection"],
                        model_probability=true_prob,
                        value_score=value,
                        confidence_level=confidence,
                        reasoning=reasoning_text,
                        is_recommended=(value > 0.03 if best_price else true_prob > 0.55),
                    )
                    self.db.add(prediction)

            print(f"   ✅ Processed {len(grouped_data)} bets for {sport} ({time.time() - sport_start:.1f}s)")

        self.db.commit()
        total_time = time.time() - start_time
        print("\n" + "="*60)
        print(f"✅ Analysis complete in {total_time:.1f} seconds")
        print(f"   Predictions saved to database")
        print("="*60)


    def _group_odds(self, odds_data):
        """Group odds data by fixture, market and selection"""
        from collections import defaultdict
        grouped_data = defaultdict(list)

        for item in odds_data:
            # Key: (Fixture Name, Market Type, Selection)
            # This ensures we group multiple bookmakers for the exact same bet
            key = (item.get("fixture_name", "Unknown"), item.get("market_type", "h2h"), item["selection"])
            grouped_data[key].append(item)
            
        return grouped_data

if __name__ == "__main__":
    pipeline = AnalysisPipeline()
    asyncio.run(pipeline.run())


if __name__ == "__main__":
    pipeline = AnalysisPipeline()
    asyncio.run(pipeline.run())
