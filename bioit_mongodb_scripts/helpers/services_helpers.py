import logging
import signal
from typing import Any

from concurrent_log_handler import ConcurrentTimedRotatingFileHandler


class Cancellation:
    """
    Class to define the cancellation token
    """

    def __init__(self):
        """
        initializes the token to false
        """
        self.cancelled = False

        # signal handler will be executed when a SIGINT/SIGTERM signal is received
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

    def cancel(self) -> None:
        """
        Turns the cancellation token to True
        :return: None
        """
        self.cancelled = True

    def handle_shutdown(self, signum: int, frame: Any) -> None:
        """
        Handler to act on cancel_token when the signal is received.
        :param signum: int corresponding usually to either SIGINT or SIGTERM
        :param frame: current stack frame
        :return: None
        """
        self.cancel()


class DropUamqpInfo(logging.Filter):
    """
    Logging filter that drops verbose uAMQP/pyamqp records to reduce noisy information coming from the azure.servicebus
    package while preserving warnings and errors.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filters out log records from the azure.servicebus logger that are below WARNING level.
        :param record: the `logging.LogRecord` to evaluate
        :return: `True` to allow the record through, `False` to drop it
        """
        return not (record.name.startswith("azure.servicebus._pyamqp") and record.levelno < logging.WARNING)


def config_log_handlers(species: str) -> None:
    """
    configure handlers to get logs rotated once by day
    :param species: the species used in ANSIBLE playbook
    :return: None
    """
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    handler = ConcurrentTimedRotatingFileHandler(
        filename=f'/var/log/NRC_platform/{species}.log',
        when="D",
        interval=1,
        backupCount=14,
        chmod=0o777)
    formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(name)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    handler.addFilter(DropUamqpInfo())
    root.addHandler(handler)
