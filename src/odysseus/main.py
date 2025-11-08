"""
Odysseus - Music Discovery Tool
Main entry point for the refactored application.
"""

import sys
from pathlib import Path

try:
    _package = __package__
except NameError:
    _package = None

if _package is None:
    _script_path = Path(__file__).resolve()
    src_path = _script_path.parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    from odysseus.core import setup_logging, get_logger
    from odysseus.core.validation import validate_and_raise
    from odysseus.ui.cli import OdysseusCLI
else:
    from .core import setup_logging, get_logger
    from .core.validation import validate_and_raise
    from .ui.cli import OdysseusCLI

logger = setup_logging()


def main():
    """Main entry point."""
    logger.debug("Starting Odysseus Music Discovery Tool")
    try:
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
