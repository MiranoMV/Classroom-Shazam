import streamlit as st
import os
import librosa
import numpy as np
import matplotlib.pyplot as plt
import librosa.display
import sounddevice as sd
import soundfile as sf
from collections import Counter
from pydub import AudioSegment
import matplotlib.cm as cm
import io
import time
import sqlite3

# === Custom Modules (ensure these are consistent) ===
from fingerprinting import preprocess_audio, get_peaks, generate_fingerprints
from songs_db import load_songs, add_song
from songs_lyrics import parse_artist_title, clean_lyrics, fetch_lyrics_genius
from db_utils import song_in_db, add_song_to_db, add_fingerprints_bulk
from build_database import build_database, convert_to_wav

# === Config & Constants ===
SONG_FOLDER = "music_wavs"
DB_FILE = "music_fingerprints.db"
AUDIO_EXTS = (".mp3", ".m4a", ".flac", ".ogg", ".aac", ".wav", ".wma", ".opus", ".alac")
N_FFT = 1024
HOP_LENGTH = 512
SR_QUERY = 8000
FREQ_MIN = 32
FREQ_MAX = 4096

os.makedirs(SONG_FOLDER, exist_ok=True)

# === Recognize Function (for SQLite) ===
def parse_offset(db_offset):
    if isinstance(db_offset, int):
        return db_offset
    if isinstance(db_offset, bytes):
        return int.from_bytes(db_offset, byteorder="little", signed=True)
    if isinstance(db_offset, str):
        return int(db_offset)
    raise ValueError(f"Unknown offset type: {type(db_offset)} - {db_offset}")

def recognize(query_path, db_file=DB_FILE, show_benchmark=True):
    t0 = time.perf_counter()
    y, sr = librosa.load(query_path, sr=None, mono=True)
    y, sr = preprocess_audio(y, sr)
    peaks = get_peaks(y, sr)
    fingerprints = generate_fingerprints(peaks)
    if not fingerprints:
        # Let the caller (page) display info; just return None
        return None, None
    hash_to_times = {}
    for h, t in fingerprints:
        if isinstance(h, bytes):
            h = h.decode("utf-8")
        hash_to_times.setdefault(h, []).append(t)
    hashes = list(hash_to_times.keys())

    offset_counter = Counter()
    BATCH = 900
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute("CREATE INDEX IF NOT EXISTS idx_hash ON fingerprints(hash)")
    t_db = time.perf_counter()

    for i in range(0, len(hashes), BATCH):
        batch_hashes = hashes[i:i+BATCH]
        placeholders = ",".join("?" for _ in batch_hashes)
        c.execute(
            f"SELECT hash, song_id, offset FROM fingerprints WHERE hash IN ({placeholders})",
            batch_hashes
        )
        for db_hash, song_id, db_offset in c.fetchall():
            db_offset = parse_offset(db_offset)
            for t in hash_to_times.get(db_hash, []):
                offset_counter[(song_id, db_offset - t)] += 1

    if not offset_counter:
        conn.close()
        # Let the caller display info if needed
        return None, None

    (best_song_id, best_delta), match_count = offset_counter.most_common(1)[0]
    c.execute("SELECT filename FROM songs WHERE id=?", (best_song_id,))
    row = c.fetchone()
    conn.close()
    t1 = time.perf_counter()

    # Just return results; let caller handle UI
    if row:
        # If caller wants, can access timing here
        return row[0], match_count
    return None, None

# === Caching for Spectrograms/Peaks ===
@st.cache_data(show_spinner=False)
def get_full_song_audio(song_path):
    y, sr = librosa.load(song_path, sr=SR_QUERY, mono=True, duration=15)
    y, sr = preprocess_audio(y, sr)
    return y, sr

@st.cache_data(show_spinner=False)
def get_peaks_plot_data(song_path):
    y, sr = librosa.load(song_path, sr=SR_QUERY, mono=True, duration=15)
    y, sr = preprocess_audio(y, sr)
    peaks = get_peaks(y, sr)
    return y, sr, peaks

# === Plotting Helpers ===
def plot_debug_spectrogram_img_fast(y, sr, title="Spectrogram", progress_callback=None):
    S = np.abs(librosa.stft(y, n_fft=N_FFT, hop_length=HOP_LENGTH))
    if progress_callback: progress_callback(40)
    S_db = librosa.amplitude_to_db(S, ref=np.max)
    if progress_callback: progress_callback(80)
    fig, ax = plt.subplots(figsize=(8, 3))
    librosa.display.specshow(S_db, sr=sr, hop_length=HOP_LENGTH, x_axis='time', y_axis='log', cmap='magma', ax=ax)
    ax.set_title(title)
    ax.set_ylim(FREQ_MIN, FREQ_MAX)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=120)
    plt.close(fig)
    buf.seek(0)
    if progress_callback: progress_callback(100)
    return buf

