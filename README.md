# Odysseus - Music Discovery Tool

A comprehensive Python tool for discovering and downloading music from various sources with proper metadata handling.

## 🏗️ New Architecture

The codebase has been completely refactored with proper separation of concerns and modular design:

```
src/odysseus/
├── __init__.py
├── main.py                 # Main entry point
├── core/                   # Core configuration and exceptions
│   ├── __init__.py
│   ├── config.py          # All configuration constants
│   └── exceptions.py      # Custom exceptions
├── models/                 # Data models
│   ├── __init__.py
│   ├── song.py           # Song and metadata models
│   ├── search_results.py # Search result models
│   └── releases.py       # Release and track models
├── services/              # Business logic services
│   ├── __init__.py
│   ├── search_service.py  # Search coordination
│   ├── metadata_service.py # Metadata handling
│   └── download_service.py # Download management
├── clients/               # External API clients
│   ├── __init__.py
│   ├── musicbrainz.py    # MusicBrainz API client
│   ├── youtube.py        # YouTube search client
│   └── youtube_downloader.py # YouTube download client
├── ui/                    # User interface components
│   ├── __init__.py
│   ├── cli.py           # Command-line interface
│   └── display.py       # Display formatting
└── utils/                 # Utility modules
    ├── __init__.py
    ├── colors.py        # Terminal colors
    └── metadata_merger.py # Metadata merging logic
```

## ✨ Key Improvements

### 1. **Separation of Concerns**
- **Models**: Clean data structures with validation
- **Services**: Business logic separated from UI and data access
- **Clients**: External API interactions isolated
- **UI**: User interface components separated from business logic

### 2. **Modular Design**
- Each module has a single responsibility
- Clear interfaces between components
- Easy to test and maintain
- Extensible architecture

### 3. **Better Error Handling**
- Custom exception hierarchy
- Proper error propagation
- User-friendly error messages

### 4. **Improved Code Organization**
- No more 1000+ line files
- Logical grouping of related functionality
- Clear import structure
- Consistent naming conventions

## 🚀 Usage

### First Time Setup

If you're pulling this repository for the first time on a new computer, follow these steps:

#### 1. Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Internet connection

#### 2. Clone and Install

```bash
# Clone the repository
git clone <repository-url>
cd odysseus

# Create a virtual environment (recommended)
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install the package in development mode
pip install -e .
```

#### 3. Verify Installation

```bash
# Check if the command is available
odysseus --help

# Or test with Python directly
python -m odysseus.main --help
```

#### 4. Optional: Configure Environment Variables

