from typing import List
from StratDaemon.integration.robinhood import RobinhoodIntegration
from StratDaemon.models.crypto import CryptoAsset

rh_integration = RobinhoodIntegration()
positions: List[CryptoAsset] = rh_integration.get_crypto_positions()
print(positions)
