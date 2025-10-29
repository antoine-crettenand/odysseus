# Odysseus - Music Discovery Tool

A comprehensive Python tool for discovering and downloading music. Odysseus searches MusicBrainz for song information, finds corresponding YouTube videos, and allows you to download them with a powerful command-line interface.

## Features

- **MusicBrainz Integration**: Search for songs, artists, albums, and releases
- **YouTube Search**: Find videos for discovered music
- **Download Support**: Download videos or extract audio using yt-dlp
- **Multiple Quality Options**: Choose from best quality, audio-only, or specific formats
- **Three Search Modes**: Recording, Release, and Discography modes
- **Interactive CLI**: User-friendly command-line interface with clear prompts
- **Batch Downloads**: Download entire albums or multiple tracks at once
- **Smart Metadata Selection**: Choose the best metadata from multiple sources (MusicBrainz, YouTube, Discogs, Spotify, Last.fm, Genius) before downloading

## Installation

1. Clone or download this repository
2. Install required dependencies:
   ```bash
   pip install requests
   pip install yt-dlp
   ```

## Usage

Odysseus provides three main modes for music discovery and downloading:

### 1. Recording Mode - Download Individual Songs

Search and download specific recordings/songs:

```bash
python3 main.py recording --title "Bohemian Rhapsody" --artist "Queen"
```

**Options:**
- `--title, -t`: Song title to search for (required)
- `--artist, -a`: Artist name (required)
- `--album, -l`: Album name (optional)
- `--year, -y`: Release year (optional)
- `--quality, -q`: Download quality: `best`, `audio`, `worst` (default: `audio`)
- `--no-download`: Search only, do not download

**Example:**
```bash
python3 main.py recording --title "Imagine" --artist "John Lennon" --year 1971 --quality audio
```

### Metadata Selection Feature

Before downloading, Odysseus now allows you to choose the best metadata from multiple sources:

1. **Automatic Source Detection**: The tool searches MusicBrainz, YouTube, Discogs, Spotify, Last.fm, and Genius for metadata
2. **Interactive Selection**: You'll see all available metadata sources with confidence scores and completeness ratings
3. **Field-by-Field Choice**: Select the best title, artist, album, and year from different sources
4. **Download Confirmation**: Review your final metadata selection before proceeding with the download

**Example Metadata Selection:**
```
================================================================================
METADATA SOURCES
================================================================================

1. MusicBrainz
   Confidence: 0.95 | Completeness: 0.90
   Title: Bohemian Rhapsody
   Artist: Queen
   Album: A Night at the Opera
   Year: 1975
   Genre: Rock, Progressive Rock
----------------------------------------

2. YouTube
   Confidence: 0.60 | Completeness: 0.70
   Title: Queen - Bohemian Rhapsody (Official Video)
   Artist: Queen Official
   Album: A Night at the Opera
   Year: 2008
----------------------------------------

3. Discogs
   Confidence: 0.90 | Completeness: 0.80
   Title: Bohemian Rhapsody
   Artist: Queen
   Album: A Night at the Opera
   Year: 1975
   Genre: Rock
----------------------------------------
```

You can then choose which source to use for each metadata field, ensuring you get the most accurate information for your music files.

### 2. Release Mode - Download Album Tracks

Search and download tracks from a specific release/album:

```bash
python3 main.py release --album "Dark Side of the Moon" --artist "Pink Floyd"
```

**Options:**
- `--album, -l`: Album/release name to search for (required)
- `--artist, -a`: Artist name (required)
- `--year, -y`: Release year (optional)
- `--quality, -q`: Download quality: `best`, `audio`, `worst` (default: `audio`)
- `--tracks, -k`: Comma-separated track numbers (e.g., `1,3,5`)
- `--no-download`: Search only, do not download

**Examples:**
```bash
# Download all tracks from an album
python3 main.py release --album "Abbey Road" --artist "The Beatles"

# Download specific tracks only
python3 main.py release --album "Abbey Road" --artist "The Beatles" --tracks "1,2,3"
```

### 3. Discography Mode - Browse Artist's Complete Discography

Browse an artist's discography and download selected releases:

```bash
python3 main.py discography --artist "The Beatles"
```

**Options:**
- `--artist, -a`: Artist name to browse discography (required)
- `--year, -y`: Filter releases by year (optional)
- `--quality, -q`: Download quality: `best`, `audio`, `worst` (default: `audio`)
- `--no-download`: Browse only, do not download

**Examples:**
```bash
# Browse complete discography
python3 main.py discography --artist "The Beatles"

# Browse releases from a specific year
python3 main.py discography --artist "The Beatles" --year 1965
```

### General Options

All modes support:
- `--help`: Show help message
- `--version`: Show version number
- `--no-download`: Search/browse only, do not download

### Example Session

```
=== Odysseus - Music Discovery Tool ===
Version: 1.0.0
Enter song information (press Enter to skip optional fields):

Song title: Bohemian Rhapsody
Artist: Queen
Album (optional): A Night at the Opera
Release year (optional): 1975

Searching MusicBrainz for: Bohemian Rhapsody by Queen

=== MUSICBRAINZ SEARCH RESULTS ===
1. Bohemian Rhapsody
   Artist: Queen
   Album: A Night at the Opera
   Release Date: 1975-10-31
   Score: 100

Select a result (1-1) or 'q' to quit: 1

Selected: Bohemian Rhapsody by Queen

=== SEARCHING YOUTUBE ===
Search query: Queen Bohemian Rhapsody

=== YOUTUBE SEARCH RESULTS ===
1. Queen - Bohemian Rhapsody (Official Video)
   Channel: Queen Official
   Duration: 5:55
   Views: 1.2B views
   Published: 8 years ago

Would you like to download a video? (y/n): y
Select a video to download (1-1) or 'q' to skip: 1

=== DOWNLOADING VIDEO ===
Title: Queen - Bohemian Rhapsody (Official Video)
URL: https://www.youtube.com/watch?v=fJ9rUzIMcZQ

Download options:
1. Best quality video
2. Audio only (MP3)
3. Specific quality

Choose option (1-3): 2

Download completed successfully!: /path/to/downloads/Queen - Bohemian Rhapsody.mp3
```

## Project Structure

```
odysseus/
├── main.py                 # Main application entry point (uses CLI)
├── cli.py                  # Command-line interface implementation
├── config.py              # Configuration and constants
├── musicbrainz_client.py  # MusicBrainz API client
├── youtube_client.py      # YouTube search client
├── youtube_downloader.py # YouTube download functionality
├── metadata_merger.py    # Metadata merging and application
├── downloads/             # Default download directory
├── config/                # Configuration files
└── logs/                  # Log files
```

## Configuration

All settings are centralized in `config.py`:

- **API Configuration**: MusicBrainz and YouTube API settings
- **Download Settings**: Quality presets, file formats, directories
- **UI Settings**: Display options, separators, limits
- **Error Messages**: Standardized error and success messages
- **Validation Rules**: Input validation parameters

## Dependencies

- `requests`: HTTP library for API calls
- `yt-dlp`: YouTube downloader (installed automatically if missing)

## Error Handling

The tool includes comprehensive error handling for:
- Network connectivity issues
- Invalid user input
- Missing dependencies
- API rate limiting
- Download failures

## License

This project is open source. Feel free to modify and distribute.

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.
