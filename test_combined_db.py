import sys
from pathlib import Path

# Set up project root in sys.path
_PROJECT_ROOT = str(Path(__file__).resolve().parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from services.db import init_db, get_db_connection, add_holding, get_holdings, delete_holding

def main():
    print("=== Testing Combined Portfolio Database Layer ===")
    
    print("\n1. Initializing database...")
    init_db()
    print("Database initialized successfully.")
    
    # Check connection type (PostgreSQL or SQLite)
    conn = get_db_connection()
    conn_type = type(conn).__name__
    print(f"Connection Type: {conn_type}")
    conn.close()
    
    user_id = "test_user_999"
    
    # Clean any existing test records first
    print("\nCleaning any existing test entries...")
    h_before = get_holdings(user_id)
    for h in h_before:
        delete_holding(h["id"])
    print("Cleaned.")
    
    print("\n2. Adding a stock holding...")
    add_holding(
        user_id=user_id,
        asset_type="stock",
        symbol="AAPL",
        units=50.0,
        purchase_date="2025-01-01",
        purchase_price=175.50
    )
    print("Stock holding added successfully.")
    
    print("\n3. Adding a mutual fund holding...")
    add_holding(
        user_id=user_id,
        asset_type="mutual_fund",
        symbol="Axis Large Cap Fund - Regular Growth",
        units=1500.0,
        purchase_date="2024-05-12",
        purchase_price=55.20
    )
    print("Mutual fund holding added successfully.")
    
    print("\n4. Retrieving holdings...")
    holdings = get_holdings(user_id)
    print(f"Retrieved {len(holdings)} holdings:")
    
    for h in holdings:
        print(f" - ID: {h['id']}, Asset Type: {h['asset_type']}, Symbol: {h['symbol']}, Units: {h['units']}, Purchase Price: ${h['purchase_price']:.2f}, Date: {h['purchase_date']}")
        
    assert len(holdings) == 2, f"Expected 2 holdings, got {len(holdings)}"
    assert any(h["asset_type"] == "stock" and h["symbol"] == "AAPL" for h in holdings), "Stock AAPL not found!"
    assert any(h["asset_type"] == "mutual_fund" and h["symbol"] == "Axis Large Cap Fund - Regular Growth" for h in holdings), "Mutual fund not found!"
    
    print("\n5. Testing deletion...")
    for h in holdings:
        print(f"Deleting holding ID {h['id']}...")
        delete_holding(h["id"])
        
    holdings_after = get_holdings(user_id)
    print(f"Retrieved {len(holdings_after)} holdings after deletion.")
    assert len(holdings_after) == 0, f"Expected 0 holdings, got {len(holdings_after)}"
    
    print("\n=== DATABASE LAYER TEST PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    main()
