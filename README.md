# yt-dlp GUI

Tkinter app for yt-dlp downloads with macOS Quick Look compatible H.264/AAC output and neumorphic UI.

## Run

```bash
python3 app.py
```

## macOS app

Double-click `yt-dlp.app` (not tracked; release asset on GitHub).

## Features
- Fetch quality options from URL.
- Best available and standard resolutions.
- Audio-only M4A/MP3.
- Paste URL and auto-fetch.
- Drag-and-drop/click-to-select video for audio extraction.
- Neumorphic styling.

## Windows

Run from source:
```bat
install-deps.bat
run.bat
```
Requires Python, `yt-dlp`, and `ffmpeg` on PATH.

Prebuilt Windows build is available in GitHub Releases as `yt-dlp-windows.zip`.
