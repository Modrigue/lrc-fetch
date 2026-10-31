#!/usr/bin/env python3
"""
LRC Fetch - Download lyrics (.lrc files) for audio files using LRCLib API.

Parses audio files in the format: <Artist>/<Album>/<Album>/<index>. <song_name>
Supports MP3, OGG, OPUS, and AAC formats.
Extracts song duration and metadata, then downloads synced lyrics from LRCLib.
"""

import os
import re
import time
import random
import requests
from pathlib import Path
from urllib.parse import quote

try:
    from mutagen import File
    from mutagen.mp3 import MP3
except ImportError:
    print("Error: mutagen library is required. Install it with: pip install mutagen")
    exit(1)

# Optional format-specific imports (mutagen's File() handles most cases)
try:
    from mutagen.oggvorbis import OggVorbis
except ImportError:
    OggVorbis = None

try:
    from mutagen.oggopus import OggOpus
except ImportError:
    OggOpus = None

try:
    from mutagen.aac import AAC
except ImportError:
    AAC = None


def get_audio_duration(file_path):
    """Get the duration of an audio file in seconds."""
    try:
        # Try mutagen's File first (auto-detects format)
        audio = File(file_path)
        if audio is not None and audio.info:
            return audio.info.length
        
        # Fallback to specific formats if auto-detect fails
        ext = file_path.suffix.lower()
        if ext == '.mp3':
            audio = MP3(file_path)
            return audio.info.length
        elif ext == '.ogg' and OggVorbis:
            audio = OggVorbis(file_path)
            return audio.info.length
        elif ext == '.opus' and OggOpus:
            audio = OggOpus(file_path)
            return audio.info.length
        elif ext == '.aac' and AAC:
            audio = AAC(file_path)
            return audio.info.length
        
        return None
    except Exception as e:
        print(f"  Error reading duration: {e}")
        return None


def extract_metadata_from_path(file_path):
    """
    Extract artist, album, and song name from the file path.
    Expected format: <Artist>/<Album>/<Album>/<index>. <song_name>
    Supports .mp3, .ogg, .opus, .aac extensions
    """
    path_parts = Path(file_path).parts
    
    # Expected: (drive, 'MP3s', 'Artist', 'Album', 'Album', 'filename.mp3')
    # Or: ('Artist', 'Album', 'Album', 'filename.mp3')
    
    if len(path_parts) < 4:
        return None, None, None
    
    # Try to find the pattern by looking at the last 3 parts
    # The song name is the last part (filename)
    filename = path_parts[-1]
    
    # The album should be the second-to-last part
    album = path_parts[-2]
    
    # The artist should be the third-to-last part
    artist = path_parts[-3]
    
    # Clean up the filename: remove index and extension
    # Format: "01. Song Name.mp3" or "01 Song Name.mp3"
    song_name = re.sub(r'^\d+[\.\s]*', '', filename)
    # Remove all supported audio extensions
    song_name = re.sub(r'\.(mp3|ogg|opus|aac)$', '', song_name, flags=re.IGNORECASE)
    
    return artist, album, song_name