You can customize the behavior by setting environment variables (see [Environment Variables](#environment-variables) section below).

#### 5. Test the Installation

```bash
# Try a simple search (no download)
odysseus recording --title "Bohemian Rhapsody" --artist "Queen" --no-download
```

### Installation (Alternative Methods)

If you've already set up the environment:

```bash
# Install dependencies only
pip install -r requirements.txt

# Install in development mode (recommended for development)
pip install -e .

# Or run directly using the entry point
odysseus recording --title "Test Song" --artist "Test Artist"

# Or using Python directly
python -m odysseus.main recording --title "Test Song" --artist "Test Artist"
```

### Environment Variables

Odysseus supports configuration through environment variables. These are optional and have sensible defaults:

```bash
# Download directory (default: ./downloads in project root)
export ODYSSEUS_DOWNLOADS_DIR="/path/to/downloads"

# Logging level (default: WARNING)
export ODYSSEUS_LOG_LEVEL="DEBUG"  # DEBUG, INFO, WARNING, ERROR

# MusicBrainz configuration
export MUSICBRAINZ_REQUEST_DELAY="1.0"  # Rate limiting delay (seconds)
export MUSICBRAINZ_MAX_RESULTS="5"      # Max search results
export MUSICBRAINZ_TIMEOUT="30"         # Request timeout (seconds)

# Download configuration
export ODYSSEUS_DEFAULT_QUALITY="best"     # best, audio, worst
export ODYSSEUS_AUDIO_FORMAT="mp3"        # Audio format (mp3, wav, flac, aac, ogg)
export ODYSSEUS_MAX_CONCURRENT_DOWNLOADS="3"

# Discogs configuration (optional - for higher rate limits)
export DISCOGS_USER_TOKEN="your_token_here"  # Get token at https://www.discogs.com/settings/developers
```

### Command Line Interface

#### Search and Download a Recording

```bash
# Basic search
odysseus recording --title "Bohemian Rhapsody" --artist "Queen"

# With album and year for better matching
odysseus recording --title "Stairway to Heaven" --artist "Led Zeppelin" --album "Led Zeppelin IV" --year 1971

# Search only (no download)
odysseus recording --title "Bohemian Rhapsody" --artist "Queen" --no-download

# Specify quality
odysseus recording --title "Bohemian Rhapsody" --artist "Queen" --quality best
```

#### Search and Download a Release/Album

```bash
# Download entire album
odysseus release --album "Dark Side of the Moon" --artist "Pink Floyd"

# Download specific tracks
odysseus release --album "Abbey Road" --artist "The Beatles" --tracks "1,2,3"

# With year filter
odysseus release --album "Thriller" --artist "Michael Jackson" --year 1982

# Search only
odysseus release --album "The Wall" --artist "Pink Floyd" --no-download
```

#### Browse and Download from Discography

```bash
# Browse all releases by artist
odysseus discography --artist "The Beatles"

# Filter by year
odysseus discography --artist "Pink Floyd" --year 1970

# Browse only (no download)
odysseus discography --artist "Led Zeppelin" --no-download
```

### Advanced Usage

#### Quality Options

- `best`: Best available quality (video + audio)
- `audio`: Audio only (MP3, high quality)
- `worst`: Lowest quality (for testing)

#### Download Organization

Files are automatically organized in the following structure:
```
downloads/
└── Artist Name/
    └── Album Name (Year)/
        ├── Track 1.mp3
        ├── Track 2.mp3
        └── ...
```

## 🔧 Development

### Running Tests

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=odysseus
```

### Code Quality

```bash
# Format code
black src/

# Lint code
flake8 src/

# Type checking
mypy src/
```

## 📁 File Structure Comparison

### Before (Monolithic)
```
odysseus/
├── cli.py              # 1049 lines - Everything mixed together
├── metadata_merger.py  # 781 lines - Complex metadata logic
├── discogs_client.py   # 446 lines - API client
├── musicbrainz_client.py # 549 lines - Another API client
├── youtube_client.py   # 145 lines - YouTube client
├── youtube_downloader.py # 413 lines - Download logic
├── config.py           # 198 lines - Configuration
├── colors.py           # 138 lines - UI utilities
└── ... (many more files)
```

### After (Modular)
```
src/odysseus/
├── core/               # Configuration and exceptions
├── models/             # Data models (3 files, ~200 lines each)
├── services/           # Business logic (3 files, ~100 lines each)
├── clients/            # API clients (3 files, ~200-400 lines each)
├── ui/                 # User interface (2 files, ~200-300 lines each)
└── utils/              # Utilities (2 files, ~100-200 lines each)
```

## 🎯 Benefits

1. **Maintainability**: Each file has a clear purpose and manageable size
2. **Testability**: Individual components can be tested in isolation
3. **Extensibility**: Easy to add new features without affecting existing code
4. **Readability**: Code is organized logically and easy to navigate
5. **Reusability**: Components can be reused across different parts of the application

## 🔄 Migration Guide

The old files are still available for reference, but the new structure should be used going forward:

- `main.py` → `src/odysseus/main.py`
- `cli.py` → `src/odysseus/ui/cli.py`
- `metadata_merger.py` → `src/odysseus/utils/metadata_merger.py`
- `musicbrainz_client.py` → `src/odysseus/clients/musicbrainz.py`
- And so on...

## 🔍 Troubleshooting

### Common Issues

#### 1. Missing Dependencies

If you see an error about missing dependencies:

```bash
# Make sure you've installed all requirements
pip install -r requirements.txt

# If using a virtual environment, make sure it's activated
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate  # Windows
```

The application will automatically check for required dependencies on startup and provide helpful error messages if any are missing.

#### 2. Download Failures (403 Errors)

If you encounter 403 errors when downloading from YouTube:

```bash
# Update yt-dlp to the latest version
pip install --upgrade yt-dlp

# Or let Odysseus auto-update it
# The downloader will attempt to update yt-dlp automatically
```

The downloader uses multiple strategies to bypass restrictions, so it should work even if one strategy fails.

#### 3. No Search Results Found

- Check your internet connection
- Verify the artist name and song title spelling
- Try a more general search (e.g., just artist and title, without album)
- Check MusicBrainz website directly to see if the recording exists

#### 4. Slow Downloads

- Reduce `ODYSSEUS_MAX_CONCURRENT_DOWNLOADS` if downloading multiple files
- Check your internet connection speed
- Consider using `--quality audio` for faster audio-only downloads

#### 5. Logging Issues

Enable debug logging for more information (console output only):

```bash
export ODYSSEUS_LOG_LEVEL="DEBUG"
odysseus recording --title "Song" --artist "Artist"
```

All logging output is displayed in the console.

#### 6. Permission Errors

Ensure you have write permissions to the download directory:

```bash
# Set custom download directory with write permissions
export ODYSSEUS_DOWNLOADS_DIR="/path/to/writable/directory"
```

#### 7. Path Issues on Different Operating Systems

The application automatically detects the project root directory. If you encounter path-related issues:

- Make sure you're running from the project directory or have installed the package with `pip install -e .`
- You can explicitly set the download directory using the `ODYSSEUS_DOWNLOADS_DIR` environment variable
- The application will create necessary directories automatically if they don't exist

### Dependencies

All required dependencies are listed in `requirements.txt`. Install them with:

```bash
pip install -r requirements.txt
```

Key dependencies:
- `requests>=2.25.0`: For API calls to MusicBrainz and other services
- `mutagen>=1.45.0`: For metadata handling in audio files
- `yt-dlp>=2023.12.30`: For YouTube downloads (auto-updated by the tool)
- `rich>=13.0.0`: For beautiful terminal output and progress bars

Optional dependencies:
- `youtube-dl`: Used as a fallback if yt-dlp fails (not required)

## 📊 Features

- ✅ **MusicBrainz Integration**: Search for recordings, releases, and discographies
- ✅ **YouTube Search**: Find corresponding videos for any track
- ✅ **Automatic Metadata**: Fetches and applies cover art, album info, and track metadata
- ✅ **Organized Downloads**: Files organized by Artist/Album structure
- ✅ **Multiple Quality Options**: Best, audio-only, or custom quality
- ✅ **Progress Bars**: Real-time download progress with speed and ETA indicators
- ✅ **Retry Logic**: Automatic retries with exponential backoff for failed requests
- ✅ **Console Logging**: Detailed console output for debugging and monitoring
- ✅ **Environment Configuration**: Flexible configuration via environment variables
- ✅ **Error Recovery**: Multiple download strategies for reliability

## 🧪 Testing

The project includes a basic test suite:

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run all tests
pytest

# Run with coverage
pytest --cov=odysseus --cov-report=html

# Run specific test file
pytest tests/test_config.py
```

## 📝 Next Steps

- [x] **Testing**: Basic test structure added
- [x] **Documentation**: Enhanced README with examples and troubleshooting
- [x] **Configuration**: Environment-based configuration support
- [x] **Logging**: Proper logging throughout the application
- [x] **Error Recovery**: Retry logic with exponential backoff

Future enhancements:
- [x] **Progress bars for downloads** - Real-time download progress with speed and ETA using Rich Progress
- [ ] Add support for batch downloads from CSV/JSON files
- [ ] Add playlist support for YouTube playlists
- [ ] Add support for other music sources (Spotify, SoundCloud, etc.)
- [ ] Add GUI interface option
- [ ] Add Docker containerization
- [ ] Add CI/CD pipeline

This refactoring provides a solid foundation for future development and makes the codebase much more maintainable and professional.
