"""
Logging configuration for Odysseus.
Provides centralized logging setup with console output only.
"""

import logging
import sys
from typing import Optional
from .config import LOGGING_CONFIG


def setup_logging(
    level: Optional[str] = None,
    enable_console: bool = True
) -> logging.Logger:
    """
    Set up logging configuration for the application.
    Console output only - no file logging.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_console: Whether to enable console logging
        
    Returns:
        Configured root logger
    """
    # Get configuration
    log_level = getattr(logging, level or LOGGING_CONFIG["LEVEL"], logging.INFO)
    
    # Create root logger
    root_logger = logging.getLogger("odysseus")
    root_logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Console handler only
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_formatter = logging.Formatter(
            "%(levelname)s - %(name)s - %(message)s"
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # Prevent propagation to root logger
    root_logger.propagate = False
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    # Ensure main logger is set up
    if not logging.getLogger("odysseus").handlers:
        setup_logging()
    
    return logging.getLogger(f"odysseus.{name}")

