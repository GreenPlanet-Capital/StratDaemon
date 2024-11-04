from datetime import datetime
from typing import List
from pydantic import BaseModel, Field
from StratDaemon.models.crypto import CryptoOrder


class Portfolio(BaseModel):
    timestamp: datetime
    value: float
    buy_power: float
    holdings: List[CryptoOrder] = Field(default_factory=list)