"""
Tests for logging configuration.
"""

import pytest
import logging
from unittest.mock import patch, MagicMock
from odysseus.core.logger import setup_logging, get_logger


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_default(self):
        """Test setting up logging with default settings."""
        logger = setup_logging()

        assert logger.name == "odysseus"
        # Default log level is WARNING according to config
        assert logger.level == logging.WARNING
        assert len(logger.handlers) == 1

    def test_setup_logging_custom_level(self):
        """Test setting up logging with custom level."""
        logger = setup_logging(level="DEBUG")

        assert logger.level == logging.DEBUG

    def test_setup_logging_disable_console(self):
        """Test setting up logging without console output."""
        logger = setup_logging(enable_console=False)

        assert len(logger.handlers) == 0

    def test_setup_logging_prevents_duplicate_handlers(self):
        """Test that setup_logging prevents duplicate handlers."""
        logger1 = setup_logging()
        handler_count1 = len(logger1.handlers)

        logger2 = setup_logging()
        handler_count2 = len(logger2.handlers)

        assert handler_count1 == handler_count2
        assert handler_count1 == 1


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_creates_child_logger(self):
        """Test that get_logger creates a child logger."""
        setup_logging()
        logger = get_logger("test_module")

        assert logger.name == "odysseus.test_module"
        assert isinstance(logger, logging.Logger)

    def test_get_logger_sets_up_if_not_configured(self):
        """Test that get_logger sets up logging if not configured."""
        # Clear existing handlers
        root_logger = logging.getLogger("odysseus")
        root_logger.handlers.clear()

        logger = get_logger("test_module")

        assert logger.name == "odysseus.test_module"
        assert len(logging.getLogger("odysseus").handlers) > 0
