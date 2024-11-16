from typing import Tuple
from StratDaemon.models.crypto import CryptoOrder
import uuid


class BaseNotification:
    def notify_order(self, order: CryptoOrder) -> str:
        raise NotImplementedError("Subclasses should implement this method.")

    def get_message_and_subject(self, order: CryptoOrder) -> Tuple[str, str, str]:
        subject = f"{order.side.capitalize()} {order.currency_code}"
        uid = str(uuid.uuid4())
        message = f"Your UID is {uid}."
        return subject, message, uid

    def format_price(self, price: float) -> str:
        return "{:.10f}".format(price)

    def get_failed_message_and_subject(
        self, currency_code: str, side: str, amount: int, asset_price: float
    ) -> Tuple[str, str]:
        subject = f"{side.upper()} {currency_code}"
        message = (
            f"Your StratDaemon order of {currency_code} has failed to {side}"
            f" for ${amount} at price ${self.format_price(asset_price)} due to RH API errors."
        )
        return subject, message
