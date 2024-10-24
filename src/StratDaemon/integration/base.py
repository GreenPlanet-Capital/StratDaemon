from typing import List
from Quantify.positions.position import Position


class BaseIntegration:
    def __init__(self) -> None:
        self.authenticate()

    def authenticate(self) -> None:
        raise NotImplementedError

    def get_crypto_positions(self) -> List[Position]:
        raise NotImplementedError