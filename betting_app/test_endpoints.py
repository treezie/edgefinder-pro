"""
Test script to debug multibets and strategy endpoints
"""
import sys
sys.path.insert(0, '.')

from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

print("Testing multibets endpoint...")
try:
    response = client.get("/multibets")
    print(f"Status: {response.status_code}")
    if response.status_code != 200:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Exception: {e}")
    import traceback
    traceback.print_exc()

print("\nTesting strategy endpoint...")
try:
    response = client.get("/strategy")
    print(f"Status: {response.status_code}")
    if response.status_code != 200:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Exception: {e}")
    import traceback
    traceback.print_exc()
