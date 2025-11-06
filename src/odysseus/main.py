"""
Odysseus - Music Discovery Tool
Main entry point for the refactored application.
"""

import sys
from pathlib import Path

# Handle direct execution (python src/odysseus/main.py)
# Check if we're being run directly (not as a module)
try:
    # Try to access __package__ - if it doesn't exist, we're running directly
    _package = __package__
except NameError:
    _package = None

if _package is None:
    # We're being run directly, add src directory to path
    # __file__ is src/odysseus/main.py, so parent.parent is src/
    _script_path = Path(__file__).resolve()
    src_path = _script_path.parent.parent  # src/
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    # Use absolute imports
    from odysseus.core import setup_logging, get_logger
    from odysseus.core.validation import validate_and_raise
    from odysseus.ui.cli import OdysseusCLI
else:
    # Use relative imports (running as module)
    from .core import setup_logging, get_logger
    from .core.validation import validate_and_raise
    from .ui.cli import OdysseusCLI

# Set up logging
logger = setup_logging()


def main():
    """Main entry point."""
    logger.debug("Starting Odysseus Music Discovery Tool")
    try:
        # Validate configuration on startup
        try:
            validate_and_raise()
            logger.debug("Configuration validation passed")
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            raise
        
        cli = OdysseusCLI()
        cli.run()
    except KeyboardInterrupt:
        logger.debug("Application interrupted by user")
        raise
    except Exception as e:
        logger.exception("Unhandled exception occurred")
        raise
    finally:
        logger.debug("Application shutting down")


if __name__ == "__main__":
    main()
