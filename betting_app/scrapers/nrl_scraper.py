import asyncio
import os
import requests
import feedparser
from typing import List, Dict, Any
from datetime import datetime, timezone
from dateutil import parser
from .base_scraper import BaseScraper
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# NRL nickname -> full team name mapping (NRL.com uses nicknames, Odds API uses full names)
NRL_TEAM_MAP = {
    "Knights": "Newcastle Knights",
    "Cowboys": "North Queensland Cowboys",
    "Storm": "Melbourne Storm",
    "Warriors": "New Zealand Warriors",
    "Roosters": "Sydney Roosters",
    "Broncos": "Brisbane Broncos",
    "Panthers": "Penrith Panthers",
    "Sharks": "Cronulla Sutherland Sharks",
    "Sea Eagles": "Manly Warringah Sea Eagles",
    "Titans": "Gold Coast Titans",
    "Raiders": "Canberra Raiders",
    "Dolphins": "Dolphins",
    "Rabbitohs": "South Sydney Rabbitohs",
    "Eels": "Parramatta Eels",
    "Dragons": "St George Illawarra Dragons",
    "Bulldogs": "Canterbury Bulldogs",
    "Tigers": "Wests Tigers",
}

# Reverse mapping for lookups
NRL_FULL_TO_NICK = {v.lower(): k for k, v in NRL_TEAM_MAP.items()}


def resolve_nrl_team_name(name: str) -> str:
    """Resolve a nickname or partial name to full NRL team name."""
    if not name:
        return name
    # Already a full name?
    for full in NRL_TEAM_MAP.values():
        if name.lower() == full.lower():
            return full
    # Try nickname lookup
    if name in NRL_TEAM_MAP:
        return NRL_TEAM_MAP[name]
    # Fuzzy: check if nickname is contained in the name
    for nick, full in NRL_TEAM_MAP.items():
        if nick.lower() in name.lower():
            return full
    return name


