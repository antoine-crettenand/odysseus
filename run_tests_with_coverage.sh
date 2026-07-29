#!/bin/bash
# Script to run tests with coverage reporting

set -e

echo "Running tests with coverage..."
echo "================================"

# Run pytest with coverage
pytest tests/ -v --cov=src/odysseus --cov-report=term-missing --cov-report=html --cov-report=xml --cov-branch

echo ""
echo "================================"
echo "Coverage report generated!"
echo ""
echo "View HTML report: open htmlcov/index.html"
echo "XML report: coverage.xml"
