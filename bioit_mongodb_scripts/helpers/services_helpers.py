import logging
from logging import Logger, handlers
from typing import Any, Optional


class Cancellation:
    """
    Class to define the cancellation token
    """

    def __init__(self):
        """
        initializes the token to false
        """
        self.cancelled = False

    def cancel(self) -> None:
        """
        Turns the cancellation token to True
        :return: None
        """
        self.cancelled = True


_cancel_token: Optional[Cancellation] = None


def register_cancellation_token(ct: Cancellation) -> None:
    """
    Registers the cancellation token to be used in the signal handler
    :param ct: Cancellation token to register
    :return: None
    """
    global _cancel_token
    _cancel_token = ct


def handle_shutdown(signum: int, frame: Any) -> None:
    """
    Handler to act on cancel_token when the signal is received.
    :param signum: int corresponding usually to either SIGINT or SIGTERM
    :param frame: current stack frame
    :return: None
    """
    if _cancel_token is not None:
        _cancel_token.cancel()

# def config_log_handlers(species: str, log_name: str) -> None:
#  logger = logging.getLogger(log_name)
#  logger.setLevel(logging.INFO)
#  handler = handlers.TimedRotatingFileHandler(f'/var/log/{log_name}_service/{log_name}_{species}.log', when="D", interval=1, backupCount=14)
#  formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
#  handler.setFormatter(formatter)
#  logger.addHandler(handler)
