# Test Suite for Odysseus

This directory contains the test suite for the Odysseus music discovery tool. The tests are designed to help understand which parts of the codebase are actually used and provide code coverage metrics.

## Running Tests

### Basic Test Execution

```bash
# Run all tests
pytest

# Run tests with verbose output
pytest -v

# Run specific test file
pytest tests/test_core_container.py

# Run specific test class
pytest tests/test_core_container.py::TestContainer

# Run specific test function
pytest tests/test_core_container.py::TestContainer::test_container_initialization
```

### Running Tests with Coverage

The test suite is configured to automatically generate coverage reports. Coverage reports show which parts of the code are executed during tests.

```bash
# Run tests with coverage (using the script)
./run_tests_with_coverage.sh

# Or run directly with pytest
pytest --cov=src/odysseus --cov-report=term-missing --cov-report=html --cov-report=xml --cov-branch
```

### Coverage Reports

After running tests with coverage, you'll get:

1. **Terminal Report**: Shows coverage summary and missing lines directly in the terminal
2. **HTML Report**: Detailed interactive report at `htmlcov/index.html`
   ```bash
   open htmlcov/index.html  # macOS
   xdg-open htmlcov/index.html  # Linux
   ```
3. **XML Report**: Machine-readable report at `coverage.xml` (useful for CI/CD)

### Viewing Coverage

The HTML report provides the most detailed view:
- Shows which lines are covered (green) and which are not (red)
- Shows branch coverage (which code paths are taken)
- Allows drilling down into specific files and modules

## Test Structure

### Test Files

- `conftest.py`: Shared fixtures and test configuration
- `test_core_*.py`: Tests for core modules (container, logger, exceptions, validation)
- `test_clients_*.py`: Tests for client modules (Spotify, YouTube, etc.)
- `test_models.py`: Tests for data models
- `test_utils.py`: Tests for utility functions
- `test_main.py`: Tests for the main entry point

### Test Markers

Tests can be marked with pytest markers:

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"
```

## Understanding Coverage

### What Coverage Tells You

1. **Line Coverage**: Percentage of lines executed during tests
2. **Branch Coverage**: Percentage of code branches (if/else, try/except) executed
3. **Missing Lines**: Specific lines that were never executed

### Interpreting Results

- **High Coverage (>80%)**: Most code paths are tested
- **Medium Coverage (50-80%)**: Many code paths tested, but some areas need attention
- **Low Coverage (<50%)**: Significant portions of code are untested

### Common Scenarios

- **Unused Code**: Code with 0% coverage that's never executed might be dead code
- **Error Handling**: Code in `except` blocks might have low coverage if errors aren't triggered in tests
- **Edge Cases**: Unusual code paths might not be covered if tests only cover happy paths

## Adding New Tests

When adding new tests:

1. Follow the naming convention: `test_*.py` for files, `test_*` for functions
2. Use fixtures from `conftest.py` when possible
3. Mock external dependencies (APIs, file system, etc.)
4. Test both success and failure cases
5. Aim for high coverage of the code you're testing

## Continuous Integration

The test suite can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run tests with coverage
  run: |
    pytest --cov=src/odysseus --cov-report=xml --cov-report=term
```

## Troubleshooting

### Import Errors

If you see import errors, make sure you're running tests from the project root:

```bash
cd /path/to/odysseus
pytest
```

### Coverage Not Showing

Make sure `pytest-cov` is installed:

```bash
pip install pytest-cov
```

### Missing Dependencies

Install test dependencies:

```bash
python -m pip install -e ".[dev]"
```
