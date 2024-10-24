from typing import List
from Quantify.positions.position import Position
from StratDaemon.integration.robinhood import RobinhoodIntegration

rh_integration = RobinhoodIntegration()
positions: List[Position] = rh_integration.get_crypto_positions()
