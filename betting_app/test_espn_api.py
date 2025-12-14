
import requests
import json

def test_athlete_endpoint():
    # ID from previous run (Hollywood Brown)
    athlete_id = "4241372"
    url = f"https://site.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{athlete_id}"
    
    print(f"Fetching {url}...")
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            print("Success!")
            # Check for stats
            if "athlete" in data:
                ath = data["athlete"]
                if "stats" in ath:
                    print("Found stats!")
                    print(json.dumps(ath["stats"], indent=2)[:500]) # First 500 chars
                else:
                    print("No 'stats' in athlete object.")
                    print(ath.keys())
        else:
            print(f"Failed: {resp.status_code}")
            
    except Exception as e:
        print(e)
        
    print("-" * 20)
    
    # Try another one: /overview
    url2 = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/athletes/{athlete_id}"
    print(f"Fetching {url2}...")
    try:
        resp = requests.get(url2)
        if resp.status_code == 200:
             data = resp.json()
             if "stats" in data:
                 print("Found stats in v2!")
             else:
                 print("No stats in v2 root")
                 # check categories?
                 # print(data.keys())
    except:
        pass

if __name__ == "__main__":
    test_athlete_endpoint()
