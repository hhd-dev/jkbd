import logging

FORMAT = "%(message)s"


def setup_logging():
    from rich.logging import RichHandler

    logging.basicConfig(
        level=logging.INFO,
        datefmt="[%H:%M]",
        format=FORMAT,
        handlers=[RichHandler()],
    )
