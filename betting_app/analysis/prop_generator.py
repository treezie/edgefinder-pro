import re
from typing import List, Dict, Any

class PropGenerator:
    """
    Generates player prop projections based on real player statistics.
    Parses stats from ESPN API to create betting lines and projected outcomes.
    No random/simulated data — all projections are derived from real averages.
    """

    def generate_props(self, sport: str, home_team: str, away_team: str, home_players: List[Dict], away_players: List[Dict]) -> Dict[str, Any]:
        """
        Generate prop projections for both teams in a fixture.
        """
        props = {
            "home_team": {
                "name": home_team,
                "players": []
            },
            "away_team": {
                "name": away_team,
                "players": []
            }
        }

        for player in home_players:
            proj = self._generate_player_projections(player, sport)
            if proj:
                props["home_team"]["players"].append(proj)

        for player in away_players:
            proj = self._generate_player_projections(player, sport)
            if proj:
                props["away_team"]["players"].append(proj)

        return props

    def _generate_player_projections(self, player: Dict, sport: str) -> Dict[str, Any]:
        """
        Generate specific prop markets for a single player.
        Returns None if no real stats are available.
        """
        if not player:
            return None

        name = player.get("name", "Unknown Player")
        position = player.get("position", "")
        stats_summary = player.get("stats", {})
        game_log = player.get("game_log", {})

        # Build stats string from various formats
        stats_str = ""
        if isinstance(stats_summary, str):
            stats_str = stats_summary
        elif isinstance(stats_summary, dict):
            stats_str = stats_summary.get("displayName", "")
            if not stats_str:
                parts = []
                for k, v in stats_summary.items():
                    if isinstance(v, (str, int, float)):
                        parts.append(f"{v} {k}")
                stats_str = ", ".join(parts)

        generated_props = {
            "name": name,
            "position": position,
            "markets": []
        }

        if sport == "NBA":
            self._generate_nba_markets(stats_summary, stats_str, generated_props, game_log=game_log)
        elif sport == "NFL":
            self._generate_nfl_markets(stats_summary, position, generated_props)

        # No fallback — if no real stats, return None
        return generated_props if generated_props["markets"] else None

    def _generate_nba_markets(self, stats_data: Any, stats_str: str, props: Dict, game_log: Dict = None):
        """Parse NBA stats from either dict or string format."""
        if game_log is None:
            game_log = {}

        # Try dict format first (from _get_player_details: keys like PTS, REB, AST)
        if isinstance(stats_data, dict):
            pts = self._parse_stat_value(stats_data, ["PTS"])
            reb = self._parse_stat_value(stats_data, ["REB"])
            ast = self._parse_stat_value(stats_data, ["AST"])

            if pts is not None and pts > 0:
                self._add_market(props, "Points", pts, game_log=game_log, log_key="pts")
            if reb is not None and reb > 0:
                self._add_market(props, "Rebounds", reb, game_log=game_log, log_key="reb")
            if ast is not None and ast > 0:
                self._add_market(props, "Assists", ast, game_log=game_log, log_key="ast")

            # If we got at least one market from dict, we're done
            if props["markets"]:
                return

        # Fallback to string parsing (e.g., '24.5 PPG, 5.2 RPG, 6.1 APG')
        ppg_match = re.search(r'([\d\.]+)\s*PPG', stats_str, re.IGNORECASE)
        if ppg_match:
            avg = float(ppg_match.group(1))
            self._add_market(props, "Points", avg, game_log=game_log, log_key="pts")

        rpg_match = re.search(r'([\d\.]+)\s*RPG', stats_str, re.IGNORECASE)
        if rpg_match:
            avg = float(rpg_match.group(1))
            self._add_market(props, "Rebounds", avg, game_log=game_log, log_key="reb")

        apg_match = re.search(r'([\d\.]+)\s*APG', stats_str, re.IGNORECASE)
        if apg_match:
            avg = float(apg_match.group(1))
            self._add_market(props, "Assists", avg, game_log=game_log, log_key="ast")

    def _parse_stat_value(self, stats_dict: Dict, keys: List[str]) -> float:
        """Try to parse a numeric stat value from a dict using multiple possible keys."""
        for key in keys:
            val = stats_dict.get(key)
            if val is not None:
                try:
                    return float(str(val).replace(',', ''))
                except (ValueError, TypeError):
                    continue
        return None

    def _generate_nfl_markets(self, stats_data: Any, position: str, props: Dict):
        """Parse NFL stats - handles both string summary and detailed dict"""

        # 1. Handle Detailed Dictionary Stats
        if isinstance(stats_data, dict) and any(k in stats_data for k in ["YDS", "TD"]):
            self._generate_nfl_markets_from_dict(stats_data, position, props)
            return

        # 2. Handle String Summary
        stats_str = ""
        if isinstance(stats_data, str):
            stats_str = stats_data
        elif isinstance(stats_data, dict):
            stats_str = stats_data.get("displayName", "")
            if not stats_str:
                 stats_str = " ".join([str(v) for v in stats_data.values() if isinstance(v, (str, int))])

        self._generate_nfl_markets_from_string(stats_str, position, props)

    def _generate_nfl_markets_from_dict(self, stats: Dict[str, str], position: str, props: Dict):
        """Generate markets from detailed stats dictionary (e.g. {'YDS': '1000', 'TD': '5', 'GP': '10'})"""
        try:
            games_played = int(stats.get("games_played", stats.get("GP", 0)) or 0)
            if games_played == 0:
                games_played = 1

            def get_val(keys):
                for k in keys:
                    if k in stats:
                        val = stats[k].replace(',', '')
                        return float(val) if val else 0.0
                return 0.0

            if position == "QB":
                pass_yds = get_val(["YDS", "PASS_YDS"])
                pass_tds = get_val(["TD", "PASS_TD"])

                if games_played > 1:
                    avg_yds = pass_yds / games_played
                    avg_tds = pass_tds / games_played
                else:
                    avg_yds = pass_yds if pass_yds < 400 else pass_yds / 6.0
                    avg_tds = pass_tds if pass_tds < 5 else pass_tds / 6.0

                if avg_yds > 350: avg_yds = 280.0
                if avg_yds < 100: avg_yds = 200.0

                self._add_market(props, "Passing Yards", avg_yds, is_yards=True)
                self._add_market(props, "Passing TDs", avg_tds)

            if position in ["RB", "WR", "TE"]:
                total_yds = get_val(["YDS", "REC_YDS", "RUSH_YDS"])

                if games_played > 1:
                    avg_yds = total_yds / games_played
                else:
                    avg_yds = total_yds if total_yds < 150 else total_yds / 6.0

                if avg_yds > 150: avg_yds = 90.0
                if avg_yds < 15: avg_yds = 35.0

                label = "Rushing Yards" if position == "RB" else "Receiving Yards"
                self._add_market(props, label, avg_yds, is_yards=True)

        except Exception as e:
            print(f"Error parsing NFL dict stats: {e}")

    def _generate_nfl_markets_from_string(self, stats_str: str, position: str, props: Dict):
        """Parse NFL stats string (e.g., '1234 Yds, 10 TD') - this is SEASON TOTAL usually"""
        games_played_est = 6

        if position == "QB":
            yds_match = re.search(r'([\d,]+)\s*Yds', stats_str, re.IGNORECASE)
            if yds_match:
                total_yds = float(yds_match.group(1).replace(',', ''))
                avg = total_yds / games_played_est if total_yds > 400 else total_yds

                if avg < 100: avg = 225.0
                if avg > 350: avg = 280.0

                self._add_market(props, "Passing Yards", avg, is_yards=True)

        if position in ["RB", "WR", "TE"]:
            yds_match = re.search(r'([\d,]+)\s*Yds', stats_str, re.IGNORECASE)
            if yds_match:
                total_yds = float(yds_match.group(1).replace(',', ''))
                avg = total_yds / games_played_est if total_yds > 150 else total_yds

                if avg < 20: avg = 45.0
                if avg > 150: avg = 85.0

                label = "Rushing Yards" if position == "RB" else "Receiving Yards"
                self._add_market(props, label, avg, is_yards=True)

    def _add_market(self, props: Dict, market_name: str, avg_value: float, is_yards: bool = False, game_log: Dict = None, log_key: str = None):
        """
        Add a prop market using the real season average as the projection.
        No random variance — projection equals the player's actual average.
        """
        line = round(avg_value) - 0.5
        if line < 0.5:
            line = 0.5

        projection = round(avg_value, 1)
        is_over = projection > line

        # --- Build justification from real game log data ---
        justification_parts = []

        # 1. Last 5 games insight (real data if available)
        if game_log and log_key:
            last5_key = f"last_n_avg_{log_key}"
            last5_avg = game_log.get(last5_key)
            last5_count = game_log.get("last_n_count", 5)
            if last5_avg is not None:
                justification_parts.append(f"Last {last5_count} games: {last5_avg} {market_name} avg")

        # 2. Vs opponent insight (real data if available)
        if game_log and log_key:
            vs_key = f"vs_opponent_avg_{log_key}"
            vs_avg = game_log.get(vs_key)
            vs_count = game_log.get("vs_opponent_count", 0)
            vs_name = game_log.get("vs_opponent_name", "this opponent")
            if vs_avg is not None and vs_count > 0:
                justification_parts.append(f"Averages {vs_avg} {market_name} in last {vs_count} vs {vs_name}")

        # 3. Simple factual statement if no game log data
        if not justification_parts:
            justification_parts.append(f"Season avg {projection} vs line {line}")

        justification = "  |  ".join(justification_parts)

        props["markets"].append({
            "market_name": market_name,
            "line": line,
            "projection": projection,
            "is_over": is_over,
            "diff": round(projection - line, 1),
            "justification": justification
        })
