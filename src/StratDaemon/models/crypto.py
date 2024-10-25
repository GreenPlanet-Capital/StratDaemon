from datetime import datetime
from pydantic import BaseModel


class CryptoAsset(BaseModel):
    created_at: datetime
    updated_at: datetime
    currency_code: str
    quantity: float
    initial_cost_basis: float
    initial_quantity: float