def plot_spectrogram_peaks_connections_fast(
        y, sr, peaks, fan_value=10, top_n=360, title="Spectrogram + Peaks + Connections"):
    S = np.abs(librosa.stft(y, n_fft=N_FFT, hop_length=HOP_LENGTH))
    S_db = librosa.amplitude_to_db(S, ref=np.max)
    fig, ax = plt.subplots(figsize=(8, 3))
    librosa.display.specshow(S_db, sr=sr, hop_length=HOP_LENGTH, x_axis='time', y_axis='log', cmap='magma', ax=ax)
    ax.set_title(title)
    ax.set_ylim(FREQ_MIN, FREQ_MAX)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)
    max_frame = S_db.shape[1]
    peaks_plot = [p for p in peaks if p[1] < max_frame and p[0] < len(freqs)]
    # Only top_n most powerful peaks for clarity
    if len(peaks_plot) > 0:
        peak_strengths = [S_db[f, t] for f, t in peaks_plot]
        idx = np.argsort(peak_strengths)[-top_n:]
        peaks_display = [peaks_plot[i] for i in idx]
    else:
        peaks_display = []
    colors = cm.viridis(np.linspace(0, 1, max(len(peaks_display), 1)))
    peaks_sorted = sorted(peaks_display, key=lambda x: x[1])
    for i, (f1, t1) in enumerate(peaks_sorted):
        color = colors[i]
        for j in range(1, fan_value):
            if i + j < len(peaks_sorted):
                f2, t2 = peaks_sorted[i + j]
                dt = t2 - t1
                if 5 < dt <= 120:
                    freq1 = freqs[f1]
                    time1 = librosa.frames_to_time([t1], sr=sr, hop_length=HOP_LENGTH, n_fft=N_FFT)[0]
                    freq2 = freqs[f2]
                    time2 = librosa.frames_to_time([t2], sr=sr, hop_length=HOP_LENGTH, n_fft=N_FFT)[0]
                    ax.plot([time1, time2], [freq1, freq2], color=color, alpha=0.22, linewidth=0.7, zorder=1)
    if peaks_display:
        times_idx = [p[1] for p in peaks_display]
        freq_bins = [p[0] for p in peaks_display]
        times = librosa.frames_to_time(times_idx, sr=sr, hop_length=HOP_LENGTH, n_fft=N_FFT)
        freqs_plot = freqs[freq_bins]
        ax.scatter(times, freqs_plot, color='cyan', s=26, zorder=2, edgecolors='black', linewidths=0.5)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf

# === Session State True Reset ===
def do_true_reset():
    if "history" not in st.session_state:
        st.session_state["history"] = []
    for k in list(st.session_state.keys()):
        if k not in ("slider_record_sec", "query_upload", "history"):
            del st.session_state[k]
    st.session_state["app_stage"] = "choose"
    st.session_state["recording"] = False
    st.session_state["record_start"] = 0
    st.session_state["record_duration"] = st.session_state.get("slider_record_sec", 6)
    st.session_state["audio_buffer"] = None
    st.session_state["query_path"] = None
    st.session_state["recog_result"] = None
    st.session_state["recog_path"] = None
    st.session_state["do_reset"] = False
    st.rerun()
if st.session_state.get("do_reset", False):
    do_true_reset()



