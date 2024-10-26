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
