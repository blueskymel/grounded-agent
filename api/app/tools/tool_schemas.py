from pydantic import BaseModel, Field
from typing import Optional

class AnalyzePriceChangeInput(BaseModel):
    sku: str = Field(..., description="SKU identifier")
    old_price: float = Field(..., gt=0, description="Old price, must be > 0")
    new_price: float = Field(..., gt=0, description="New price, must be > 0")

class TriageLowStockInput(BaseModel):
    store_id: str = Field(..., description="Store identifier")
    sku: str = Field(..., description="SKU identifier")
    on_hand: int = Field(..., ge=0, description="Units on hand, must be >= 0")
    forecast_per_day: Optional[float] = Field(None, ge=0, description="Forecasted sales per day")
    lead_time_days: Optional[int] = Field(None, ge=0, description="Lead time in days")

class DraftStoreIncidentSummaryInput(BaseModel):
    store_id: str = Field(..., description="Store identifier")
    incident_type: str = Field(..., description="Type of incident")
    duration_minutes: int = Field(..., ge=0, description="Duration in minutes, must be >= 0")

class CheckPromoComplianceInput(BaseModel):
    promo_id: str = Field(..., description="Promotion identifier")
    sku: str = Field(..., description="SKU identifier")
    price: float = Field(..., gt=0, description="Promo price, must be > 0")
    channel: Optional[str] = Field("both", description="Channel: online, store, or both")
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")
