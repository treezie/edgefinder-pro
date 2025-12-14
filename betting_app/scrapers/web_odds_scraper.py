import asyncio
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import json
import re


class WebOddsScraper:
    """
    Scrapes REAL odds from online betting websites when API quota is exhausted.
    Acts as fallback to The Odds API.
    Sources: Odds comparison sites that aggregate real bookmaker odds.
    """

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    async def get_all_markets_for_game(self, sport: str, home_team: str, away_team: str) -> List[Dict[str, Any]]:
        """
        Scrapes odds from web sources for a specific game.
        Returns same format as OddsAPIFetcher for compatibility.
        """
        print(f"🌐 Web scraping odds for {home_team} vs {away_team}...")

        try:
            if sport == "NBA":
                return await self._scrape_nba_odds(home_team, away_team)
            elif sport == "NFL":
                return await self._scrape_nfl_odds(home_team, away_team)
            else:
                print(f"⚠ Web scraping not configured for {sport}")
                return []
        except Exception as e:
            print(f"❌ Web scraping error: {e}")
            return []

    async def _scrape_nba_odds(self, home_team: str, away_team: str) -> List[Dict[str, Any]]:
        """
        Scrape NBA odds from ESPN's public betting data.
        ESPN provides real odds from various bookmakers in their game pages.
        """
        result = []

        try:
            await asyncio.sleep(1)  # Rate limiting

            # ESPN provides betting odds in their scoreboard API
            # This is the same public API we use for schedules
            from datetime import datetime, timedelta

            # Check next 3 days for the game
            for days_ahead in range(3):
                check_date = (datetime.now() + timedelta(days=days_ahead)).strftime('%Y%m%d')

                url = f"http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={check_date}"
                response = requests.get(url, headers=self.headers, timeout=10)

                if response.status_code != 200:
                    continue

                data = response.json()
                events = data.get('events', [])

                for event in events:
                    # Check if this is our game
                    competitors = event.get('competitions', [{}])[0].get('competitors', [])
                    home = next((c for c in competitors if c.get('homeAway') == 'home'), {})
                    away = next((c for c in competitors if c.get('homeAway') == 'away'), {})

                    event_home = home.get('team', {}).get('displayName', '')
                    event_away = away.get('team', {}).get('displayName', '')

                    # Match teams (case insensitive, partial match)
                    if (home_team.lower() not in event_home.lower() or
                        away_team.lower() not in event_away.lower()):
                        continue

                    # Found our game! Now extract odds
                    odds_data = event.get('competitions', [{}])[0].get('odds', [])

                    for odds_provider in odds_data:
                        # Extract provider name from logo URL (e.g., "Draftkings_Light.svg" -> "DraftKings")
                        provider_logos = odds_provider.get('provider', {}).get('logos', [])
                        provider_name = 'ESPN'
                        if provider_logos:
                            logo_url = provider_logos[0].get('href', '')
                            if 'draftkings' in logo_url.lower():
                                provider_name = 'DraftKings'
                            elif 'fanduel' in logo_url.lower():
                                provider_name = 'FanDuel'
                            elif 'caesars' in logo_url.lower():
                                provider_name = 'Caesars'
                            elif 'betmgm' in logo_url.lower():
                                provider_name = 'BetMGM'

                        # Get moneyline (h2h) odds from the correct path
                        moneyline = odds_provider.get('moneyline', {})
                        home_odds_str = moneyline.get('home', {}).get('close', {}).get('odds')
                        away_odds_str = moneyline.get('away', {}).get('close', {}).get('odds')

                        # Convert string odds to float
                        home_odds = float(home_odds_str) if home_odds_str else None
                        away_odds = float(away_odds_str) if away_odds_str else None

                        # Convert American odds to decimal
                        if home_odds:
                            home_decimal = self._american_to_decimal(home_odds)
                            if 1.01 <= home_decimal <= 50.0:
                                result.append({
                                    'bookmaker': provider_name,
                                    'market_type': 'h2h',
                                    'selection': event_home,
                                    'price': home_decimal,
                                    'point': None
                                })

                        if away_odds:
                            away_decimal = self._american_to_decimal(away_odds)
                            if 1.01 <= away_decimal <= 50.0:
                                result.append({
                                    'bookmaker': provider_name,
                                    'market_type': 'h2h',
                                    'selection': event_away,
                                    'price': away_decimal,
                                    'point': None
                                })

                        # Get spread odds
                        point_spread = odds_provider.get('pointSpread', {})
                        home_spread_line = point_spread.get('home', {}).get('close', {}).get('line')
                        home_spread_odds_str = point_spread.get('home', {}).get('close', {}).get('odds')
                        away_spread_line = point_spread.get('away', {}).get('close', {}).get('line')
                        away_spread_odds_str = point_spread.get('away', {}).get('close', {}).get('odds')

                        if home_spread_line and home_spread_odds_str:
                            # Parse line (e.g., "-3" -> -3.0)
                            spread_point = float(home_spread_line)
                            spread_odds = float(home_spread_odds_str)
                            spread_decimal = self._american_to_decimal(spread_odds)

                            if 1.01 <= spread_decimal <= 50.0:
                                result.append({
                                    'bookmaker': provider_name,
                                    'market_type': 'spreads',
                                    'selection': event_home,
                                    'price': spread_decimal,
                                    'point': spread_point
                                })

                        if away_spread_line and away_spread_odds_str:
                            spread_point = float(away_spread_line)
                            spread_odds = float(away_spread_odds_str)
                            spread_decimal = self._american_to_decimal(spread_odds)

                            if 1.01 <= spread_decimal <= 50.0:
                                result.append({
                                    'bookmaker': provider_name,
                                    'market_type': 'spreads',
                                    'selection': event_away,
                                    'price': spread_decimal,
                                    'point': spread_point
                                })

                        # Get totals (over/under)
                        total_odds = odds_provider.get('total', {})
                        over_under = odds_provider.get('overUnder')  # The line (e.g., 54.5)
                        over_odds_str = total_odds.get('over', {}).get('close', {}).get('odds')
                        under_odds_str = total_odds.get('under', {}).get('close', {}).get('odds')

                        if over_under and over_odds_str:
                            over_odds = float(over_odds_str)
                            over_decimal = self._american_to_decimal(over_odds)
                            if 1.01 <= over_decimal <= 50.0:
                                result.append({
                                    'bookmaker': provider_name,
                                    'market_type': 'totals',
                                    'selection': 'Over',
                                    'price': over_decimal,
                                    'point': float(over_under)
                                })

                        if over_under and under_odds_str:
                            under_odds = float(under_odds_str)
                            under_decimal = self._american_to_decimal(under_odds)
                            if 1.01 <= under_decimal <= 50.0:
                                result.append({
                                    'bookmaker': provider_name,
                                    'market_type': 'totals',
                                    'selection': 'Under',
                                    'price': under_decimal,
                                    'point': float(over_under)
                                })

                    if result:
                        print(f"✓ Web scraped {len(result)} odds for {home_team} vs {away_team}")
                        return result

            print(f"⚠ No web odds found for {home_team} vs {away_team}")
            return []

        except Exception as e:
            print(f"❌ NBA scraping failed: {e}")
            return []

    async def _scrape_nfl_odds(self, home_team: str, away_team: str) -> List[Dict[str, Any]]:
        """
        Scrape NFL odds from ESPN's public betting data.
        ESPN provides real odds from various bookmakers.
        """
        result = []

        try:
            await asyncio.sleep(1)  # Rate limiting

            # ESPN provides betting odds in their scoreboard API
            from datetime import datetime, timedelta

            # Check next 7 days for the game
            for days_ahead in range(7):
                check_date = (datetime.now() + timedelta(days=days_ahead)).strftime('%Y%m%d')

                url = f"http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={check_date}"
                response = requests.get(url, headers=self.headers, timeout=10)

                if response.status_code != 200:
                    continue

                data = response.json()
                events = data.get('events', [])

                for event in events:
                    # Check if this is our game
                    competitors = event.get('competitions', [{}])[0].get('competitors', [])
                    home = next((c for c in competitors if c.get('homeAway') == 'home'), {})
                    away = next((c for c in competitors if c.get('homeAway') == 'away'), {})

                    event_home = home.get('team', {}).get('displayName', '')
                    event_away = away.get('team', {}).get('displayName', '')

                    # Match teams (case insensitive, partial match)
                    if (home_team.lower() not in event_home.lower() or
                        away_team.lower() not in event_away.lower()):
                        continue

                    # Found our game! Now extract odds (same logic as NBA)
                    odds_data = event.get('competitions', [{}])[0].get('odds', [])

                    for odds_provider in odds_data:
                        # Extract provider name from logo URL
                        provider_logos = odds_provider.get('provider', {}).get('logos', [])
                        provider_name = 'ESPN'
                        if provider_logos:
                            logo_url = provider_logos[0].get('href', '')
                            if 'draftkings' in logo_url.lower():
                                provider_name = 'DraftKings'
                            elif 'fanduel' in logo_url.lower():
                                provider_name = 'FanDuel'
                            elif 'caesars' in logo_url.lower():
                                provider_name = 'Caesars'
                            elif 'betmgm' in logo_url.lower():
                                provider_name = 'BetMGM'

                        # Get moneyline (h2h) odds
                        moneyline = odds_provider.get('moneyline', {})
                        home_odds_str = moneyline.get('home', {}).get('close', {}).get('odds')
                        away_odds_str = moneyline.get('away', {}).get('close', {}).get('odds')

                        home_odds = float(home_odds_str) if home_odds_str else None
                        away_odds = float(away_odds_str) if away_odds_str else None

                        if home_odds:
                            home_decimal = self._american_to_decimal(home_odds)
                            if 1.01 <= home_decimal <= 50.0:
                                result.append({
                                    'bookmaker': provider_name,
                                    'market_type': 'h2h',
                                    'selection': event_home,
                                    'price': home_decimal,
                                    'point': None
                                })

                        if away_odds:
                            away_decimal = self._american_to_decimal(away_odds)
                            if 1.01 <= away_decimal <= 50.0:
                                result.append({
                                    'bookmaker': provider_name,
                                    'market_type': 'h2h',
                                    'selection': event_away,
                                    'price': away_decimal,
                                    'point': None
                                })

                        # Get spread odds (same as NBA)
                        point_spread = odds_provider.get('pointSpread', {})
                        home_spread_line = point_spread.get('home', {}).get('close', {}).get('line')
                        home_spread_odds_str = point_spread.get('home', {}).get('close', {}).get('odds')
                        away_spread_line = point_spread.get('away', {}).get('close', {}).get('line')
                        away_spread_odds_str = point_spread.get('away', {}).get('close', {}).get('odds')

                        if home_spread_line and home_spread_odds_str:
                            spread_point = float(home_spread_line)
                            spread_odds = float(home_spread_odds_str)
                            spread_decimal = self._american_to_decimal(spread_odds)

                            if 1.01 <= spread_decimal <= 50.0:
                                result.append({
                                    'bookmaker': provider_name,
                                    'market_type': 'spreads',
                                    'selection': event_home,
                                    'price': spread_decimal,
                                    'point': spread_point
                                })

                        if away_spread_line and away_spread_odds_str:
                            spread_point = float(away_spread_line)
                            spread_odds = float(away_spread_odds_str)
                            spread_decimal = self._american_to_decimal(spread_odds)

                            if 1.01 <= spread_decimal <= 50.0:
                                result.append({
                                    'bookmaker': provider_name,
                                    'market_type': 'spreads',
                                    'selection': event_away,
                                    'price': spread_decimal,
                                    'point': spread_point
                                })

                        # Get totals (over/under) (same as NBA)
                        total_odds = odds_provider.get('total', {})
                        over_under = odds_provider.get('overUnder')
                        over_odds_str = total_odds.get('over', {}).get('close', {}).get('odds')
                        under_odds_str = total_odds.get('under', {}).get('close', {}).get('odds')

                        if over_under and over_odds_str:
                            over_odds = float(over_odds_str)
                            over_decimal = self._american_to_decimal(over_odds)
                            if 1.01 <= over_decimal <= 50.0:
                                result.append({
                                    'bookmaker': provider_name,
                                    'market_type': 'totals',
                                    'selection': 'Over',
                                    'price': over_decimal,
                                    'point': float(over_under)
                                })

                        if over_under and under_odds_str:
                            under_odds = float(under_odds_str)
                            under_decimal = self._american_to_decimal(under_odds)
                            if 1.01 <= under_decimal <= 50.0:
                                result.append({
                                    'bookmaker': provider_name,
                                    'market_type': 'totals',
                                    'selection': 'Under',
                                    'price': under_decimal,
                                    'point': float(over_under)
                                })

                    if result:
                        print(f"✓ Web scraped {len(result)} odds for {home_team} vs {away_team}")
                        return result

            print(f"⚠ No web odds found for {home_team} vs {away_team}")
            return []

        except Exception as e:
            print(f"❌ NFL scraping failed: {e}")
            return []

    def _american_to_decimal(self, american_odds: float) -> float:
        """
        Convert American odds to decimal odds.
        American: -110, +150, etc.
        Decimal: 1.91, 2.50, etc.
        """
        if american_odds > 0:
            # Positive odds: (american_odds / 100) + 1
            return (american_odds / 100) + 1
        else:
            # Negative odds: (100 / abs(american_odds)) + 1
            return (100 / abs(american_odds)) + 1

    def _get_team_abbreviation(self, team_name: str, sport: str) -> str:
        """Map team names to abbreviations for web scraping."""
        nba_abbrev = {
            'Atlanta Hawks': 'ATL',
            'Boston Celtics': 'BOS',
            'Brooklyn Nets': 'BKN',
            'Charlotte Hornets': 'CHA',
            'Chicago Bulls': 'CHI',
            'Cleveland Cavaliers': 'CLE',
            'Dallas Mavericks': 'DAL',
            'Denver Nuggets': 'DEN',
            'Detroit Pistons': 'DET',
            'Golden State Warriors': 'GSW',
            'Houston Rockets': 'HOU',
            'Indiana Pacers': 'IND',
            'Los Angeles Clippers': 'LAC',
            'Los Angeles Lakers': 'LAL',
            'Memphis Grizzlies': 'MEM',
            'Miami Heat': 'MIA',
            'Milwaukee Bucks': 'MIL',
            'Minnesota Timberwolves': 'MIN',
            'New Orleans Pelicans': 'NOP',
            'New York Knicks': 'NYK',
            'Oklahoma City Thunder': 'OKC',
            'Orlando Magic': 'ORL',
            'Philadelphia 76ers': 'PHI',
            'Phoenix Suns': 'PHX',
            'Portland Trail Blazers': 'POR',
            'Sacramento Kings': 'SAC',
            'San Antonio Spurs': 'SAS',
            'Toronto Raptors': 'TOR',
            'Utah Jazz': 'UTA',
            'Washington Wizards': 'WAS'
        }

        if sport == "NBA":
            return nba_abbrev.get(team_name, team_name[:3].upper())

        return team_name[:3].upper()

    async def scrape_odds_from_oddschecker(self, sport: str, home_team: str, away_team: str) -> List[Dict[str, Any]]:
        """
        Scrape from Oddschecker (UK/AU odds comparison site).
        This is a PUBLIC site that aggregates odds from multiple bookmakers.
        """
        # Note: Oddschecker has anti-scraping measures, so this is a placeholder
        # In production, you'd use their affiliate API or similar
        print(f"⚠ Oddschecker scraping requires additional setup")
        return []