def search_lyrics(artist, track_name, album=None, duration=None, max_retries=3, synced_only=False):
    """
    Search for lyrics using LRCLib API with retry logic for rate limiting.
    
    Args:
        artist: Artist name
        track_name: Track name
        album: Album name (optional)
        duration: Track duration in seconds (optional)
        max_retries: Maximum number of retry attempts
        synced_only: If True, only return synced lyrics, not plain lyrics
    
    Returns:
        Synced lyrics if found, otherwise plain lyrics if synced_only=False, otherwise None
    """
    base_url = "https://lrclib.net/api/get"
    
    params = {
        "track_name": track_name,
        "artist_name": artist,
    }
    
    if album:
        params["album_name"] = album
    
    if duration:
        params["duration"] = round(duration)
    
    headers = {
        "User-Agent": "LRCGET v1.0.0 (https://github.com/yourusername/lrcget)"
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.get(base_url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data and data.get("syncedLyrics"):
                    return data["syncedLyrics"]
                elif data and data.get("plainLyrics"):
                    if synced_only:
                        print(f"  Only plain lyrics available (no synced lyrics)")
                        return None
                    else:
                        print(f"  Using plain lyrics (synced not available)")
                        return data["plainLyrics"]
                else:
                    print(f"  No lyrics found in response")
                    return None
            elif response.status_code == 404:
                print(f"  No lyrics found for this track")
                return None
            elif response.status_code in (429, 503):
                # Rate limited or server overloaded - honor Retry-After
                retry_after = response.headers.get("Retry-After", "5")
                try:
                    retry_after = int(retry_after)
                except ValueError:
                    retry_after = 5
                
                # Add random jitter (up to 30% of the delay)
                jitter = retry_after * 0.3 * random.random()
                wait_time = retry_after + jitter
                
                if attempt < max_retries - 1:
                    print(f"  {response.status_code} - Waiting {wait_time:.1f}s before retry {attempt + 1}/{max_retries}")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"  {response.status_code} - Max retries reached")
                    return None
            else:
                print(f"  API error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"  Error searching lyrics: {e}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"  Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            return None
    
    return None


def process_audio_folder(root_folder, skip_existing=True, synced_only=False, max_retries_per_file=3, max_retries_per_dir=2, retry_delay=1.0):
    """
    Process all audio files in the given folder and its subfolders.
    Supports MP3, OGG, OPUS, and AAC formats.

    Args:
        root_folder: Path to the audio folder
        skip_existing: If True, skip files that already have .lrc files
        synced_only: If True, only download synced lyrics (not plain lyrics)
                     Default: False (will fall back to plain lyrics if synced not available)
        max_retries_per_file: Maximum number of retries for each file (default: 3)
        max_retries_per_dir: Maximum number of retry passes for the entire folder (default: 2)
        retry_delay: Delay in seconds between processing files (default: 1.0)
    """
    root_path = Path(root_folder)
    
    if not root_path.exists():
        print(f"Error: Folder '{root_folder}' does not exist")
        return
    
    # Find all supported audio files
    audio_extensions = ['*.mp3', '*.ogg', '*.opus', '*.aac']
    audio_files = []
    for ext in audio_extensions:
        audio_files.extend(root_path.rglob(ext))
    
    if not audio_files:
        print(f"No audio files found in '{root_folder}'")
        return
    
    # Filter out files that already have .lrc files if skip_existing is True
    if skip_existing:
        audio_files = [f for f in audio_files if not f.with_suffix('.lrc').exists()]
        if not audio_files:
            print(f"All audio files already have .lrc files. Use --force to re-download.")
            return
    
    print(f"Found {len(audio_files)} audio files to process")
    print("=" * 60)
    
    total_success = 0
    total_failed = 0
    failed_files = []
    
    # Process files
    for audio_file in audio_files:
        success = process_single_file(audio_file, synced_only, max_retries=max_retries_per_file)
        if success:
            total_success += 1
        else:
            total_failed += 1
            failed_files.append(audio_file)
        
        # Add delay to respect rate limits
        time.sleep(retry_delay)
    
    # Retry failed files
    for retry_num in range(1, max_retries_per_dir + 1):
        if not failed_files:
            break
        
        print(f"\n{'=' * 60}")
        print(f"Retry pass {retry_num}/{max_retries_per_dir} - {len(failed_files)} files remaining")
        print(f"{'=' * 60}")
        
        # Add delay before retry pass
        time.sleep(5)
        
        new_failed_files = []
        for audio_file in failed_files:
            success = process_single_file(audio_file, synced_only, max_retries=max_retries_per_file)
            if success:
                total_success += 1
                total_failed -= 1
            else:
                new_failed_files.append(audio_file)
            
            # Add delay to respect rate limits
            time.sleep(retry_delay)
        
        failed_files = new_failed_files
    
    print("\n" + "=" * 60)
    print(f"Done! Success: {total_success}, Failed: {total_failed}")
    if failed_files:
        print(f"\nFailed files:")
        for f in failed_files:
            path_parts = f.parts
            if len(path_parts) >= 3:
                artist = path_parts[-3]
                album = path_parts[-2]
                print(f"  - {artist}/{album}/{f.name}")
            elif len(path_parts) >= 2:
                album = path_parts[-2]
                print(f"  - {album}/{f.name}")
            else:
                print(f"  - {f.name}")


def process_single_file(audio_file, synced_only=False, max_retries=3):
    """
    Process a single audio file and download its lyrics.
    Supports MP3, OGG, OPUS, and AAC formats.
    
    Returns:
        True if lyrics were successfully downloaded, False otherwise
    """
    print(f"\nProcessing: {audio_file.name}")
    
    # Extract metadata from path
    artist, album, song_name = extract_metadata_from_path(audio_file)
    
    if not artist or not song_name:
        print(f"  Could not extract metadata from path")
        return False
    
    print(f"  Artist: {artist}")
    print(f"  Album: {album}")
    print(f"  Song: {song_name}")
    
    # Get duration
    duration = get_audio_duration(audio_file)
    if duration:
        print(f"  Duration: {duration:.2f}s ({int(duration//60)}:{int(duration%60):02d})")
    else:
        print(f"  Could not read duration")
    
    # Search for lyrics
    lyrics = search_lyrics(artist, song_name, album, duration, synced_only=synced_only)
    
    if lyrics:
        # Save lyrics to .lrc file
        lrc_path = audio_file.with_suffix('.lrc')
        
        try:
            with open(lrc_path, 'w', encoding='utf-8') as f:
                f.write(lyrics)
            print(f"  ✓ Lyrics saved to: {lrc_path.name}")
            return True
        except Exception as e:
            print(f"  Error saving lyrics: {e}")
            return False
    else:
        return False


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python lrc-fetch.py <audio_folder> [--force] [--synced-only] [--retries-per-file N] [--retries-per-dir N] [--retry-delay N]")
        print("\nOptions:")
        print("  --force              Re-download lyrics even if .lrc file already exists")
        print("  --synced-only        Only download synced lyrics, skip if only plain available")
        print("                       (default: fall back to plain lyrics if synced not available)")
        print("  --retries-per-file N Maximum retries per file (default: 3)")
        print("  --retries-per-dir N  Maximum retry passes for the folder (default: 2)")
        print("  --retry-delay N      Delay in seconds between processing files (default: 1)")
        print("\nSupported formats: MP3, OGG, OPUS, AAC")
        print("\nExample:")
        print('  python lrc-fetch.py "PATH:\\TO\\<ARTIST>\\<ALBUM>"')
        sys.exit(1)

    audio_folder = sys.argv[1]
    skip_existing = "--force" not in sys.argv
    synced_only = "--synced-only" in sys.argv

    # Parse retry arguments
    nb_retries_per_file = 3
    nb_retries_per_dir = 2
    retry_delay = 1

    try:
        retries_file_idx = sys.argv.index("--retries-per-file")
        if retries_file_idx + 1 < len(sys.argv):
            nb_retries_per_file = int(sys.argv[retries_file_idx + 1])
    except ValueError:
        pass

    try:
        retries_dir_idx = sys.argv.index("--retries-per-dir")
        if retries_dir_idx + 1 < len(sys.argv):
            nb_retries_per_dir = int(sys.argv[retries_dir_idx + 1])
    except ValueError:
        pass

    try:
        retry_delay_idx = sys.argv.index("--retry-delay")
        if retry_delay_idx + 1 < len(sys.argv):
            retry_delay = float(sys.argv[retry_delay_idx + 1])
    except ValueError:
        pass

    process_audio_folder(audio_folder, skip_existing=skip_existing, synced_only=synced_only, max_retries_per_file=nb_retries_per_file, max_retries_per_dir=nb_retries_per_dir, retry_delay=retry_delay)


if __name__ == "__main__":
    main()
