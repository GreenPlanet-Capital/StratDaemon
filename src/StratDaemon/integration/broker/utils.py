from enum import Enum
import time

MAX_RETRIES = 5
WAIT_TIME = 5


class ExceptionType(Enum):
    ORDER_REJECTED = 1
    ORDER_NOT_FILLED = 2


class RobinhoodException(Exception):
    def __init__(self, message: str, exception_type: ExceptionType) -> None:
        self.message = message
        self.exception_type = exception_type

    def __str__(self) -> str:
        return f"{self.exception_type.name}: {self.message}"


def retry_function(func):
    def wrapper(*args, **kwargs):
        attempts = 0
        while attempts < MAX_RETRIES:
            try:
                return func(*args, **kwargs)
            except RobinhoodException as re:
                if re.exception_type == ExceptionType.ORDER_NOT_FILLED:
                    raise re
                print(f"Attempt {attempts + 1} failed: {re}")
                attempts += 1
                if attempts < MAX_RETRIES:
                    time.sleep(WAIT_TIME)
        raise Exception("Function failed after maximum retries")

    return wrapper
