import requests
from datetime import datetime
import json

BASE_URL = "http://localhost:8000"

def check_endpoint(endpoint, name):
    print(f"Checking {name} ({endpoint})...")
    try:
        response = requests.get(f"{BASE_URL}{endpoint}")
        if response.status_code != 200:
            print(f"❌ {name} failed with status {response.status_code}")
            return
        
        # Parse response text to find dates or just check if it loads
        # Since these are HTML pages, we can't easily parse JSON data without a parser
        # But we can check if the request succeeds.
        # For a better check, we'd need to parse the HTML or have a JSON endpoint.
        
        # However, we can check if the response contains "Dec 08" (yesterday) if we know that's a past date
        # This is a rough check.
        
        content = response.text
        print(f"✅ {name} loaded successfully ({len(content)} bytes)")
        
    except Exception as e:
        print(f"❌ {name} error: {e}")

if __name__ == "__main__":
    check_endpoint("/bets", "Single Bets")
    check_endpoint("/multibets", "Multi-Bets")
    check_endpoint("/strategy", "Strategy")
