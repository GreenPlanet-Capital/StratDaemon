from email.message import EmailMessage
import smtplib
from StratDaemon.integration.notification.base import BaseNotification
from StratDaemon.models.crypto import CryptoOrder
from StratDaemon.utils.constants import (
    EMAIL_HOST,
    EMAIL_PORT,
    GMAIL_EMAIL,
    GMAIL_PASSWORD,
    PHONE_NUMBER,
    CARRIER_MAP,
    CARRIER,
)


class SMSNotification(BaseNotification):
    def __init__(self):
        if CARRIER not in CARRIER_MAP:
            raise ValueError(
                f"Carrier {CARRIER} is not supported. Supported carriers are: {', '.join(CARRIER_MAP.keys())}"
            )
        self.to_email = f"{PHONE_NUMBER}@{CARRIER_MAP[CARRIER]}"

    def notify_failed_order(
        self, currency_code: str, side: str, amount: int, asset_price: float
    ):
        subject, message = self.get_failed_message_and_subject(
            currency_code, side, amount, asset_price
        )
        self.send_text(subject, message)

    def notify_order(self, order: CryptoOrder) -> str:
        subject, message, uid = self.get_message_and_subject(order)
        self.send_text(subject, message)
        return uid

    def send_text(self, subject: str, message: str):
        email_message = EmailMessage()
        email_message["From"] = GMAIL_EMAIL
        email_message["To"] = self.to_email
        email_message["Subject"] = subject
        email_message.set_content(message)

        with smtplib.SMTP(host=EMAIL_HOST, port=EMAIL_PORT) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(GMAIL_EMAIL, GMAIL_PASSWORD)
            smtp.send_message(email_message)
