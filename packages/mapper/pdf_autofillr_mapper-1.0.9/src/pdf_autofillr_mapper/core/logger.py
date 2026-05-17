import logging
import sys
from pythonjsonlogger import jsonlogger

# Create a default logger instance for modules to import
logger = logging.getLogger(__name__)

def setup_logging(log_level: str = "INFO") -> None:
    """Configure root logger for JSON output to stdout."""
    logger = logging.getLogger()
    logger.setLevel(log_level)

    logHandler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        fmt="%(name)s %(levelname)s %(message)s %(request_id)s"
    )
    logHandler.setFormatter(formatter)

    # Clear other handlers and add structured JSON handler
    if logger.hasHandlers():
        logger.handlers.clear()
    logger.addHandler(logHandler)

    # Prevent propagation if needed
    logger.propagate = False
