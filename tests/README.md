# Test Suite Documentation

This directory contains an extensive test suite for the Odysseus codebase.

## Test Coverage

The test suite includes comprehensive tests for:

### Models (4 test files)
- **test_models_song.py**: Tests for `SongData` and `AudioMetadata` models
- **test_models_releases.py**: Tests for `Track` and `ReleaseInfo` models
- **test_models_search_results.py**: Tests for all search result models (MusicBrainzSong, YouTubeVideo, DiscogsRelease, LastFmTrack, SpotifyTrack, GeniusSong)

### Core Modules (3 test files)
- **test_core_exceptions.py**: Tests for all custom exception classes
- **test_core_validation.py**: Tests for configuration validation utilities
- **test_core_logger.py**: Tests for logging configuration

### Utilities (4 test files)
- **test_utils_string_utils.py**: Tests for string normalization functions
- **test_utils_retry.py**: Tests for retry decorator with exponential backoff
- **test_utils_colors.py**: Tests for terminal color utilities
- **test_utils_metadata_merger.py**: Tests for metadata merging logic

### Clients (3 test files)
- **test_clients_musicbrainz.py**: Tests for MusicBrainz API client (with mocks)
- **test_clients_discogs.py**: Tests for Discogs API client (with mocks)
- **test_clients_youtube.py**: Tests for YouTube search client (with mocks)

### Services (3 test files)
- **test_services_search.py**: Tests for search service coordination
- **test_services_metadata.py**: Tests for metadata service
- **test_services_download.py**: Tests for download service

### Configuration (1 test file)
- **test_config.py**: Tests for configuration constants and settings

## Running Tests

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=src/odysseus --cov-report=html
```

### Run specific test file
```bash
pytest tests/test_models_song.py
```

### Run specific test class
```bash
pytest tests/test_models_song.py::TestSongData
```

### Run specific test
```bash
pytest tests/test_models_song.py::TestSongData::test_song_data_creation
```

### Run with verbose output
```bash
pytest -v
```

### Run with output capture disabled
```bash
pytest -s
```

## Test Fixtures

The `conftest.py` file provides shared fixtures for:
- `temp_dir`: Temporary directory for test files
- `temp_audio_file`: Temporary audio file for testing
- `mock_requests_get/post`: Mocked HTTP requests
- `mock_musicbrainz_client`: Mocked MusicBrainz client
- `mock_discogs_client`: Mocked Discogs client
- `mock_youtube_client`: Mocked YouTube client
- `sample_song_data`: Sample song data for testing
- `sample_audio_metadata`: Sample audio metadata
- Various sample search results

## Test Statistics

- **Total test files**: 18
- **Total test cases**: 233+
- **Coverage**: Models, utilities, core modules, clients, and services

## Writing New Tests

When adding new tests:

1. Follow the existing naming convention: `test_<module>_<component>.py`
2. Use descriptive test names: `test_<function>_<scenario>`
3. Use fixtures from `conftest.py` when possible
4. Mock external dependencies (APIs, file system operations)
5. Test both success and failure cases
6. Test edge cases and boundary conditions

## Dependencies

Test dependencies are listed in `requirements.txt`:
- `pytest>=6.0`
- `pytest-cov>=2.0`
- `pytest-mock>=3.0`

Install test dependencies:
```bash
pip install -r requirements.txt
```

