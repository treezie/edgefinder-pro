import requests
from datetime import datetime, timedelta, timezone

today = datetime.now(timezone.utc)

print("Checking next 7 days for NFL games:")
for i in range(7):
    check_date = (today + timedelta(days=i)).strftime('%Y%m%d')
    resp = requests.get(f'http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={check_date}')
    events = resp.json().get('events', [])
    if events:
        print(f'\n{check_date}: {len(events)} NFL games')
        for e in events[:5]:
            status = e.get('status', {}).get('type', {}).get('name', 'Unknown')
            print(f'  - {e.get("name")} - Status: {status}')

print("\n\nChecking next 3 days for NBA games:")
for i in range(3):
    check_date = (today + timedelta(days=i)).strftime('%Y%m%d')
    resp = requests.get(f'http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={check_date}')
    events = resp.json().get('events', [])
    if events:
        print(f'\n{check_date}: {len(events)} NBA games')
        for e in events[:10]:
            status = e.get('status', {}).get('type', {}).get('name', 'Unknown')
            print(f'  - {e.get("name")} - Status: {status}')
