from datetime import datetime
from pydantic import BaseModel, Field
import pandera as pa


class CryptoAsset(BaseModel):
    created_at: datetime
    updated_at: datetime
    currency_code: str
    quantity: float
    initial_cost_basis: float
    initial_quantity: float


class CryptoHistorical(pa.DataFrameModel):
    open: float = pa.Field()
    close: float = pa.Field()
    high: float = pa.Field()
    low: float = pa.Field()
    volume: float = pa.Field()
    timestamp: datetime = pa.Field()


class CryptoOrder(BaseModel):
    side: str = Field(pattern="^(buy|sell)$")
    currency_code: str
    asset_price: float
    amount: float
    limit_price: float  # -1 means market order
    quantity: float
    timestamp: datetime


class CryptoLimitOrder(BaseModel):
    side: str = Field(pattern="^(buy|sell)$")
    currency_code: str
    limit_price: float
    amount: float
