from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class PortfolioCreate(BaseModel):
    user_id: str = Field(..., min_length=1)
    investor_name: str = Field(..., min_length=1)
    risk_profile: Optional[str] = None
    scheme_code: str = Field(..., min_length=1)
    scheme_name: str = Field(..., min_length=1)
    units: Decimal = Field(..., gt=0)
    purchase_nav: Decimal = Field(..., gt=0)
    current_nav: Optional[Decimal] = None
    invested_amount: Optional[Decimal] = None
    current_value: Optional[Decimal] = None
    purchase_date: Optional[date] = None


class PortfolioUpdate(BaseModel):
    investor_name: Optional[str] = None
    risk_profile: Optional[str] = None
    scheme_code: Optional[str] = None
    scheme_name: Optional[str] = None
    units: Optional[Decimal] = None
    purchase_nav: Optional[Decimal] = None
    current_nav: Optional[Decimal] = None
    invested_amount: Optional[Decimal] = None
    current_value: Optional[Decimal] = None
    purchase_date: Optional[date] = None
