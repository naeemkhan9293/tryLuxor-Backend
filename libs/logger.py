import logging
import os


class ColoredFormatter(logging.Formatter):
    """
    A custom formatter that adds color to log messages based on their level.
    """

    COLORS = {
        "DEBUG": "\033[94m",  # Blue
        "INFO": "\033[92m",  # Green
        "WARNING": "\033[93m",  # Yellow
        "ERROR": "\033[91m",  # Red
        "CRITICAL": "\033[95m",  # Magenta
        "RESET": "\033[0m",  # Reset color
    }

    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt=fmt, datefmt=datefmt) # Removed style=style as it's default and causing Pylance error
        self.last_levelname = None

    def format(self, record):
        newline_prefix = ""
        if self.last_levelname is not None and self.last_levelname != record.levelname:
            newline_prefix = "\n"
        self.last_levelname = record.levelname

        log_message = super().format(record)
        return f"{newline_prefix}{self.COLORS.get(record.levelname, self.COLORS['RESET'])}{log_message}{self.COLORS['RESET']}"


def get_logger(name: str) -> logging.Logger:
    """
    Configures and returns a logger instance.

    Args:
        name: The name of the logger, typically __name__ of the calling module.

    Returns:
        A configured logging.Logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())

    # Ensure handlers are not duplicated if get_logger is called multiple times
    if not logger.handlers:
        # Use the custom colored formatter
        formatter = ColoredFormatter(
            "%(levelname)s - %(name)s - %(message)s -----> %(asctime)s"
        )

        # Console handler
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        # Optional: File handler (uncomment to enable file logging)
        # log_file = "app.log"
        # fh = logging.FileHandler(log_file)
        # fh.setFormatter(formatter)
        # logger.addHandler(fh)

    return logger
