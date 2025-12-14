import asyncio
import requests
from typing import List, Dict, Any
from datetime import datetime, timezone
from dateutil import parser
from .base_scraper import BaseScraper
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class NFLScraper(BaseScraper):
    def __init__(self):
        super().__init__("NFL")

    async def fetch_odds(self) -> List[Dict[str, Any]]:
        """
        Fetches real NFL schedule and data from ESPN.
        """
        print(f"Fetching data for {self.sport}...")
        await asyncio.sleep(1) # Simulate network delay

        fixtures = []
        
        try:
            print("Fetching real NFL schedule from ESPN...")
            # ESPN Public API for NFL Scoreboard
            response = requests.get("http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard", timeout=10)
            if response.status_code == 200:
                data = response.json()
                events = data.get("events", [])
                print(f"Found {len(events)} NFL events.")
                
                for event in events:
                    fixture_name = event.get("name", "Unknown vs Unknown")
                    date_str = event.get("date")
                    
                    try:
                        start_time = parser.parse(date_str).replace(tzinfo=timezone.utc)
                    except:
                        continue

                    # Extract competitors and headlines
                    comps = event.get("competitions", [])[0].get("competitors", [])
                    headlines = []
                    
                    # Check for specific headlines in the event structure (often under 'competitions' -> 'headlines')
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
                    
                    # Try to find odds if available in the ESPN response
                    # Sometimes odds are in competitions -> odds
                    odds_list = event.get("competitions", [])[0].get("odds", [])
                    home_price = None
                    away_price = None
                    
                    if odds_list:
                        # This is a simplification. ESPN odds structure can vary.
                        # Usually it gives a 'details' string like "BUF -3.0" or "O/U 45.5"
                        # It might not give raw moneyline odds directly in this endpoint easily.
                        # We will stick to None for price unless we find explicit moneyline.
                        pass

                    common_data = {
                        "fixture_name": fixture_name,
                        "start_time": start_time,
                        "market_type": "h2h",
                        "bookmaker": "ESPN (API)", 
                        "sport": "NFL",
                        "league": "NFL",
                        "home_team": home_team,
                        "away_team": away_team,
                        "headlines": headlines
                    }

                    fixtures.append({
                        **common_data,
                        "selection": home_team,
                        "price": home_price,
                        "record": home_record
                    })
                    fixtures.append({
                        **common_data,
                        "selection": away_team,
                        "price": away_price,
                        "record": away_record
                    })
        except Exception as e:
            print(f"Failed to fetch NFL schedule: {e}")

        return fixtures
