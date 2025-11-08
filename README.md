# Odysseus - Music Discovery Tool

A comprehensive Python tool for discovering and downloading music from various sources with proper metadata handling.

## 🚀 Usage

### First Time Setup

If you're pulling this repository for the first time on a new computer, follow these steps:

#### 1. Prerequisites

- Python 3.8 or higher
- pip (Python package manager) - setuptools will be installed automatically by pip
- Internet connection

**Note:** Do not run `python setup.py` directly. Always use `pip install -e .` instead, as it automatically handles all dependencies including setuptools.

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

#### 3. Verify Installation

```bash
# Check if the command is available
odysseus --help

# Or test with Python directly
python -m odysseus.main --help
```

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

# With year filter
odysseus release --album "album_name" --artist "artist_name" --year 1982

# Search only
odysseus release --album "album_name" --artist "artist_name" --no-download
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
