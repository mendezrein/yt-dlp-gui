yt-dlp GUI project

Files:
- app.py: Tkinter neumorphic frontend + yt-dlp/ffmpeg controller.
- run.command: shell launcher.
- yt-dlp.app: macOS app bundle (Contents/MacOS/launcher).
- index.md: this file.

Features:
- Fetch formats from URL; auto-fetch on paste/Enter.
- Quality options: best + standard resolutions converted to H.264/AAC.
- Audio-only M4A/MP3.
- Paste URL from clipboard.
- Drag-and-drop/click-to-select video for audio extraction.
- Neumorphic UI styling.
- macOS app bundle available.

Version: v0.1.8
Change: customtkinter

Windows:
- run.bat launches app.py on Windows.
- install-deps.bat installs Python deps.
- GitHub Actions workflow builds Windows exe on tags/push.
