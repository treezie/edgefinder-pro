"""
ESPN Results Fetcher — fetches final scores and settles PredictionSnapshots.
"""
import requests
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from database.models import Fixture, PredictionSnapshot


# Maps our sport keys to ESPN API sport/league slugs
SPORT_MAP = {
    "NFL": ("football", "nfl"),
    "NBA": ("basketball", "nba"),
    "NRL": ("rugby-league", "nrl"),
}


class ResultsFetcher:
    def fetch_and_settle(self, db: Session, days_back: int = 3):
        """
        1. Find fixtures with past start_time and no result_settled_at.
        2. For each sport+date combo, hit ESPN scoreboard API.
        3. Match results to fixtures and update scores.
        4. Settle each PredictionSnapshot linked to that fixture.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

        unsettled = (
            db.query(Fixture)
            .filter(
                Fixture.start_time < datetime.now(timezone.utc),
                Fixture.start_time >= cutoff,
                Fixture.result_settled_at.is_(None),
            )
            .all()
        )

        if not unsettled:
            return

        # Group by (sport, date_str)
        groups: dict[tuple[str, str], list[Fixture]] = {}
        for f in unsettled:
            st = f.start_time
            if st.tzinfo is None:
                st = st.replace(tzinfo=timezone.utc)
            date_str = st.strftime("%Y%m%d")
            key = (f.sport, date_str)
            groups.setdefault(key, []).append(f)

        for (sport, date_str), fixtures in groups.items():
            espn_results = self._fetch_espn_scores(sport, date_str)
            if not espn_results:
                continue

            for fixture in fixtures:
                result = self._match_result(fixture, espn_results)
                if result is None:
                    continue

                home_score, away_score = result
                fixture.home_score = home_score
                fixture.away_score = away_score
                fixture.result_settled_at = datetime.now(timezone.utc)

                # Settle all snapshots for this fixture
                snapshots = (
                    db.query(PredictionSnapshot)
                    .filter(
                        PredictionSnapshot.fixture_id == fixture.id,
                        PredictionSnapshot.outcome.is_(None),
                    )
                    .all()
                )
                for snap in snapshots:
                    snap.outcome = self._determine_outcome(
                        snap, home_score, away_score, fixture
                    )
                    snap.settled_at = datetime.now(timezone.utc)

        db.commit()

    # ------------------------------------------------------------------
    # ESPN API
    # ------------------------------------------------------------------

    def _fetch_espn_scores(self, sport: str, date_str: str) -> list[dict]:
        """Return list of {home_team, away_team, home_score, away_score, status}."""
        mapping = SPORT_MAP.get(sport)
        if not mapping:
            return []

        sport_slug, league_slug = mapping
        url = (
            f"https://site.api.espn.com/apis/site/v2/sports/"
            f"{sport_slug}/{league_slug}/scoreboard?dates={date_str}"
        )

        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  ESPN fetch error ({sport} {date_str}): {e}")
            return []

        results = []
        for event in data.get("events", []):
            competition = (event.get("competitions") or [{}])[0]
            competitors = competition.get("competitors", [])
            status_type = (
                event.get("status", {}).get("type", {}).get("name", "")
            )
            if status_type not in ("STATUS_FINAL", "STATUS_FULL_TIME"):
                continue

            home = away = None
            for c in competitors:
                if c.get("homeAway") == "home":
                    home = c
                elif c.get("homeAway") == "away":
                    away = c

            if home and away:
                results.append({
                    "home_team": home.get("team", {}).get("displayName", ""),
                    "away_team": away.get("team", {}).get("displayName", ""),
                    "home_score": int(home.get("score", 0)),
                    "away_score": int(away.get("score", 0)),
                })

        return results

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    def _match_result(self, fixture: Fixture, espn_results: list[dict]):
        """Try to match fixture to an ESPN result by team name."""
        fh = (fixture.home_team or "").lower()
        fa = (fixture.away_team or "").lower()

        for r in espn_results:
            rh = r["home_team"].lower()
            ra = r["away_team"].lower()

            # Exact match
            if fh == rh and fa == ra:
                return r["home_score"], r["away_score"]

            # Fuzzy: one name contained in the other
            if (fh in rh or rh in fh) and (fa in ra or ra in fa):
                return r["home_score"], r["away_score"]

        return None

    # ------------------------------------------------------------------
    # Settlement logic
    # ------------------------------------------------------------------

    def _determine_outcome(
        self,
        snap: PredictionSnapshot,
        home_score: int,
        away_score: int,
        fixture: Fixture,
    ) -> str:
        """Return 'correct', 'incorrect', or 'push'."""
        market = snap.market_type
        selection = (snap.selection or "").strip()

        if market == "h2h":
            return self._settle_h2h(selection, home_score, away_score, fixture)
        elif market == "spreads":
            return self._settle_spread(
                selection, snap.point, home_score, away_score, fixture
            )
        elif market == "totals":
            return self._settle_total(selection, snap.point, home_score, away_score)

        return "incorrect"  # Unknown market

    def _settle_h2h(self, selection, home_score, away_score, fixture):
        if home_score == away_score:
            return "push"
        winner = fixture.home_team if home_score > away_score else fixture.away_team
        sel_lower = selection.lower()
        win_lower = winner.lower()
        if sel_lower == win_lower or sel_lower in win_lower or win_lower in sel_lower:
            return "correct"
        return "incorrect"

    def _settle_spread(self, selection, point, home_score, away_score, fixture):
        if point is None:
            return "incorrect"
        sel_lower = selection.lower()
        home_lower = (fixture.home_team or "").lower()
        # Determine if selection is home or away
        if sel_lower == home_lower or sel_lower in home_lower or home_lower in sel_lower:
            adjusted = home_score + point
            opponent = away_score
        else:
            adjusted = away_score + point
            opponent = home_score

        if adjusted > opponent:
            return "correct"
        elif adjusted < opponent:
            return "incorrect"
        return "push"

    def _settle_total(self, selection, point, home_score, away_score):
        if point is None:
            return "incorrect"
        total = home_score + away_score
        sel_lower = selection.lower()

        if total == point:
            return "push"

        if "over" in sel_lower:
            return "correct" if total > point else "incorrect"
        elif "under" in sel_lower:
            return "correct" if total < point else "incorrect"

        return "incorrect"
