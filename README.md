# Odysseus - Music Discovery Tool

A comprehensive Python tool for discovering and downloading music from various sources with proper metadata handling.

## ⚠️ Legal Disclaimer

**IMPORTANT:** This software is provided for educational and personal use only. Users are responsible for ensuring that their use of this tool complies with all applicable laws and regulations in their jurisdiction, including but not limited to:

- Copyright laws
- Terms of service of third-party platforms (YouTube, Spotify, etc.)
- Intellectual property rights

**The authors and contributors of this software:**
- Do not condone or encourage copyright infringement
- Are not responsible for any misuse of this software
- Do not guarantee that downloaded content is legal in your jurisdiction
- Recommend using this tool only for content you have the legal right to download

**By using this software, you agree to:**
- Use it only for legally obtained content
- Respect the intellectual property rights of content creators
- Comply with all applicable laws and regulations
- Accept full responsibility for your use of this software

The developers of this project are not liable for any legal consequences resulting from the use or misuse of this software.

## 🚀 Usage

### First Time Setup

If you're pulling this repository for the first time on a new computer, follow these steps:

#### 1. Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- FFmpeg (required for audio extraction, conversion, and album splitting)
- Internet connection

Install FFmpeg with your system package manager, for example `brew install
ffmpeg` on macOS, `sudo apt install ffmpeg` on Debian/Ubuntu, or `winget
install Gyan.FFmpeg` on Windows.

The project is configured through `pyproject.toml`; do not run `setup.py`.

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

# Install the application and its dependencies
pip install -e .
```

For development, install the test and lint tools:

```bash
pip install -e ".[dev]"
```

#### 3. Verify Installation

```bash
# Check if the command is available
odysseus --help

# Or test with Python directly
python -m odysseus.main --help
```

#### 4. Configure API access (recommended)

Odysseus can fall back when a provider is unavailable, but authenticated,
identified requests are less likely to be denied. Set only the providers you
use:

```bash
# Uses the supported YouTube Data API instead of HTML search when present.
export YOUTUBE_API_KEY="..."

# Optional, but recommended for authenticated Discogs access.
export DISCOGS_USER_TOKEN="..."

# Required for Spotify metadata and search.
export SPOTIFY_CLIENT_ID="..."
export SPOTIFY_CLIENT_SECRET="..."

# Optional overrides. Keep a real project URL or contact address in each value.
export MUSICBRAINZ_USER_AGENT="Odysseus/1.0.0 (https://example.com/project)"
export DISCOGS_USER_AGENT="Odysseus/1.0.0 (https://example.com/project)"
```

Do not commit API keys or tokens. Without `YOUTUBE_API_KEY`, YouTube HTML
search remains available as a less reliable fallback.

### Command Line Interface

#### Search and Download a Recording

```bash
# Basic search
odysseus recording --title "title_name" --artist "artist_name"

# With album and year for better matching
odysseus recording --title "title_name" --artist "artist_name" --album "album_name" --year 1971

# Search only (no download)
odysseus recording --title "title_name" --artist "artist_name" --no-download

# Specify quality
odysseus recording --title "title_name" --artist "artist_name" --quality best
```

#### Search and Download a Release/Album

```bash
# Download entire album
odysseus release --album "album_name" --artist "artist_name"

# Download specific tracks
odysseus release --album "album_name" --artist "artist_name" --tracks "1,2,3"

# Download independent tracks concurrently (bounded to 1-4 workers)
odysseus release --album "album_name" --artist "artist_name" --jobs 3

# With year filter
odysseus release --album "album_name" --artist "artist_name" --year 1982

# Search only
odysseus release --album "album_name" --artist "artist_name" --no-download
```

#### Export releases from Spotify

```bash
# Export the unique releases represented in a playlist
odysseus spotify --mode releases --url "https://open.spotify.com/playlist/..." \
  --export releases.tsv --no-download

# Export liked-track and saved-album releases. The token needs
# the Spotify user-library-read scope.
export SPOTIFY_USER_ACCESS_TOKEN="..."
odysseus spotify --mode releases \
  --url "https://open.spotify.com/user/me/collection" \
  --collection-type both --export library.json --export-format json --no-download
```

#### Browse and Download from Discography

```bash
# Browse all releases by artist
odysseus discography --artist "artist_name"

# Filter by year
odysseus discography --artist "artist_name" --year 1970

# Browse only (no download)
odysseus discography --artist "artist_name" --no-download
```

`--jobs` is also available for `discography` and `spotify`. It defaults to
`1` for the existing sequential behavior and accepts at most `4`. Playlist
and individual-track transfers can run concurrently; full-album download and
track splitting remain sequential.

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

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## ⚠️ Security

This software implements security best practices including:
- SSL/TLS certificate verification for secure connections
- Input validation and sanitization
- Path traversal protection
- Secure handling of API credentials via environment variables

If you discover a security vulnerability, please report it responsibly.
