import asyncio
import requests
import os
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone
from dateutil import parser
from .base_scraper import BaseScraper
from .odds_api_fetcher import OddsAPIFetcher
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class MockScraper(BaseScraper):
    def __init__(self, sport: str):
        super().__init__(sport)
        api_key = os.getenv('ODDS_API_KEY')
        self.odds_fetcher = OddsAPIFetcher(api_key=api_key)

        if api_key:
            print(f"✓ Odds API Key loaded for {sport}")
        else:
            print(f"⚠ No Odds API Key - will use ESPN fallback for {sport}")

    async def fetch_odds(self) -> List[Dict[str, Any]]:
        """
        Fetches real NFL/NBA schedule and data from ESPN for upcoming games only.
        """
        print(f"Fetching data for {self.sport}...")
        await asyncio.sleep(1)  # Simulate network delay

        fixtures: List[Dict[str, Any]] = []

        if self.sport == "NFL":
            fixtures = await self._fetch_nfl_games()
        elif self.sport == "NBA":
            fixtures = await self._fetch_nba_games()
        else:
            print(f"Real data only mode. Skipping {self.sport} (No real source configured).")

        return fixtures

    async def _fetch_nfl_games(self) -> List[Dict[str, Any]]:
        """Fetch upcoming NFL games from next 7 days"""
        fixtures = []
        try:
            print("Fetching real NFL schedule from ESPN...")
            all_events = []
            
            # Fetch games from next 7 days
            for days_ahead in range(7):
                check_date = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).strftime('%Y%m%d')
                response = requests.get(
                    f"http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={check_date}",
                    timeout=10,
                )
                if response.status_code == 200:
                    data = response.json()
                    day_events = data.get("events", [])
                    all_events.extend(day_events)

            print(f"Found {len(all_events)} total NFL events in next 7 days.")
            
            for event in all_events:
                # Only process scheduled upcoming games
                status = event.get("status", {}).get("type", {}).get("state", "")
                if status in ["post", "in"]:
                    continue

                fixture_name = event.get("name", "Unknown vs Unknown")
                date_str = event.get("date")
                
                try:
                    start_time = parser.parse(date_str).replace(tzinfo=timezone.utc)
                except Exception:
                    continue

                # Only future games
                if start_time < datetime.now(timezone.utc):
                    continue

                comps = event.get("competitions", [])[0].get("competitors", [])
                headlines = []
                event_headlines = event.get("competitions", [])[0].get("headlines", [])
                for h in event_headlines:
                    headlines.append(h.get("description", "") or h.get("shortLinkText", ""))

                home_team = "Unknown"
                away_team = "Unknown"
                home_record = "0-0"
                away_record = "0-0"
                
                for comp in comps:
                    team_name = comp.get("team", {}).get("displayName", "Unknown")
                    records = comp.get("records", [])
                    record_summary = "0-0"
                    for r in records:
                        if r.get("type") == "total":
                            record_summary = r.get("summary")
                            break
                    if comp.get("homeAway") == "home":
                        home_team = team_name
                        home_record = record_summary
                    else:
                        away_team = team_name
                        away_record = record_summary

                # Get odds for all markets (h2h, spreads, totals)
                all_market_odds = await self.odds_fetcher.get_all_markets_for_game("NFL", home_team, away_team)

                # Add fixture for each market/bookmaker combination
                for odds_data in all_market_odds:
                    # Determine which record to use based on selection
                    record = home_record if odds_data['selection'] == home_team else away_record if odds_data['selection'] == away_team else None

                    fixtures.append({
                        "fixture_name": fixture_name,
                        "start_time": start_time,
                        "market_type": odds_data['market_type'],
                        "bookmaker": odds_data['bookmaker'],
                        "sport": "NFL",
                        "league": "NFL",
                        "home_team": home_team,
                        "away_team": away_team,
                        "headlines": headlines,
                        "selection": odds_data['selection'],
                        "price": odds_data['price'],
                        "point": odds_data['point'],
                        "record": record
                    })
                    
            print(f"Processed {len(fixtures)} NFL bet options from scheduled games.")
        except Exception as e:
            print(f"Failed to fetch NFL schedule: {e}")

        return fixtures

    async def _fetch_nba_games(self) -> List[Dict[str, Any]]:
        """Fetch upcoming NBA games from next 3 days"""
        fixtures = []
        try:
            print("Fetching real NBA schedule from ESPN...")
            all_events = []
            
            # Fetch games from next 3 days
            for days_ahead in range(3):
                check_date = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).strftime('%Y%m%d')
                response = requests.get(
                    f"http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={check_date}",
                    timeout=10,
                )
                if response.status_code == 200:
                    data = response.json()
                    day_events = data.get("events", [])
                    all_events.extend(day_events)

            print(f"Found {len(all_events)} total NBA events in next 3 days.")
            
            for event in all_events:
                # Only process scheduled upcoming games
                status = event.get("status", {}).get("type", {}).get("state", "")
                if status in ["post", "in"]:
                    continue

                fixture_name = event.get("name", "Unknown vs Unknown")
                date_str = event.get("date")
                
                try:
                    start_time = parser.parse(date_str).replace(tzinfo=timezone.utc)
                except Exception:
                    continue

                # Only future games
                if start_time < datetime.now(timezone.utc):
                    continue

                comps = event.get("competitions", [])[0].get("competitors", [])
                headlines = []
                event_headlines = event.get("competitions", [])[0].get("headlines", [])
                for h in event_headlines:
                    headlines.append(h.get("description", "") or h.get("shortLinkText", ""))

                home_team = "Unknown"
                away_team = "Unknown"
                home_record = "0-0"
                away_record = "0-0"
                
                for comp in comps:
                    team_name = comp.get("team", {}).get("displayName", "Unknown")
                    records = comp.get("records", [])
                    record_summary = "0-0"
                    for r in records:
                        if r.get("type") == "total":
                            record_summary = r.get("summary")
                            break
                    if comp.get("homeAway") == "home":
                        home_team = team_name
                        home_record = record_summary
                    else:
                        away_team = team_name
                        away_record = record_summary

                # Get odds for all markets (h2h, spreads, totals)
                all_market_odds = await self.odds_fetcher.get_all_markets_for_game("NBA", home_team, away_team)

                # Add fixture for each market/bookmaker combination
                for odds_data in all_market_odds:
                    # Determine which record to use based on selection
                    record = home_record if odds_data['selection'] == home_team else away_record if odds_data['selection'] == away_team else None

                    fixtures.append({
                        "fixture_name": fixture_name,
                        "start_time": start_time,
                        "market_type": odds_data['market_type'],
                        "bookmaker": odds_data['bookmaker'],
                        "sport": "NBA",
                        "league": "NBA",
                        "home_team": home_team,
                        "away_team": away_team,
                        "headlines": headlines,
                        "selection": odds_data['selection'],
                        "price": odds_data['price'],
                        "point": odds_data['point'],
                        "record": record
                    })
                    
            print(f"Processed {len(fixtures)} NBA bet options from scheduled games.")
        except Exception as e:
            print(f"Failed to fetch NBA schedule: {e}")

        return fixtures
