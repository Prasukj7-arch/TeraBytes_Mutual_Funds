import sys
import os
from pathlib import Path
from fastapi.testclient import TestClient

# Set up paths for FastAPI imports
_PROJECT_ROOT = str(Path(__file__).resolve().parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Ensure api directory is in path
api_dir = os.path.join(_PROJECT_ROOT, "api")
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

from api.main import app

client = TestClient(app)

def test_routes():
    print("=== Testing FastAPI Wealth API Endpoints ===")
    
    print("\n1. GET Root /")
    response = client.get("/")
    print(f"Status Code: {response.status_code}")
    print(response.json())
    assert response.status_code == 200
    
    user_id = "api_test_user_777"
    
    print("\n2. POST /portfolio/ (Adding a Stock)")
    stock_payload = {
        "user_id": user_id,
        "scheme_code": "AAPL",
        "units": 10.0,
        "purchase_date": "2025-01-01",
        "purchase_nav": 180.0
    }
    response = client.post("/portfolio/", json=stock_payload)
    print(f"Status Code: {response.status_code}")
    stock_resp = response.json()
    print(stock_resp)
    assert response.status_code == 201
    assert stock_resp["asset_type"] == "stock"
    assert stock_resp["scheme_code"] == "AAPL"
    
    print("\n3. POST /portfolio/ (Adding a Mutual Fund)")
    mf_payload = {
        "user_id": user_id,
        "scheme_code": "Axis Large Cap Fund - Regular Growth",
        "units": 100.0,
        "purchase_date": "2024-06-15",
        "purchase_nav": 50.0
    }
    response = client.post("/portfolio/", json=mf_payload)
    print(f"Status Code: {response.status_code}")
    mf_resp = response.json()
    print(mf_resp)
    assert response.status_code == 201
    assert mf_resp["asset_type"] == "mutual_fund"
    
    print("\n4. GET /portfolio/{user_id} (Fetching Consolidated Portfolio)")
    response = client.get(f"/portfolio/{user_id}")
    print(f"Status Code: {response.status_code}")
    portfolio = response.json()
    print(portfolio)
    assert response.status_code == 200
    assert portfolio["user_id"] == user_id
    assert len(portfolio["holdings"]) == 2
    
    # Verify holding computations are present
    for h in portfolio["holdings"]:
        print(f"\nHolding: {h['scheme_name']}")
        print(f"  Asset Type: {h['asset_type']}")
        print(f"  Purchase Price: ${h['purchase_nav']}, Current Price: ${h['current_nav']}")
        print(f"  Current Value: ${h['current_value']}, Gain: {h['gain_pct']}%")
        assert h["current_value"] > 0
        assert h["current_nav"] > 0
        assert h["gain_pct"] is not None

    print("\n=== FASTAPI ENDPOINT TESTS PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    test_routes()
