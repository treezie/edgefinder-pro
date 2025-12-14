
import requests
import json

def inspect_nba_roster():
    # ID 25 is OKC Thunder
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/25/roster"
    print(f"Fetching {url}...")
    
    try:
        resp = requests.get(url)
        data = resp.json()
        
        print("Roster Data Keys:", data.keys())
        
        if "athletes" in data:
            print(f"Athletes List Length: {len(data['athletes'])}")
            for i, group in enumerate(data['athletes']):
                print(f" - Group {i} keys: {group.keys()}")
                if "position" in group:
                    print(f"   Position: {group['position']}")
                if "items" in group:
                    print(f"   Items count: {len(group['items'])}")
                    if group['items']:
                        sample = group['items'][0]
                        print(f"   Sample Player: {sample.get('fullName')}")
                        print(f"   Sample Keys: {sample.keys()}")
                        print(f"   Sample Stats: {sample.get('statsSummary')}")
        else:
            print("No 'athletes' key found!")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_nba_roster()
