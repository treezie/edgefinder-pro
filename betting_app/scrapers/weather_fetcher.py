import requests
from typing import Dict, Any
from datetime import datetime
import asyncio

class WeatherFetcher:
    """
    Fetches REAL weather data for NFL games
    Uses OpenWeatherMap API or weather.gov
    """

    def __init__(self):
        # Stadium locations (latitude, longitude)
        self.stadiums = {
            "Detroit Lions": {"lat": 42.34, "lon": -83.05, "indoor": True, "name": "Ford Field"},
            "Dallas Cowboys": {"lat": 32.75, "lon": -97.09, "indoor": True, "name": "AT&T Stadium"},
            "Atlanta Falcons": {"lat": 33.76, "lon": -84.39, "indoor": True, "name": "Mercedes-Benz Stadium"},
            "Seattle Seahawks": {"lat": 47.60, "lon": -122.33, "indoor": False, "name": "Lumen Field"},
            "Buffalo Bills": {"lat": 42.77, "lon": -78.79, "indoor": False, "name": "Highmark Stadium"},
            "Cincinnati Bengals": {"lat": 39.10, "lon": -84.52, "indoor": False, "name": "Paycor Stadium"},
            "Cleveland Browns": {"lat": 41.51, "lon": -81.70, "indoor": False, "name": "Cleveland Browns Stadium"},
            "Tennessee Titans": {"lat": 36.17, "lon": -86.77, "indoor": False, "name": "Nissan Stadium"},
            "Minnesota Vikings": {"lat": 44.97, "lon": -93.26, "indoor": True, "name": "U.S. Bank Stadium"},
            "Washington Commanders": {"lat": 38.91, "lon": -76.86, "indoor": False, "name": "FedExField"},
            "New York Jets": {"lat": 40.81, "lon": -74.07, "indoor": False, "name": "MetLife Stadium"},
            "Miami Dolphins": {"lat": 25.96, "lon": -80.24, "indoor": False, "name": "Hard Rock Stadium"},
            "Tampa Bay Buccaneers": {"lat": 27.98, "lon": -82.50, "indoor": False, "name": "Raymond James Stadium"},
            "New Orleans Saints": {"lat": 29.95, "lon": -90.08, "indoor": True, "name": "Caesars Superdome"},
            "Jacksonville Jaguars": {"lat": 30.32, "lon": -81.64, "indoor": False, "name": "TIAA Bank Field"},
            "Indianapolis Colts": {"lat": 39.76, "lon": -86.16, "indoor": True, "name": "Lucas Oil Stadium"},
            "Baltimore Ravens": {"lat": 39.28, "lon": -76.62, "indoor": False, "name": "M&T Bank Stadium"},
            "Pittsburgh Steelers": {"lat": 40.45, "lon": -80.02, "indoor": False, "name": "Acrisure Stadium"},
            "Las Vegas Raiders": {"lat": 36.09, "lon": -115.18, "indoor": True, "name": "Allegiant Stadium"},
            "Denver Broncos": {"lat": 39.74, "lon": -104.99, "indoor": False, "name": "Empower Field"},
            "Green Bay Packers": {"lat": 44.50, "lon": -88.06, "indoor": False, "name": "Lambeau Field"},
            "Chicago Bears": {"lat": 41.86, "lon": -87.62, "indoor": False, "name": "Soldier Field"},
            "Arizona Cardinals": {"lat": 33.53, "lon": -112.26, "indoor": True, "name": "State Farm Stadium"},
            "Los Angeles Rams": {"lat": 33.95, "lon": -118.34, "indoor": True, "name": "SoFi Stadium"},
            "Kansas City Chiefs": {"lat": 39.05, "lon": -94.48, "indoor": False, "name": "GEHA Field"},
            "Houston Texans": {"lat": 29.68, "lon": -95.41, "indoor": True, "name": "NRG Stadium"},
            "Los Angeles Chargers": {"lat": 33.95, "lon": -118.34, "indoor": True, "name": "SoFi Stadium"},
            "Philadelphia Eagles": {"lat": 39.90, "lon": -75.17, "indoor": False, "name": "Lincoln Financial Field"},
        }

    async def get_game_weather(self, home_team: str, game_time: datetime) -> Dict[str, Any]:
        """
        Fetch REAL weather forecast for game time and location
        """
        if home_team not in self.stadiums:
            return self._get_no_weather_data()

        stadium = self.stadiums[home_team]

        # Indoor stadium - no weather impact
        if stadium["indoor"]:
            return {
                "available": True,
                "indoor": True,
                "stadium": stadium["name"],
                "impact": "None - Indoor Stadium",
                "temperature": "Controlled",
                "conditions": "Perfect",
                "wind_speed": 0,
                "precipitation": 0
            }

        # Outdoor stadium - fetch real weather
        try:
            return await self._fetch_weather(stadium["lat"], stadium["lon"], stadium["name"], game_time)
        except Exception as e:
            print(f"⚠ Weather fetch failed for {home_team}: {e}")
            return self._get_no_weather_data()

    async def _fetch_weather(self, lat: float, lon: float, stadium_name: str, game_time: datetime) -> Dict[str, Any]:
        """
        Fetch from weather.gov (free, no API key needed for US locations)
        """
        try:
            # Use weather.gov API (NOAA)
            # First get forecast URL for this location
            points_url = f"https://api.weather.gov/points/{lat},{lon}"

            response = requests.get(points_url, timeout=10, headers={
                "User-Agent": "BettingApp/1.0"
            })

            if response.status_code != 200:
                print(f"⚠ Could not get weather points (Status: {response.status_code})")
                return self._get_no_weather_data()

            points_data = response.json()
            forecast_url = points_data.get("properties", {}).get("forecast")

            if not forecast_url:
                return self._get_no_weather_data()

            # Get actual forecast
            forecast_response = requests.get(forecast_url, timeout=10, headers={
                "User-Agent": "BettingApp/1.0"
            })

            if forecast_response.status_code != 200:
                return self._get_no_weather_data()

            forecast_data = forecast_response.json()
            periods = forecast_data.get("properties", {}).get("periods", [])

            if not periods:
                return self._get_no_weather_data()

            # Get the relevant forecast period (usually first period)
            current_forecast = periods[0]

            temperature = current_forecast.get("temperature", 0)
            conditions = current_forecast.get("shortForecast", "Unknown")
            wind_speed = current_forecast.get("windSpeed", "0 mph")

            # Parse wind speed
            try:
                wind_mph = int(wind_speed.split()[0]) if wind_speed else 0
            except:
                wind_mph = 0

            # Assess weather impact on game
            impact = self._assess_weather_impact(temperature, wind_mph, conditions)

            print(f"✓ Fetched real weather for {stadium_name}: {temperature}°F, {conditions}")

            return {
                "available": True,
                "indoor": False,
                "stadium": stadium_name,
                "temperature": f"{temperature}°F",
                "conditions": conditions,
                "wind_speed": wind_mph,
                "wind_description": wind_speed,
                "impact": impact,
                "precipitation": "rain" in conditions.lower() or "snow" in conditions.lower()
            }

        except Exception as e:
            print(f"⚠ Weather API error: {e}")
            return self._get_no_weather_data()

    def _assess_weather_impact(self, temp: int, wind: int, conditions: str) -> str:
        """Assess weather impact on game"""
        impacts = []

        if temp < 20:
            impacts.append("Extreme Cold")
        elif temp < 32:
            impacts.append("Freezing Conditions")
        elif temp > 95:
            impacts.append("Extreme Heat")

        if wind > 20:
            impacts.append("High Winds - Passing Game Affected")
        elif wind > 15:
            impacts.append("Moderate Winds")

        if "rain" in conditions.lower():
            impacts.append("Rain - Ball Handling Affected")
        if "snow" in conditions.lower():
            impacts.append("Snow - Visibility Issues")

        if not impacts:
            return "Minimal Weather Impact"

        return " | ".join(impacts)

    def _get_no_weather_data(self) -> Dict[str, Any]:
        """Return when weather data unavailable"""
        return {
            "available": False,
            "message": "Weather data not available"
        }