class NRLScraper(BaseScraper):
    def __init__(self):
        super().__init__("NRL")
        self.odds_api_key = os.getenv('ODDS_API_KEY')

    async def fetch_odds(self) -> List[Dict[str, Any]]:
        """
        Fetches real NRL fixtures and odds.
        Primary: The Odds API (rugbyleague_nrl) for h2h, spreads, totals
        Fallback: NRL.com Draw API for fixtures + built-in odds
        Headlines: Zero Tackle RSS for sentiment analysis
        """
        print(f"Fetching data for {self.sport}...")

        fixtures = []

        # 1. Fetch headlines from Zero Tackle RSS (for sentiment)
        headlines = await self._fetch_nrl_headlines()

        # 2. Primary: The Odds API
        if self.odds_api_key:
            odds_api_fixtures = await self._fetch_from_odds_api(headlines)
            if odds_api_fixtures:
                print(f"  Got {len(odds_api_fixtures)} NRL fixture entries from Odds API")
                fixtures.extend(odds_api_fixtures)
                return fixtures

        # 3. Fallback: NRL.com Draw API
        print("  Falling back to NRL.com Draw API...")
        nrl_com_fixtures = await self._fetch_from_nrl_draw(headlines)
        if nrl_com_fixtures:
            print(f"  Got {len(nrl_com_fixtures)} NRL fixture entries from NRL.com")
            fixtures.extend(nrl_com_fixtures)

        return fixtures

    async def _fetch_from_odds_api(self, headlines: List[str]) -> List[Dict[str, Any]]:
        """Fetch NRL odds from The Odds API (rugbyleague_nrl)."""
        fixtures = []
        try:
            url = "https://api.the-odds-api.com/v4/sports/rugbyleague_nrl/odds"
            params = {
                'apiKey': self.odds_api_key,
                'regions': 'au,us',
                'markets': 'h2h,spreads,totals',
                'oddsFormat': 'decimal'
            }

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: requests.get(url, params=params, timeout=15)
            )

            if response.status_code != 200:
                print(f"  Odds API returned {response.status_code} for NRL")
                return []

            data = response.json()
            print(f"  Odds API returned {len(data)} NRL games")

            for game in data:
                home_team = game.get('home_team', 'Unknown')
                away_team = game.get('away_team', 'Unknown')
                start_time_str = game.get('commence_time')

                try:
                    start_time = datetime.strptime(
                        start_time_str, "%Y-%m-%dT%H:%M:%SZ"
                    ).replace(tzinfo=timezone.utc)
                except Exception:
                    start_time = datetime.now(timezone.utc)

                fixture_name = f"{home_team} vs {away_team}"

                for bookmaker in game.get('bookmakers', []):
                    bookmaker_name = bookmaker.get('title', 'Unknown')
                    for market in bookmaker.get('markets', []):
                        market_key = market.get('key')
                        if market_key not in ['h2h', 'spreads', 'totals']:
                            continue

                        for outcome in market.get('outcomes', []):
                            price = outcome.get('price')
                            if price and 1.01 <= price <= 50.0:
                                fixtures.append({
                                    "fixture_name": fixture_name,
                                    "start_time": start_time,
                                    "market_type": market_key,
                                    "selection": outcome.get('name'),
                                    "price": price,
                                    "point": outcome.get('point'),
                                    "bookmaker": bookmaker_name,
                                    "sport": "NRL",
                                    "league": "NRL",
                                    "home_team": home_team,
                                    "away_team": away_team,
                                    "headlines": headlines
                                })

        except Exception as e:
            print(f"  Error fetching NRL from Odds API: {e}")

        return fixtures

    async def _fetch_from_nrl_draw(self, headlines: List[str]) -> List[Dict[str, Any]]:
        """Fallback: Fetch NRL fixtures from NRL.com Draw API."""
        fixtures = []
        try:
            url = "https://www.nrl.com/draw/data"
            params = {
                'competition': 111,
                'season': 2026
            }

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: requests.get(url, params=params, timeout=15)
            )

            if response.status_code != 200:
                print(f"  NRL.com returned {response.status_code}")
                return []

            data = response.json()
            # NRL.com draw data structure: list of rounds with matches
            matches = []
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and 'matches' in item:
                        matches.extend(item['matches'])
            elif isinstance(data, dict):
                # Could be wrapped in a top-level key
                for key in ['fixtures', 'matches', 'drawGroups']:
                    if key in data:
                        groups = data[key]
                        if isinstance(groups, list):
                            for group in groups:
                                if isinstance(group, dict) and 'matches' in group:
                                    matches.extend(group['matches'])
                                elif isinstance(group, dict):
                                    matches.append(group)

            print(f"  NRL.com: found {len(matches)} matches")

            for match in matches:
                try:
                    home_nick = match.get('homeTeam', {}).get('nickName', '')
                    away_nick = match.get('awayTeam', {}).get('nickName', '')

                    home_team = resolve_nrl_team_name(home_nick)
                    away_team = resolve_nrl_team_name(away_nick)

                    # Parse kickoff time
                    kick_off = match.get('clock', {}).get('kickOffTimeLong') or match.get('startTime', '')
                    try:
                        start_time = parser.parse(kick_off)
                        if start_time.tzinfo is None:
                            start_time = start_time.replace(tzinfo=timezone.utc)
                    except Exception:
                        continue

                    fixture_name = f"{home_team} vs {away_team}"

                    # Extract odds if provided by NRL.com
                    home_odds = match.get('homeTeam', {}).get('odds')
                    away_odds = match.get('awayTeam', {}).get('odds')

                    home_price = float(home_odds) if home_odds else None
                    away_price = float(away_odds) if away_odds else None

                    common_data = {
                        "fixture_name": fixture_name,
                        "start_time": start_time,
                        "market_type": "h2h",
                        "bookmaker": "NRL.com",
                        "sport": "NRL",
                        "league": "NRL",
                        "home_team": home_team,
                        "away_team": away_team,
                        "headlines": headlines
                    }

                    fixtures.append({
                        **common_data,
                        "selection": home_team,
                        "price": home_price,
                        "point": None,
                        "record": "0-0"
                    })
                    fixtures.append({
                        **common_data,
                        "selection": away_team,
                        "price": away_price,
                        "point": None,
                        "record": "0-0"
                    })

                except Exception as e:
                    print(f"  Error parsing NRL.com match: {e}")
                    continue

        except Exception as e:
            print(f"  Error fetching from NRL.com: {e}")

        return fixtures

    async def _fetch_nrl_headlines(self) -> List[str]:
        """Fetch NRL news headlines from Zero Tackle RSS for sentiment analysis."""
        headlines = []
        feeds = [
            "https://www.zerotackle.com/feed/",
            "https://www.espn.com/espn/rss/rugby/news",
        ]

        for feed_url in feeds:
            try:
                loop = asyncio.get_event_loop()
                feed = await loop.run_in_executor(
                    None, lambda url=feed_url: feedparser.parse(url)
                )
                for entry in feed.entries[:10]:
                    title = entry.get('title', '')
                    if title:
                        headlines.append(title)
            except Exception as e:
                print(f"  Error fetching NRL headlines from {feed_url}: {e}")

        print(f"  Fetched {len(headlines)} NRL headlines for sentiment")
        return headlines
