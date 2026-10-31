# LRCFetch - Lyrics Downloader

Download synced lyrics (.lrc files) for your audio collection using the free LRCLib API.

## Features

- Parses audio files in the format: `<Artist>/<Album>/<Album>/<Index>. <SongName>`
- Supports MP3, OGG, OPUS, and AAC formats
- Extracts song duration from audio metadata
- Searches LRCLib API for synced lyrics
- Saves lyrics as .lrc files alongside your audio files
- Respects API rate limits with automatic delays
- Automatically retries failed files up to 2 additional times with increasing delays

## Installation

1. Install Python 3.7 or higher
2. Install required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the script with the path to the album folder:

```bash
python lrc-fetch.py "PATH\TO\COLLECTION\<ARTIST>\<ALBUM>"
```

Or recursively process an artist folder:

```bash
python lrc-fetch.py "PATH\TO\COLLECTION\<ARTIST>\<ALBUM>"
```

Or recursively process a artists/albums collection:

```bash
python lrc-fetch.py "PATH\TO\COLLECTION"
```

### Options

- `--force` - Re-download lyrics even if .lrc file already exists
- `--synced-only` - Only download synced lyrics, skip if only plain lyrics are available
                    (default: fall back to plain lyrics if synced not available)
- `--retries-per-file N` - Maximum retries per file (default: 3)
- `--retries-per-dir N` - Maximum retry passes for the folder (default: 2)
- `--retry-delay N` - Delay in seconds between processing files (default: 1.0)

Examples:
```bash
# Download synced lyrics, fall back to plain if synced not available (default)
python lrc-fetch.py "PATH\TO\COLLECTION\<ARTIST>\<ALBUM>"

# Only download synced lyrics, skip if only plain available
python lrc-fetch.py "PATH\TO\COLLECTION\<ARTIST>\<ALBUM>" --synced-only

# Re-download all lyrics (overwrite existing .lrc files)
python lrc-fetch.py "PATH\TO\COLLECTION\<ARTIST>\<ALBUM>" --force

# Increase retry limits for slower connections
python lrc-fetch.py "PATH\TO\COLLECTION\<ARTIST>\<ALBUM>" --retries-per-file 5 --retries-per-dir 3

# Increase delay between requests to avoid rate limiting
python lrc-fetch.py "PATH\TO\COLLECTION\<ARTIST>\<ALBUM>" --retry-delay 1.0
```

## Folder Structure

The script expects the following folder structure:

```
Music/
└── <ARTIST>/
    └── <ALBUM>/
        └── <ALBUM>/
            ├── 01. Song 1 Name.mp3
            ├── 02. Song 2 Name.ogg
            ├── 03. Song 3 Name.opus
            └── ...
```

After running, .lrc files will be created alongside the audio files:

```
Music/
└── <ARTIST>/
    └── <ALBUM>/
        └── <ALBUM>/
            ├── 01. Song 1 Name.mp3
            ├── 01. Song 1 Name.lrc
            ├── 02. Song 2 Name.ogg
            ├── 02. Song 2 Name.lrc
            ├── 03. Song 3 Name.opus
            ├── 03. Song 3 Name.lrc
            └── ...
```

## API Details

This script uses the free LRCLib API (https://lrclib.net). The API:
- Requires no API key for basic use
- Has generous rate limits (~90 requests/min for identified clients)
- Returns both synced and plain lyrics
- Requires track duration for better matching accuracy

## Rate Limiting

The script automatically:
- Adds a 300ms delay between requests
- Respects the `Retry-After` header if rate limited
- Identifies itself with a proper User-Agent header

For heavy usage, consider registering your application at https://lrclib.net/developers to get higher rate limits.
