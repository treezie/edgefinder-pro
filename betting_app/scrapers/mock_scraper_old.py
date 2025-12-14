import asyncio
import random
import requests
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
        self.odds_fetcher = OddsAPIFetcher()  # Using demo mode (no API key)

    async def fetch_odds(self) -> List[Dict[str, Any]]:
        """
        Fetches real NFL schedule and data from ESPN.
        Returns mock NBA data with random odds when sport is NBA.
        """
        print(f"Fetching data for {self.sport}...")
        await asyncio.sleep(1)  # Simulate network delay

        fixtures: List[Dict[str, Any]] = []

        if self.sport == "NFL":
            try:
                print("Fetching real NFL schedule from ESPN...")
                # Fetch games from next 7 days
                all_events = []
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

                events = all_events
                print(f"Found {len(events)} NFL events in next 7 days.")

                for event in events:
                    # Filter out completed and in-progress games - only show scheduled/upcoming
                    status = event.get("status", {}).get("type", {}).get("state", "")
                    if status in ["post", "in"]:  # Skip completed and in-progress games
                        continue

                    fixture_name = event.get("name", "Unknown vs Unknown")
                    date_str = event.get("date")
                    try:
                        start_time = parser.parse(date_str).replace(tzinfo=timezone.utc)
                    except Exception:
                        continue

                    # Only show games that are in the future
                    if start_time < datetime.now(timezone.utc):
                        continue

                    comps = event.get("competitions", [])[0].get("competitors", [])
                        headlines: List[str] = []
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

                        # Fetch odds for both teams
                        home_odds = await self.odds_fetcher.get_odds_for_team("NFL", home_team)
                        away_odds = await self.odds_fetcher.get_odds_for_team("NFL", away_team)

                        # Get multiple bookmaker odds for comparison
                        home_bookmaker_odds = await self.odds_fetcher.get_multiple_bookmaker_odds("NFL", home_team)
                        away_bookmaker_odds = await self.odds_fetcher.get_multiple_bookmaker_odds("NFL", away_team)

                        # Add fixture for each bookmaker to get comprehensive odds data
                        for bookie_data in home_bookmaker_odds:
                            fixtures.append({
                                "fixture_name": fixture_name,
                                "start_time": start_time,
                                "market_type": "h2h",
                                "bookmaker": bookie_data["bookmaker"],
                                "sport": "NFL",
                                "league": "NFL",
                                "home_team": home_team,
                                "away_team": away_team,
                                "headlines": headlines,
                                "selection": home_team,
                                "price": bookie_data["odds"],
                                "record": home_record
                            })

                        for bookie_data in away_bookmaker_odds:
                            fixtures.append({
                                "fixture_name": fixture_name,
                                "start_time": start_time,
                                "market_type": "h2h",
                                "bookmaker": bookie_data["bookmaker"],
                                "sport": "NFL",
                                "league": "NFL",
                                "home_team": home_team,
                                "away_team": away_team,
                                "headlines": headlines,
                                "selection": away_team,
                                "price": bookie_data["odds"],
                                "record": away_record
                            })
            except Exception as e:
                print(f"Failed to fetch NFL schedule: {e}")

        elif self.sport == "NBA":
            try:
                print("Fetching real NBA schedule from ESPN...")
                response = requests.get(
                    "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
                    timeout=10,
                )
                if response.status_code == 200:
                    data = response.json()
                    events = data.get("events", [])
                    print(f"Found {len(events)} NBA events.")

                    for event in events:
                        # Filter out completed and in-progress games - only show scheduled/upcoming
                        status = event.get("status", {}).get("type", {}).get("state", "")
                        if status in ["post", "in"]:  # Skip completed and in-progress games
                            continue

                        fixture_name = event.get("name", "Unknown vs Unknown")
                        date_str = event.get("date")
                        try:
                            start_time = parser.parse(date_str).replace(tzinfo=timezone.utc)
                        except Exception:
                            continue

                        # Only show games that are in the future
                        if start_time < datetime.now(timezone.utc):
                            continue

                        comps = event.get("competitions", [])[0].get("competitors", [])
                        headlines: List[str] = []
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

                        # Fetch odds for both teams
                        home_odds = await self.odds_fetcher.get_odds_for_team("NBA", home_team)
                        away_odds = await self.odds_fetcher.get_odds_for_team("NBA", away_team)

                        # Get multiple bookmaker odds for comparison
                        home_bookmaker_odds = await self.odds_fetcher.get_multiple_bookmaker_odds("NBA", home_team)
                        away_bookmaker_odds = await self.odds_fetcher.get_multiple_bookmaker_odds("NBA", away_team)

                        # Add fixture for each bookmaker to get comprehensive odds data
                        for bookie_data in home_bookmaker_odds:
                            fixtures.append({
                                "fixture_name": fixture_name,
                                "start_time": start_time,
                                "market_type": "h2h",
                                "bookmaker": bookie_data["bookmaker"],
                                "sport": "NBA",
                                "league": "NBA",
                                "home_team": home_team,
                                "away_team": away_team,
                                "headlines": headlines,
                                "selection": home_team,
                                "price": bookie_data["odds"],
                                "record": home_record
                            })

                        for bookie_data in away_bookmaker_odds:
                            fixtures.append({
                                "fixture_name": fixture_name,
                                "start_time": start_time,
                                "market_type": "h2h",
                                "bookmaker": bookie_data["bookmaker"],
                                "sport": "NBA",
                                "league": "NBA",
                                "home_team": home_team,
                                "away_team": away_team,
                                "headlines": headlines,
                                "selection": away_team,
                                "price": bookie_data["odds"],
                                "record": away_record
                            })
            except Exception as e:
                print(f"Failed to fetch NBA schedule: {e}")
        else:
            print(f"Real data only mode. Skipping {self.sport} (No real source configured).")

        return fixtures
