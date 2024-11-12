from enum import Enum
import time


class ExceptionType(Enum):
    ORDER_REJECTED = 1
    ORDER_NOT_FILLED = 2
    FAILED_TO_FETCH_DATA = 3


class BrokerException(Exception):
    def __init__(self, message: str, exception_type: ExceptionType) -> None:
        self.message = message
        self.exception_type = exception_type

    def __str__(self) -> str:
        return f"{self.exception_type.name}: {self.message}"


def retry_function(max_retries: int, wait_time: int):
    def retry_logic(func):
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_retries:
                try:
                    return func(*args, **kwargs)
                except BrokerException as re:
                    if re.exception_type == ExceptionType.ORDER_NOT_FILLED:
                        raise re
                    print(f"Attempt {attempts + 1} failed: {re}")
                    attempts += 1
                    if attempts < max_retries:
                        time.sleep(wait_time)
            raise Exception("Function failed after maximum retries")

        return wrapper

    return retry_logic
