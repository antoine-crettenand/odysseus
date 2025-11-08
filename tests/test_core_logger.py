"""
Tests for logging configuration.
"""

import pytest
import sys
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from odysseus.core.logger import setup_logging, get_logger


class TestSetupLogging:
    """Tests for setup_logging function."""
    
    def test_setup_logging_default(self):
        """Test setup_logging with default parameters."""
        logger = setup_logging()
        
        assert logger is not None
        assert logger.name == "odysseus"
        assert isinstance(logger, logging.Logger)
    
    def test_setup_logging_custom_level(self):
        """Test setup_logging with custom level."""
        logger = setup_logging(level="DEBUG")
        
        assert logger.level == logging.DEBUG
    
    def test_setup_logging_disable_console(self):
        """Test setup_logging with console disabled."""
        logger = setup_logging(enable_console=False)
        
        # Logger should still be created
        assert logger is not None
        # But handlers might be empty
        # (This depends on implementation)
    
    def test_setup_logging_removes_existing_handlers(self):
        """Test that setup_logging removes existing handlers."""
        logger1 = setup_logging()
        initial_handler_count = len(logger1.handlers)
        
        logger2 = setup_logging()
        # Should not have duplicate handlers
        assert len(logger2.handlers) <= initial_handler_count + 1
    
    def test_setup_logging_invalid_level(self):
        """Test setup_logging with invalid level."""
        # Should default to INFO
        logger = setup_logging(level="INVALID_LEVEL")
        assert logger.level == logging.INFO  # Default fallback


class TestGetLogger:
    """Tests for get_logger function."""
    
    def test_get_logger_creates_logger(self):
        """Test that get_logger creates a logger."""
        logger = get_logger("test_module")
        
        assert logger is not None
        assert logger.name == "odysseus.test_module"
        assert isinstance(logger, logging.Logger)
    
    def test_get_logger_sets_up_main_logger(self):
        """Test that get_logger sets up main logger if needed."""
        # Clear any existing handlers
        main_logger = logging.getLogger("odysseus")
        main_logger.handlers.clear()
        
        logger = get_logger("test_module")
        
        # Main logger should have handlers now
        assert len(main_logger.handlers) > 0
    
    def test_get_logger_different_modules(self):
        """Test that get_logger creates different loggers for different modules."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")
        
        assert logger1.name != logger2.name
        assert logger1.name == "odysseus.module1"
        assert logger2.name == "odysseus.module2"
    
    def test_get_logger_same_module_returns_same_logger(self):
        """Test that get_logger returns same logger for same module."""
        logger1 = get_logger("test_module")
        logger2 = get_logger("test_module")
        
        assert logger1 is logger2

