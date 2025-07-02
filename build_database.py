import os
import sqlite3
import librosa
from pydub import AudioSegment
from fingerprinting import preprocess_audio, get_peaks, generate_fingerprints
from db_utils import create_tables_and_indices, song_in_db, add_song_to_db, add_fingerprints_bulk

AUDIO_EXTS = (".mp3", ".m4a", ".flac", ".ogg", ".aac", ".wma", ".opus", ".alac", ".wav")
SONG_FOLDER = "music_wavs"
DB_FILE = "music_fingerprints.db"

def convert_to_wav(src, dst, sr=44100):
    try:
        audio = AudioSegment.from_file(src)
        audio = audio.set_channels(1)
        audio = audio.set_frame_rate(sr)
        audio.export(dst, format="wav")
        print(f"  ✅ Converted {src} to {dst}")
        return True
    except Exception as e:
        print(f"  ❌ Conversion failed for {src}: {e}")
        return False

def build_database(song_folder=SONG_FOLDER, db_file=DB_FILE):
    conn = sqlite3.connect(db_file)
    create_tables_and_indices(conn)

    # --- Convert to WAV if needed ---
    for filename in os.listdir(song_folder):
        ext = os.path.splitext(filename)[1].lower()
        if ext in AUDIO_EXTS and ext != ".wav":
            src = os.path.join(song_folder, filename)
            dst = os.path.join(song_folder, os.path.splitext(filename)[0] + ".wav")
            if not os.path.exists(dst):
                convert_to_wav(src, dst)

    # --- Fingerprint all new WAVs ---
    files = [f for f in os.listdir(song_folder) if f.lower().endswith(".wav")]
    total = len(files)
    for idx, filename in enumerate(files, 1):
        if song_in_db(conn, filename):
            print(f"({idx}/{total}) Already fingerprinted: {filename}")
            continue
        print(f"({idx}/{total}) Fingerprinting: {filename}")
        path = os.path.join(song_folder, filename)
        try:
            y, sr = librosa.load(path, sr=None, mono=True)
            y, sr = preprocess_audio(y, sr)
            peaks = get_peaks(y, sr)
            fingerprints = generate_fingerprints(peaks)
            print(f"    Peaks: {len(peaks)} | Fingerprints: {len(fingerprints)}")
            if not fingerprints:
                print("    ⚠️ No fingerprints extracted, skipping.")
                continue
            song_id = add_song_to_db(conn, filename)
            add_fingerprints_bulk(conn, song_id, fingerprints)
            print(f"    ✅ Done: {filename}")
        except Exception as e:
            print(f"    ❌ Error processing {filename}: {e}")

    conn.close()
    print(f"\nAll songs processed and indexed! Database: {db_file}")

if __name__ == "__main__":
    if not os.path.exists(SONG_FOLDER):
        print(f"Folder '{SONG_FOLDER}' does not exist!")
    elif not os.listdir(SONG_FOLDER):
        print(f"Folder '{SONG_FOLDER}' is empty!")
    else:
        build_database()
