from enum import Enum
import time
from StratDaemon.utils.constants import RESTART_WAIT_TIME
from StratDaemon.utils.funcs import restart_program


class ExceptionType(Enum):
    ORDER_FAILED = 0
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
            lst_exc: BrokerException | None = None
            while attempts < max_retries:
                try:
                    return func(*args, **kwargs)
                except BrokerException as re:
                    lst_exc = re
                    if re.exception_type in {
                        ExceptionType.ORDER_NOT_FILLED,
                        ExceptionType.ORDER_FAILED,
                    }:
                        break
                    print(
                        f"Attempt {attempts + 1} failed: {re.exception_type.name} {re.message}"
                    )
                    attempts += 1
                    if attempts < max_retries:
                        time.sleep(wait_time)
            if lst_exc and lst_exc.exception_type == ExceptionType.FAILED_TO_FETCH_DATA:
                print(
                    f"Restarting program due to {lst_exc.exception_type.name} {lst_exc.message}"
                )
                time.sleep(RESTART_WAIT_TIME)
                restart_program()
            else:
                lst_exc.message += f" after max {attempts + 1} attempts"
                raise lst_exc

        return wrapper

    return retry_logic
