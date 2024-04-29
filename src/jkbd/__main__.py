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
                logger.error(
                    f"Received error (likely controller disconencted), waiting 1s:\n{e}"
                )
                time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
