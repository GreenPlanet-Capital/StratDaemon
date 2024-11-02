from typing import List
from StratDaemon.models.crypto import (
    CryptoAsset,
    CryptoOrder,
    CryptoHistorical,
)
from pandera.typing import DataFrame, Series


class BaseBroker:
    def __init__(self) -> None:
        self.authenticate()

    def authenticate(self) -> None:
        raise NotImplementedError

    def get_crypto_positions(self) -> List[CryptoAsset]:
        raise NotImplementedError

    def get_crypto_historical(
        self, currency_code: str, interval: str, span: str
    ) -> DataFrame[CryptoHistorical]:
        raise NotImplementedError

    def buy_crypto_limit(
        self, currency_code: str, amount: float, limit_price: float
    ) -> CryptoOrder:
        raise NotImplementedError

    def buy_crypto_market(
        self,
        currency_code: str,
        amount: float,
        cur_df: Series[CryptoHistorical] | None,
    ) -> CryptoOrder:
        raise NotImplementedError

    def sell_crypto_limit(
        self, currency_code: str, amount: float, limit_price: float
    ) -> CryptoOrder:
        raise NotImplementedError

    def sell_crypto_market(
        self,
        currency_code: str,
        amount: float,
        cur_df: Series[CryptoHistorical] | None,
    ) -> CryptoOrder:
        raise NotImplementedError
