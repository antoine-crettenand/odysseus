#!/usr/bin/env python3
"""
Odysseus - Music Discovery Tool
Main entry point that uses the CLI interface.
"""

from cli import OdysseusCLI


def main():
    """Main entry point."""
    cli = OdysseusCLI()
    cli.run()


if __name__ == "__main__":
    main()
