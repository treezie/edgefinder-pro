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




    def _get_player_details(self, player_id: str, sport: str, league: str = "nfl") -> Dict[str, Any]:
        """
        Fetch detailed player stats from the overview endpoint.
        Returns a dictionary of parsed stats from the 'Regular Season' split.
        """
        try:
            url = f"https://site.api.espn.com/apis/common/v3/sports/{sport}/{league}/athletes/{player_id}/overview"
            response = requests.get(url, timeout=5)
            
            if response.status_code != 200:
                return {}

            data = response.json()
            stats_data = data.get("statistics", {})
            splits = stats_data.get("splits", [])
            
            # Find Regular Season split (and match current year/season logic if needed)
            # Just taking "Regular Season" might return an old year if that's all that's returned.
            # We can check the 'year' field in the split if it exists, or just hope the API is current.
            # Usually ESPN overview defaults to current.
            reg_season = next((s for s in splits if s.get("displayName") == "Regular Season"), None)
            
            if not reg_season:
                # Try finding any split with '2024' or '2025' in displayName if "Regular Season" is missing or different
                reg_season = next((s for s in splits if "2024" in s.get("displayName", "") or "2025" in s.get("displayName", "")), None)

            if not reg_season:
                return {}
             
            stats_values = reg_season.get("stats", [])
            labels = stats_data.get("labels", [])
            
            # Map labels to values
            # Example: {"REC": "40", "YDS": "359", "TD": "5"}
            parsed_stats = {}
            if len(stats_values) == len(labels):
                for i, label in enumerate(labels):
                    parsed_stats[label] = stats_values[i]
            
            # Also get games played if available (usually in stats or calculated)
            # In some sports 'GP' is a label, check for it
            if "GP" in parsed_stats:
                parsed_stats["games_played"] = parsed_stats["GP"]
            
            return parsed_stats

        except Exception as e:
            print(f"⚠ Error fetching details for player {player_id}: {e}")
            return {}

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
            print(f"DEBUG: Searching for NFL team: '{team_name}'")
            target_name = team_name.lower().strip()
            
            for team in teams_data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []):
                team_info = team.get("team", {})
                display_name = team_info.get("displayName", "").lower().strip()
                name = team_info.get("name", "").lower().strip()
                
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
                    # Check status
                    status = athlete.get("status", {}).get("type")
                    if status != "active":
                        continue

                    position = athlete.get("position", {}).get("abbreviation", "")

                    if position in ["QB", "RB", "WR", "TE"]:
                        player_id = athlete.get("id")
                        player_name = athlete.get("displayName", "Unknown")
                        jersey_number = athlete.get("jersey", "")
                        
                        # Get detailed stats since statsSummary is often null
                        detailed_stats = self._get_player_details(player_id, "football", "nfl")
                        
                        # If we failed to get details, try the summary
                        if not detailed_stats:
                             detailed_stats = athlete.get("statsSummary", {})

                        player_info = {
                            "id": player_id,
                            "name": player_name,
                            "position": position,
                            "jersey": jersey_number,
                            "stats": detailed_stats 
                        }

                        top_players.append(player_info)

                        if len(top_players) >= limit:
                            break
                if len(top_players) >= limit:
                    break
            
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
            
            athletes_list = roster_data.get("athletes", [])
            
            for athlete in athletes_list:
                # Check status
                status = athlete.get("status", {}).get("type")
                if status != "active":
                    continue

                player_id = athlete.get("id")
                player_name = athlete.get("displayName", "Unknown")
                position = athlete.get("position", {}).get("abbreviation", "")
                
                # Fetch detailed stats
                detailed_stats = self._get_player_details(player_id, "basketball", "nba")
                if not detailed_stats:
                    detailed_stats = athlete.get("statsSummary", {})

                player_info = {
                    "id": player_id,
                    "name": player_name,
                    "position": position,
                    "stats": detailed_stats
                }

                top_players.append(player_info)
                
                if len(top_players) >= limit:
                    break

            return top_players[:limit]

        except Exception as e:
            print(f"⚠ NBA player stats fetch failed for {team_name}: {e}")
            return []

