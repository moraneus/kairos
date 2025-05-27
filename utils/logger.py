# utils/logger.py

"""
Provides a utility function for obtaining configured logger instances.
This helps centralize logger configuration and usage.
"""
import logging

# Here we can customize the default log level and format here if needed.
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

_configured_loggers = {}


def get_logger(name: str, level: int = DEFAULT_LOG_LEVEL, log_format: str = DEFAULT_LOG_FORMAT) -> logging.Logger:
    """
    Retrieves a logger instance with the specified name.
    If the logger has already been configured, it returns the existing instance.
    Otherwise, it configures a new logger with a basic console handler.

    Args:
        name: The name for the logger (typically __name__ of the calling module).
        level: The logging level (e.g., logging.INFO, logging.DEBUG).
        log_format: The format string for log messages.

    Returns:
        A configured logging.Logger instance.
    """
    if name in _configured_loggers:
        return _configured_loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent adding multiple handlers if the logger (e.g. root) was already configured.
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        formatter = logging.Formatter(log_format)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    _configured_loggers[name] = logger
    return logger