# === Page Functions ===
def show_choose_page():
    # Title
    st.markdown("<h1 style='font-weight: 700; text-align:center;'>🎵 Mini Shazam</h1>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:1.22em; text-align:center;'>Identify a song by recording or uploading!<br>Get lyrics, see its audio fingerprint, and more.</div>", unsafe_allow_html=True)

    # Vinyl GIF
    vinyl_gif_url = "https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExbzB6cnlucWQyc3ZiaXc2c3Bpdm96Y3o2d2xmd3gybDczamtpcmNhbSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/h4HgOdLMIyomSiFh0I/giphy.gif"
    st.markdown(f"""<div style='display: flex; justify-content: center; align-items: center; margin: 1.7em 0 1.6em 0;'><img src="{vinyl_gif_url}" alt="Spinning Vinyl" width="220" height="220" style="border-radius:50%; box-shadow:0 3px 32px #0005;"></div>""", unsafe_allow_html=True)

    # Main menu buttons
    st.markdown("### How would you like to recognize your song?")
    col_rec, col_up = st.columns(2)
    with col_rec:
        if st.button("🎤 Record with Microphone", key="choose_record", use_container_width=True, type="primary"):
            st.session_state["app_stage"] = "record"
            st.rerun()
    with col_up:
        if st.button("⬆️ Upload Audio File", key="choose_upload", use_container_width=True, type="primary"):
            st.session_state["app_stage"] = "upload"
            st.rerun()

    # Add song to DB (expander)
    with st.expander("➕ Add a song to your database"):
        st.info("Upload any song (MP3, FLAC, WAV, OGG, ...). For best results, use clean studio versions!")
        uploaded_song = st.file_uploader("Choose a song to add:", type=[e[1:] for e in AUDIO_EXTS])
        song_name = st.text_input("Display name for the song:", "")
        spotify_url = st.text_input("Spotify link (optional):", "")
        add_btn = st.button("Add song to database 🎶", use_container_width=True)
        if uploaded_song and song_name and add_btn:
            ext = os.path.splitext(uploaded_song.name)[1].lower()
            file_path = os.path.join(SONG_FOLDER, song_name + ".wav")
            if ext == ".wav":
                with open(file_path, "wb") as f:
                    f.write(uploaded_song.read())
            elif ext in AUDIO_EXTS:
                temp_path = os.path.join(SONG_FOLDER, "temp_input" + ext)
                with open(temp_path, "wb") as f:
                    f.write(uploaded_song.read())
                try:
                    audio = AudioSegment.from_file(temp_path)
                    audio.export(file_path, format="wav")
                    os.remove(temp_path)
                except Exception as e:
                    st.error(f"Failed to convert uploaded file: {e}")
                    os.remove(temp_path)
                    file_path = None
            else:
                st.error("Unsupported file format!")
                file_path = None
            if file_path:
                st.success(f"✅ Added {song_name}.wav to your database!")
                add_song(song_name + ".wav", song_name, spotify_url)
                build_database()
                st.info("Database updated!")

    # Last recognized songs (history, up to 5)
    if "history" in st.session_state and st.session_state["history"]:
        st.markdown("### Last Recognized Songs")
        for item in reversed(st.session_state["history"][-5:]):
            display_name = item['display_name']
            spotify_url = item['spotify_url']
            timestamp = item['timestamp']
            if "open.spotify.com/track/" in spotify_url:
                spotify_id = spotify_url.split("/track/")[1].split("?")[0]
                st.markdown(
                    f"""<div style="margin-bottom: 1.1em;">
                        <iframe src="https://open.spotify.com/embed/track/{spotify_id}"
                            width="100%" height="80" frameborder="0"
                            style="border-radius:16px; box-shadow:0 2px 10px #0004;"
                            allowtransparency="true" allow="encrypted-media"></iframe>
                        <div style="text-align:right; color:#b6dbfc; font-size:0.95em; margin-top:0.2em;">
                            <span style='color:#aaa;'>at {timestamp}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown(
                    f"""<div style="margin-bottom:0.85em; background:#232b3c; border-radius:14px; padding:0.9em 1.2em;">
                        <b style="color:#35d2ea;">{display_name}</b>
                        <div style="text-align:right; color:#b6dbfc; font-size:1.01em; margin-top:0.15em; margin-bottom:-0.3em;">
                            <span style='color:#aaa;'>at {timestamp}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

def show_record_page():
    st.markdown("#### Record a sample with your microphone")
    record_sec = st.slider("Seconds to record:", 3, 15, 6, key="slider_record_sec")
    cd_sr = 44100
    if not st.session_state.get("recording", False):
        if st.button("Start Recording 🎙️", key="record_start_btn", use_container_width=True, type="primary"):
            st.session_state["recording"] = True
            st.session_state["record_start"] = time.time()
            st.session_state["record_duration"] = record_sec
            st.session_state["audio_buffer"] = None
            st.rerun()
    elif st.session_state["recording"]:
        duration = st.session_state["record_duration"]
        start = st.session_state["record_start"]
        now = time.time()
        elapsed = now - start
        remaining = int(duration - elapsed + 1)
        if st.session_state.get("audio_buffer") is None:
            st.session_state["audio_buffer"] = sd.rec(
                int(duration * cd_sr), samplerate=cd_sr, channels=1, dtype='float32'
            )
            st.rerun()
        if elapsed < duration:
            bar_width = min(int((elapsed / duration) * 100), 100)
            st.progress(bar_width, text=f"🎤 Recording... {remaining}s left")
            time.sleep(0.09)
            st.rerun()
        else:
            sd.wait()
            temp_path = "query.wav"
            rec = st.session_state.get("audio_buffer")
            if rec is not None:
                sf.write(temp_path, rec.flatten(), cd_sr)
            st.success("Recorded! 🎵")
            st.session_state["query_path"] = temp_path
            st.session_state["recording"] = False
            st.session_state["audio_buffer"] = None
            st.session_state["app_stage"] = "result"
            st.rerun()
    if st.button("⬅️ Go Back", key="back_record", use_container_width=True):
        st.session_state["app_stage"] = "choose"
        st.rerun()

def show_upload_page():
    st.markdown("#### Upload a short audio sample (WAV, MP3, FLAC, etc, 6-10s, clear sound).")
    uploaded_query = st.file_uploader("Upload song sample", type=[e[1:] for e in AUDIO_EXTS], key="query_upload2")
    if uploaded_query:
        temp_input_path = "query_input" + os.path.splitext(uploaded_query.name)[1].lower()
        with open(temp_input_path, "wb") as f:
            f.write(uploaded_query.read())
        temp_wav_path = "query.wav"
        if temp_input_path.endswith(".wav"):
            os.rename(temp_input_path, temp_wav_path)
        else:
            convert_to_wav(temp_input_path, temp_wav_path)
            os.remove(temp_input_path)
        st.session_state["query_path"] = temp_wav_path
        st.session_state["app_stage"] = "result"
        st.rerun()
    if st.button("⬅️ Go Back", key="back_upload", use_container_width=True):
        st.session_state["app_stage"] = "choose"
        st.rerun()

def show_result_page():
    query_path = st.session_state.get("query_path", None)
    if query_path and os.path.exists(query_path):
        if ("recog_result" not in st.session_state or st.session_state.get("recog_path") != query_path):
            with st.spinner("🎶 Analyzing and recognizing the song..."):
                best_song, match_count = recognize(query_path)
                songs_info = load_songs()
            st.session_state["recog_result"] = (best_song, match_count, songs_info)
            st.session_state["recog_path"] = query_path
        else:
            best_song, match_count, songs_info = st.session_state["recog_result"]
        if best_song:

            # Save result to history if not a duplicate
            history = st.session_state.get("history", [])
            info = songs_info.get(best_song, {})
            entry = {
                "song": best_song,
                "display_name": info.get("display_name", best_song),
                "match_count": match_count,
                "spotify_url": info.get("spotify_url", ""),
                "timestamp": time.strftime("%H:%M:%S")
            }
            if not history or history[-1]["song"] != best_song:
                history.append(entry)
                st.session_state["history"] = history


            display_name = info.get('display_name', best_song)
            spotify_url = info.get('spotify_url', '')
            st.markdown(f"""
                    <div style="
                        background: linear-gradient(90deg,#212C3C,#173955);
                        border-radius: 18px;padding: 1.2em 1.3em 0.9em 1.3em;
                        margin-bottom: 1.1em;
                        box-shadow: 0 2px 10px #0003;
                    ">
                    <div style="
                        font-size: 1.6em; 
                        font-weight: 700; 
                        color: #38f9d7; 
                        letter-spacing:0.01em; 
                        margin-bottom:0.2em;">
                            {display_name}
                        </div>
                        <div style="font-size:1.07em; color:#9ae8e9;">
                            🔎 Matched with <b>{match_count}</b> fingerprints
                        </div>
                    </div> """, unsafe_allow_html=True)
            if "open.spotify.com/track/" in spotify_url:
                spotify_id = spotify_url.split("/track/")[1].split("?")[0]
                embed_html = f'''
                <iframe src="https://open.spotify.com/embed/track/{spotify_id}"
                        width="100%" height="360" frameborder="0"
                        style="border-radius:18px; margin:0.7em 0; background:#232b3c;"
                        allowtransparency="true" allow="encrypted-media"></iframe>
                '''
                st.markdown(embed_html, unsafe_allow_html=True)
            elif spotify_url:
                st.markdown(f"[🔗 Open in Spotify]({spotify_url})", unsafe_allow_html=True)
            st.success(f"**Recognized:** {display_name}")


            # Lyrics section (fetch on demand)
            artist, title = parse_artist_title(display_name)
            lyrics_state_key = f"lyrics_{best_song}"
            if lyrics_state_key not in st.session_state:
                st.session_state[lyrics_state_key] = None
            show_lyrics = st.checkbox("Show Lyrics", key=f"lyrics_toggle_{best_song}")
            if show_lyrics and st.session_state[lyrics_state_key] is None:
                with st.spinner("Fetching lyrics from Genius..."):
                    lyrics = fetch_lyrics_genius(artist, title)
                st.session_state[lyrics_state_key] = lyrics

            if show_lyrics:
                lyrics = st.session_state.get(lyrics_state_key, "")
                if lyrics and lyrics.strip() and not lyrics.lower().startswith('lyrics not found'):
                    cleaned = clean_lyrics(lyrics, title)
                    st.subheader("🎼 Lyrics")
                    st.code(cleaned)
                else:
                    st.info("No lyrics found for this song.")
            
            st.markdown("---")

            # Query waveform & constellation
            st.subheader("🎤 Your Query Sample")
            show_waveform = st.checkbox("Show Query Waveform & Peaks", key="show_waveform_peaks")

            if show_waveform:
                y, sr = librosa.load(st.session_state["query_path"], sr=SR_QUERY, mono=True, duration=15)
                y, sr = preprocess_audio(y, sr)
                peaks = get_peaks(y, sr)
                duration = len(y) / sr
                fig1, ax1 = plt.subplots(figsize=(8, 2.5))
                librosa.display.waveshow(y, sr=sr, ax=ax1, color='#3ad1e6')
                ax1.set_title("Raw Waveform (Query)")
                ax1.set_xlim(0, duration)
                st.pyplot(fig1)
                plt.close(fig1)
                st.audio(query_path, format="audio/wav")

                # Spectrogram
                # Query constellation plot (same as DB)
                show_query_const = st.checkbox("Show Query Constellation Plot", key="show_query_const")
                if show_query_const:
                    y_query, sr_query = librosa.load(query_path, sr=SR_QUERY, mono=True, duration=15)
                    y_query, sr_query = preprocess_audio(y_query, sr_query)
                    peaks_query = get_peaks(y_query, sr_query)
                    buf = plot_spectrogram_peaks_connections_fast(y_query, sr_query, peaks_query, fan_value=5, top_n=60,title="Query Sample: Spectrogram + Peaks + Connections")
                    st.image(buf, use_container_width=True)

            st.markdown("---")
        
            # Spectrogram visualizations
            st.subheader("🔊 Audio Fingerprint (Spectrogram)")
            song_path = os.path.join(SONG_FOLDER, best_song)
            y_full, sr_full = get_full_song_audio(song_path)
            classic_img_key = f"classic_spectrogram_img_{best_song}"
            if classic_img_key not in st.session_state:
                progress = st.progress(0, text="Preparing full-song spectrogram...")
                def prog_cb(val): progress.progress(val, text="Preparing full-song spectrogram...")
                st.session_state[classic_img_key] = plot_debug_spectrogram_img_fast(
                    y_full, sr_full, "Spectrogram of recognized song", progress_callback=prog_cb
                )
                progress.empty()
            st.image(st.session_state[classic_img_key], use_container_width=True)
            y_short, sr_short, peaks_short = get_peaks_plot_data(song_path)
            peaks_img_key = f"peaks_spectrogram_img_{best_song}"
            if peaks_img_key not in st.session_state:
                st.session_state[peaks_img_key] = None
            show_peaks = st.checkbox("Show Peaks & Connections", key=f"showpeaksbtn_{best_song}")
            if show_peaks:
                if st.session_state[peaks_img_key] is None:
                    st.session_state[peaks_img_key] = plot_spectrogram_peaks_connections_fast(
                        y_short, sr_short, peaks_short, fan_value=5, top_n=60,
                        title="Spectrogram + Peaks + Connections"
                    )
                st.image(st.session_state[peaks_img_key], use_container_width=True)
            st.markdown("---")
            st.button("🔄 Start Over", key="reset_btn", use_container_width=True, on_click=lambda: st.session_state.update({"do_reset": True}))
        else:
            st.error("❌ No match found. Try a longer/clearer sample, or add more songs to your database.")


# === Main ===
def main():
    app_stage = st.session_state.get("app_stage", "choose")
    if app_stage == "choose":
        show_choose_page()
    elif app_stage == "record":
        show_record_page()
    elif app_stage == "upload":
        show_upload_page()
    elif app_stage == "result":
        show_result_page()

    st.caption("Made with Streamlit · Local, fast and private · By Milan Dragacevac!")

if __name__ == "__main__":
    main()