import logging


def configure_tick_logging() -> None:
    """Make ``tick.*`` INFO logs visible under uvicorn's default config."""
    tick_logger = logging.getLogger("tick")
    tick_logger.setLevel(logging.INFO)
    if tick_logger.handlers:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
    tick_logger.addHandler(handler)
    tick_logger.propagate = False
