import logging
import time

from .controller import controller_loop
from .log import setup_logging

logger = logging.getLogger(__name__)


def main():
    setup_logging()
    try:
        while True:
            try:
                controller_loop()
            except Exception as e:
                # from rich import get_console

                logger.error(
                    f"Received error (likely controller disconencted), waiting 1s. Error:{e}"
                )
                # get_console().print_exception()
                time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
