from StratDaemon.integration.confirmation.base import BaseConfirmation
import requests

from StratDaemon.utils.constants import CRYPTO_DB_URL


class CryptoDBConfirmation(BaseConfirmation):
    def __init__(self):
        super().__init__()

    def init_confirmation(self, uid: str) -> None:
        resp = requests.get(f"{CRYPTO_DB_URL}/init-order?uid={uid}")

        if resp.status_code != 200:
            raise Exception("Failed to initialize confirmation")

        return resp.json()

    def check_confirmation(self, uid: str) -> bool:
        resp = requests.get(f"{CRYPTO_DB_URL}/get-order?uid={uid}")

        if resp.status_code != 200:
            raise Exception("Failed to check confirmation")

        return resp.json()["order"]["confirmed"]

    def delete_confirmation(self, uid: str) -> None:
        resp = requests.get(f"{CRYPTO_DB_URL}/delete-order?uid={uid}")

        if resp.status_code != 200:
            raise Exception("Failed to delete confirmation")

        return resp.json()