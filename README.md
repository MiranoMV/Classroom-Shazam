🎵 Classroom Shazam – Local Audio Recognition App
A Python/Streamlit web app for music recognition – identify a song by recording or uploading a sample. Features lyric fetching, spectrogram visualizations, and your own local music database.

🚀 Features
Record or upload audio to recognize songs
Add songs to your local fingerprint database (MP3, WAV, FLAC…)
Spectrogram and fingerprint visualizations
Lyrics fetching from Genius.com
Works offline and locally
Lightweight, private, and fast

🛠️ Setup & Installation

0. First of all Install VS Studio, Python, and Python extension in VS Studio

1. Clone the repo, write this in your terminal:
git clone https://github.com/YOUR-USERNAME/mini-shazam.git
cd mini-shazam


2. Create a virtual environment (optional, but recommended):
python -m venv venv
source venv/bin/activate    # On Linux/Mac
venv\Scripts\activate       # On Windows

3. Install dependencies:
pip install -r requirements.txt

If you get errors for pyaudio or sounddevice, see the Troubleshooting section.

4. Create music_wavs, music_mp3s folders and upload desired songs

▶️ Running the App
Just run:
streamlit run app.py

This will open your browser at http://localhost:8501.
On your laptop/PC: You can record using your built-in or external microphone, or upload a file.
On your phone: Open your local server IP in your mobile browser on the same Wi-Fi, and use the upload function.


📲 Mobile Use
The Record button will use your browser/device’s microphone.
To access from your phone, get your PC’s IP address (e.g., 192.168.1.123) and visit http://192.168.1.123:8501 in your phone’s browser (both must be on the same Wi-Fi).
File uploads work from any device/browser.

🎵 Adding Songs to Database
Go to Add a song to your database in the app sidebar.
Upload a file (MP3, WAV, etc.), enter a display name, and (optionally) a Spotify link.
The app will convert and fingerprint the song when enter or the button is pressed.

🔧 Troubleshooting
If your microphone isn’t recognized, see platform-specific instructions in the Wiki or the “Issues” section.
For large music libraries, more RAM may be needed. 
For errors with sounddevice, ensure you have the proper OS-level drivers.

📝 Project Structure
app.py – Main Streamlit app.
fingerprinting.py – Audio fingerprinting functions.
build_database.py – Database building script.
songs_db.py – Song info management.
songs_lyrics.py – Lyrics fetching/cleaning.
music_wavs/ – Your audio files.
music_fingerprints.db – SQLite database (created after first run).

📚 Credits
Inspired by Shazam algorithm
Lyrics from Genius.com
Built with Streamlit, librosa, pydub, sounddevice, sqlite3.

🙋 FAQ
Can I run this on my phone?
Yes! Use the upload feature from your phone’s browser. For recording, the browser will use your phone mic if accessed over Wi-Fi.
Is my data private?
100%. Everything runs locally, nothing is uploaded anywhere.
Can I add more songs?
Yes! You can add as many songs as your PC has memory for.
Feel free to open an issue or discussion for help!


