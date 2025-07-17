# 🎵 Classroom Shazam – Music Recognition App

This is a Shazam-like web app built with Python and Streamlit that identifies uploaded songs using audio fingerprinting.

## 🚀 Features
- Upload an audio file (`.mp3`, `.wav`, etc.)
- The app computes a unique fingerprint of the song
- It matches it against a local database of songs
- Displays the song name and additional info like lyrics

## 🧰 Requirements
Before running the app, make sure the following are installed on your system:

 1. Install Python
Go to: https://www.python.org/downloads/
Click the yellow "Download Python X.X.X" button, download the latest python version
Run the installer
IMPORTANT: Check the box that says “Add Python to PATH”
Click “Install Now”
This installs Python and pip, which is used to install other tools.

3. Install FFmpeg
Required so the app can process .mp3 files.
Download FFmpeg from here: https://www.gyan.dev/ffmpeg/builds/
Choose: “ffmpeg-release-essentials.zip”
Extract it (e.g., to C:\ffmpeg)
Add C:\ffmpeg\bin to the system PATH:
Click Windows icon and search for environment variables
Click "Edit the system environment variables"
In System Properties → Click “Environment Variables”
Under "System variables" → Find Path → Click “Edit”
Click “New” → Paste: C:\ffmpeg\bin
Click OK
Check if it works in the terminal:
```
ffmpeg -version
exit
```

### ⚠️ Important: This app starts with an empty song database.
When you first launch the app, there are no songs stored or recognized yet.

To test the app:
1. Run it normally with streamlit run app.py
2. Use the Upload a Song section in the browser
3. Once you upload a song (e.g., song.mp3), the app will:
4. Fingerprint it
5. Add it to the local database
6. Recognize it in future uploads

🧪 So the very first song you upload becomes the "known" song the app can match later.


# Finally, how to actually launch the app

### Option 1: Git (Recommended if you have Git installed)
git clone https://github.com/MiranoMV/Classroom-Shazam.git
cd classroom-shazam
This creates a local copy of the whole repository on the computer.
Open terminal in that folder (shift and right click, and click "Open in Terminal) paste text inside and run:
   `pip install -r requirements.txt`
   `streamlit run app.py`
To stop the app: press `Ctrl + C`  
To close the terminal: type `exit` and press Enter, or just close the window


### Option 2: If you don't have Git installed:
1. Download the project ZIP: https://github.com/MiranoMV/Classroom-Shazam/archive/refs/heads/main.zip
2. Extract the folder
3. Open terminal in that folder (shift and right click, and click "Open in Terminal) paste text inside and run:
   `pip install -r requirements.txt`
   `streamlit run app.py`
4. To stop the app: press `Ctrl + C`  
5. To close the terminal: type `exit` and press Enter, or just close the window

### 🎤 Genius API for Lyrics (Optional)
This app can fetch song lyrics using the Genius API.
To enable this feature:
1. Go to https://genius.com/api-clients
2. Click “Create an API Client”
3. Fill out the form (you can use dummy values)
4. Once your client is created, you'll see a Client Access Token
5. Open songs_lyrics file in your Notepad in the same folder as your app.py, and change the GENIUS_TOKEN, "your_actual_genius_api_token_here", Variable with your actual Token.
6. Click File > Save
9. Done!

If you don’t set up the token, the app will still work — but lyrics won’t appear.


---

Let me know if you need help with the setup, contact me on Github, and if a THWS Student, on BI2E 2025 Course on E-learning
