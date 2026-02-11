import asyncio
import requests
from typing import List, Dict, Any
from datetime import datetime, timezone
from dateutil import parser
from .base_scraper import BaseScraper
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class NRLScraper(BaseScraper):
    def __init__(self):
        super().__init__("NRL")

    async def fetch_odds(self) -> List[Dict[str, Any]]:
        """
        Fetches real NRL schedule and data from ESPN.
        """
        print(f"Fetching data for {self.sport}...")
        await asyncio.sleep(1)  # Simulate network delay

        fixtures = []
        
        try:
            print("Fetching real NRL schedule from ESPN...")
            # ESPN Public API for Rugby League Scoreboard
            response = requests.get("http://site.api.espn.com/apis/site/v2/sports/rugby/league/nrl/scoreboard", timeout=10)
            if response.status_code == 200:
                data = response.json()
                events = data.get("events", [])
                print(f"Found {len(events)} NRL events.")
                
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
                    
                    # Check for specific headlines in the event structure
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
                        try:
                            # Basic parsing attempt for H2H
                            # ESPN often stores it as "details" like "PEN -4.0" or ML if available
                            # If direct moneyline (h2h) is available:
                            provider = odds_list[0] # Take first provider
                            if "moneyline" in provider:
                                ml = provider["moneyline"]
                                if "home" in ml: home_price = float(ml["home"]["close"]["odds"])
                                if "away" in ml: away_price = float(ml["away"]["close"]["odds"])
                                
                                # Convert American to Decimal if needed (ESPN usually gives American)
                                # Simple check: if > 50 or < -50, likely American
                                if home_price and (home_price > 50 or home_price < -50):
                                    home_price = (home_price/100 + 1) if home_price > 0 else (100/abs(home_price) + 1)
                                if away_price and (away_price > 50 or away_price < -50):
                                    away_price = (away_price/100 + 1) if away_price > 0 else (100/abs(away_price) + 1)
                        except:
                            pass

                    common_data = {
                        "fixture_name": fixture_name,
                        "start_time": start_time,
                        "market_type": "h2h",
                        "bookmaker": "ESPN (API)", 
                        "sport": "NRL",
                        "league": "NRL",
                        "home_team": home_team,
                        "away_team": away_team,
                        "headlines": headlines
                    }

                    # Only add if we successfully parsed data, or at least have a valid fixture
                    # We accept None price as "market not open"
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
            print(f"Failed to fetch NRL schedule: {e}")

        return fixtures
