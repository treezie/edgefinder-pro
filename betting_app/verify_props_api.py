import requests
import sys
import os

# Add the current directory to sys.path to import database modules if needed
sys.path.append(os.getcwd())

from database.db import SessionLocal
from database.models import Fixture

def verify_api():
    print("Verifying Prop Builder API...")
    
    # 1. Get a fixture ID from the database
    session = SessionLocal()
    try:
        # Get an NBA or NFL fixture
        fixture = session.query(Fixture).filter(Fixture.sport.in_(['NBA', 'NFL'])).first()
        
        if not fixture:
            print("❌ No NBA or NFL fixtures found in database.")
            return
            
        print(f"✅ Found fixture: {fixture.sport} - {fixture.home_team} vs {fixture.away_team} (ID: {fixture.id})")
        fixture_id = fixture.id
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return
    finally:
        session.close()

    # 2. Call the API endpoint
    url = f"http://127.0.0.1:8000/api/props/{fixture_id}"
    print(f"Calling API: {url}")
    
    try:
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            
            # 3. Validate response structure
            if "home_team" in data and "away_team" in data:
                print("✅ API returned valid JSON structure.")
                
                home_players = data["home_team"].get("players", [])
                print(f"   Home Team: {data['home_team']['name']} ({len(home_players)} players)")
                
                if home_players:
                    player = home_players[0]
                    print(f"   Sample Player: {player['name']} - {player['position']}")
                    print(f"   Markets: {len(player['markets'])}")
                    if player['markets']:
                        print(f"   Sample Market: {player['markets'][0]['name']} {player['markets'][0]['line']}")
                
                print("✅ Prop generation successful!")
            else:
                print("❌ API returned unexpected JSON structure.")
                print(data)
        else:
            print(f"❌ API call failed with status code: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ API call error: {e}")

if __name__ == "__main__":
    verify_api()
