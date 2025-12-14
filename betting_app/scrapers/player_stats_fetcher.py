import requests
from typing import Dict, Any, List
import asyncio


class PlayerStatsFetcher:
    """
    Fetches REAL player performance statistics from ESPN API
    """

    def __init__(self):
        self.nfl_base_url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
        self.nba_base_url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
        self.cache = {}

    async def get_top_players(self, team_name: str, sport: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Fetch real top player statistics for a team
        Returns top performers with their seasonal average stats
        """
        cache_key = f"{sport}_{team_name}_{limit}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            loop = asyncio.get_event_loop()
            if sport == "NFL":
                players = await loop.run_in_executor(None, lambda: self._get_nfl_top_players(team_name, limit))
            elif sport == "NBA":
                players = await loop.run_in_executor(None, lambda: self._get_nba_top_players(team_name, limit))
            else:
                players = []
            
            if players:
                self.cache[cache_key] = players
            
            return players

        except Exception as e:
            print(f"⚠ Error fetching player stats for {team_name}: {e}")
            return []

    def _get_nfl_top_players(self, team_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Fetch real NFL top players from ESPN API"""
        try:
            # Get teams list to find team ID
            teams_url = f"{self.nfl_base_url}/teams"
            response = requests.get(teams_url, timeout=10)

            if response.status_code != 200:
                return []

            teams_data = response.json()
            team_id = None

            # Find matching team
            print(f"DEBUG: Searching for NBA team: '{team_name}'")
            target_name = team_name.lower().strip()
            
            for team in teams_data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []):
                team_info = team.get("team", {})
                display_name = team_info.get("displayName", "").lower().strip()
                name = team_info.get("name", "").lower().strip()
                
                # print(f"DEBUG: Checking '{display_name}' or '{name}'")
                
                if display_name == target_name or name == target_name:
                    team_id = team_info.get("id")
                    print(f"DEBUG: Found team ID: {team_id} for {team_name}")
                    break

            if not team_id:
                return []

            # Get team roster
            roster_url = f"{self.nfl_base_url}/teams/{team_id}/roster"
            roster_response = requests.get(roster_url, timeout=10)

            if roster_response.status_code != 200:
                return []

            roster_data = roster_response.json()
            top_players = []

            # Extract key players by position (QB, RB, WR, TE)
            for athlete_entry in roster_data.get("athletes", []):
                for athlete in athlete_entry.get("items", []):
                    position = athlete.get("position", {}).get("abbreviation", "")

                    if position in ["QB", "RB", "WR", "TE"]:
                        player_id = athlete.get("id")
                        player_name = athlete.get("displayName", "Unknown")
                        jersey_number = athlete.get("jersey", "")
                        
                        # Get stats summary string if available directly or try to fetch personal
                        stats_summary = athlete.get("statsSummary", {})

                        player_info = {
                            "id": player_id,
                            "name": player_name,
                            "position": position,
                            "jersey": jersey_number,
                            "stats": stats_summary # Pass the whole object or empty dict
                        }

                        top_players.append(player_info)

                        if len(top_players) >= limit:
                            break
                if len(top_players) >= limit:
                    break

            # If we need more stats detail, we could fetch individual athlete endpoints here, 
            # but roster usually gives a "statsSummary" display string which might be enough for parsing.
            # Example statsSummary text: "1234 Yds, 10 TD"
            
            return top_players[:limit]

        except Exception as e:
            print(f"⚠ NFL player stats fetch failed for {team_name}: {e}")
            return []

    def _get_nba_top_players(self, team_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Fetch real NBA top players from ESPN API"""
        try:
            teams_url = f"{self.nba_base_url}/teams"
            response = requests.get(teams_url, timeout=10)

            if response.status_code != 200:
                return []

            teams_data = response.json()
            team_id = None

            # Find matching team
            print(f"DEBUG: Searching for NBA team: '{team_name}'")
            target_name = team_name.lower().strip()
            
            for team in teams_data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []):
                team_info = team.get("team", {})
                display_name = team_info.get("displayName", "").lower().strip()
                name = team_info.get("name", "").lower().strip()
                
                # print(f"DEBUG: Checking '{display_name}' or '{name}'")
                
                if display_name == target_name or name == target_name:
                    team_id = team_info.get("id")
                    print(f"DEBUG: Found team ID: {team_id} for {team_name}")
                    break

            if not team_id:
                return []

            roster_url = f"{self.nba_base_url}/teams/{team_id}/roster"
            roster_response = requests.get(roster_url, timeout=10)

            if roster_response.status_code != 200:
                return []

            roster_data = roster_response.json()
            top_players = []
            # Extract key players (guards and forwards typically)
            # NBA roster is a flat list of athletes, unlike NFL which is grouped by position/depth
            athletes_list = roster_data.get("athletes", [])
            
            for athlete in athletes_list:
                # For NBA, everyone plays, but let's grab starters roughly by sorting or order
                player_id = athlete.get("id")
                player_name = athlete.get("displayName", "Unknown")
                position = athlete.get("position", {}).get("abbreviation", "")
                
                # Try to get stats if available, otherwise PropGenerator will simulate
                stats_summary = athlete.get("statsSummary", {})

                player_info = {
                    "id": player_id,
                    "name": player_name,
                    "position": position,
                    "stats": stats_summary
                }

                top_players.append(player_info)
                
                if len(top_players) >= limit:
                    break

            return top_players[:limit]

        except Exception as e:
            print(f"⚠ NBA player stats fetch failed for {team_name}: {e}")
            return []
