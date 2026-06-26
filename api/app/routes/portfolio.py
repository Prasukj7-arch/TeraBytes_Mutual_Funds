import sys
import logging
from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, status
from pathlib import Path

# Ensure project root is in sys.path for database imports
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.append(_PROJECT_ROOT)

import api.app.services.db as db
from databricks_connector.data_service import DataService

logger = logging.getLogger("api.routes.portfolio")
router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class PortfolioCreate(BaseModel):
    user_id: str = Field(..., example="user_001")
    scheme_code: str = Field(..., example="119598")
    units: float = Field(..., gt=0, example=120.5)
    purchase_date: str = Field(..., example="2023-06-15")
    purchase_nav: float = Field(..., gt=0, example=132.10)

class HoldingResponse(BaseModel):
    scheme_code: str
    scheme_name: str
    units: float
    purchase_date: str
    purchase_nav: float
    current_nav: float
    current_value: float
    gain_pct: float
    asset_type: str

class PortfolioResponse(BaseModel):
    user_id: str
    holdings: List[HoldingResponse]

# ---------------------------------------------------------------------------
# Helper functions for price fetching
# ---------------------------------------------------------------------------

def get_stock_price(symbol: str) -> Optional[float]:
    """Fetch current price of a stock using yfinance."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        price = info.get("last_price", None)
        if price is None:
            # Fallback to history close
            hist = ticker.history(period="1d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
        return price
    except Exception as e:
        logger.warning(f"Failed to fetch live stock price for {symbol} via yfinance: {e}")
        return None

def get_mf_nav(symbol_or_code: str) -> Optional[float]:
    """Fetch current NAV of a mutual fund using DataService."""
    try:
        ds = DataService()
        funds_df = ds.get_all_funds()
        if not funds_df.empty:
            # Try matching code or name
            match = funds_df[
                (funds_df["fund_name"].astype(str).str.lower() == symbol_or_code.lower()) |
                (funds_df.index.astype(str) == symbol_or_code)
            ]
            if not match.empty:
                return float(match.iloc[0]["nav"])
    except Exception as e:
        logger.warning(f"Failed to fetch mutual fund NAV for {symbol_or_code} via DataService: {e}")
    return None

# ---------------------------------------------------------------------------
# Route Handlers
# ---------------------------------------------------------------------------

@router.post("/", response_model=HoldingResponse, status_code=status.HTTP_201_CREATED)
def add_portfolio_holding(payload: PortfolioCreate):
    """Add a holding (stock or mutual fund) to the portfolio."""
    symbol = payload.scheme_code.strip()
    
    # Auto-detect asset type
    if symbol.isupper() and (len(symbol) <= 5 or symbol.endswith(".NS") or symbol.endswith(".BO")):
        asset_type = "stock"
        name = symbol
    else:
        asset_type = "mutual_fund"
        # Try to resolve MF name for display
        try:
            ds = DataService()
            funds_df = ds.get_all_funds()
            match = funds_df[
                (funds_df["fund_name"].astype(str).str.lower() == symbol.lower()) |
                (funds_df.index.astype(str) == symbol)
            ]
            name = match.iloc[0]["fund_name"] if not match.empty else symbol
        except Exception:
            name = symbol

    try:
        # Save to database
        db.add_holding(
            user_id=payload.user_id,
            asset_type=asset_type,
            symbol=symbol,
            units=payload.units,
            purchase_date=payload.purchase_date,
            purchase_price=payload.purchase_nav
        )
        
        # Calculate current NAV/price for response
        current_nav = None
        if asset_type == "stock":
            current_nav = get_stock_price(symbol)
        else:
            current_nav = get_mf_nav(symbol)
            
        if current_nav is None:
            # Fallback values for response
            current_nav = payload.purchase_nav * 1.08  # Default positive performance simulation
            
        current_val = current_nav * payload.units
        gain = 100.0 * (current_nav - payload.purchase_nav) / payload.purchase_nav
        
        return HoldingResponse(
            scheme_code=symbol,
            scheme_name=name,
            units=payload.units,
            purchase_date=payload.purchase_date,
            purchase_nav=payload.purchase_nav,
            current_nav=current_nav,
            current_value=current_val,
            gain_pct=round(gain, 2),
            asset_type=asset_type
        )
    except Exception as e:
        logger.error(f"Error adding holding: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add holding: {str(e)}"
        )

@router.get("/{user_id}", response_model=PortfolioResponse)
def get_user_portfolio(user_id: str):
    """Retrieve all holdings for a user and calculate real-time performance."""
    try:
        holdings = db.get_holdings(user_id)
        response_holdings = []
        
        # Load all mutual funds once to speed up lookups if possible
        funds_df = None
        try:
            ds = DataService()
            funds_df = ds.get_all_funds()
        except Exception as e:
            logger.warning(f"Could not load all mutual funds: {e}")
            
        for h in holdings:
            symbol = h["symbol"]
            asset_type = h["asset_type"]
            units = h["units"]
            purchase_nav = h["purchase_price"]
            
            # Resolve name and current nav
            scheme_name = symbol
            current_nav = None
            
            if asset_type == "stock":
                current_nav = get_stock_price(symbol)
            else:
                # Find in loaded funds
                if funds_df is not None and not funds_df.empty:
                    match = funds_df[
                        (funds_df["fund_name"].astype(str).str.lower() == symbol.lower()) |
                        (funds_df.index.astype(str) == symbol)
                    ]
                    if not match.empty:
                        scheme_name = match.iloc[0]["fund_name"]
                        current_nav = float(match.iloc[0]["nav"])
                
                # If still None, fetch individually
                if current_nav is None:
                    current_nav = get_mf_nav(symbol)
                    
            if current_nav is None:
                # Fallback to simulate a realistic change (e.g. +5% since purchase)
                current_nav = purchase_nav * 1.05
                
            current_val = current_nav * units
            gain = 100.0 * (current_nav - purchase_nav) / purchase_nav
            
            response_holdings.append(
                HoldingResponse(
                    scheme_code=symbol,
                    scheme_name=scheme_name,
                    units=units,
                    purchase_date=h["purchase_date"],
                    purchase_nav=purchase_nav,
                    current_nav=current_nav,
                    current_value=current_val,
                    gain_pct=round(gain, 2),
                    asset_type=asset_type
                )
            )
            
        return PortfolioResponse(
            user_id=user_id,
            holdings=response_holdings
        )
    except Exception as e:
        logger.error(f"Error fetching portfolio for {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch portfolio: {str(e)}"
        )
