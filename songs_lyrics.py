import csv
import os
import re
import lyricsgenius

from dotenv import load_dotenv

load_dotenv()
GENIUS_TOKEN = os.getenv("GENIUS_API_TOKEN")



def parse_artist_title(display_name):
    # Split on ' - ' (first one), get artist and the rest
    if ' - ' in display_name:
        artist, rest = display_name.split(' - ', 1)
    else:
        # fallback, treat all as title
        return '', display_name

    # Remove stuff like [NCS Release], [Remix], etc.
    title = re.sub(r'\[.*?\]', '', rest).strip()
    # Remove trailing or leading spaces and dashes
    title = title.strip(" -")
    # Remove multiple spaces
    title = re.sub(' +', ' ', title)
    return artist.strip(), title.strip()

def clean_lyrics(lyrics, title):
    lines = lyrics.strip().splitlines()
    # Remove "Song Title Lyrics" line
    if lines and lines[0].strip().lower() == f"{title.lower()} lyrics":
        lines = lines[1:]
    # Remove contributor lines
    lines = [line for line in lines if "Contributor" not in line]
    # Remove empty lines at the top
    while lines and not lines[0].strip():
        lines = lines[1:]
    return "\n".join(lines)

genius = lyricsgenius.Genius(GENIUS_TOKEN, skip_non_songs=True, excluded_terms=["(Remix)", "(Live)"], remove_section_headers=True, timeout=10)

def fetch_lyrics_genius(artist, title):
    if not GENIUS_TOKEN:
        return "Genius API token is missing. Please set GENIUS_API_TOKEN in .env"

    try:
        song = genius.search_song(title, artist)
        if song and song.lyrics:
            return clean_lyrics(song.lyrics, title)
        else:
            return "Lyrics not found on Genius."
    except Exception as e:
        return f"[Lyrics Error] {str(e)}"
