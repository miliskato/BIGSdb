import signal
import logging
from logging import handlers
from typing import Any


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

# def config_log_handlers(species: str, log_name: str) -> None:
#  logger = logging.getLogger(log_name)
#  logger.setLevel(logging.INFO)
#  handler = handlers.TimedRotatingFileHandler(f'/var/log/{log_name}_service/{log_name}_{species}.log', when="D", interval=1, backupCount=14)
#  formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
#  handler.setFormatter(formatter)
#  logger.addHandler(handler)


def config_log_handlers(species: str) -> None:
    """
    configure handlers to get logs rotated once by day
    :param species: the species used in ANSIBLE playbook
    :return: None
    """
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    handler = handlers.TimedRotatingFileHandler(f'/var/log/NRC_platform/{species}.log', when="D", interval=1, backupCount=14)
    formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(name)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    root.addHandler(handler)
