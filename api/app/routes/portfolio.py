from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status

from app.models.portfolio import PortfolioCreate, PortfolioUpdate
from app.services.portfolio_service import (
    create_portfolio_record,
    delete_portfolio_record,
    get_portfolio_by_user,
    seed_portfolio_data,
    update_portfolio_record,
)

router = APIRouter()


@router.post("/portfolio", status_code=status.HTTP_201_CREATED)
def create_portfolio(payload: PortfolioCreate):
    try:
        record = create_portfolio_record(payload.dict(exclude_none=True))
        return {"message": "Portfolio holding created successfully", "record": record}
    except Exception as exc:  # pragma: no cover - defensive path
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/portfolio/{user_id}")
def get_portfolio(user_id: str):
    try:
        return get_portfolio_by_user(user_id)
    except Exception as exc:  # pragma: no cover - defensive path
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/portfolio/{portfolio_id}")
def update_portfolio(portfolio_id: int, payload: PortfolioUpdate):
    try:
        result = update_portfolio_record(portfolio_id, payload.dict(exclude_none=True))
        return result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive path
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/portfolio/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_portfolio(portfolio_id: int):
    try:
        deleted = delete_portfolio_record(portfolio_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Portfolio record {portfolio_id} was not found")
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive path
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/portfolio/setup", status_code=status.HTTP_201_CREATED)
def initialize_portfolio_data():
    count = seed_portfolio_data()
    return {"message": "Portfolio data initialized", "record_count": count}
