import json
import queue
import re
import subprocess
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from urllib.parse import urlparse

import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD

LABELS = {4320: "8k", 2160: "4k", 1440: "2k", 1080: "1080", 720: "720", 480: "480", 360: "360"}
ORANGE = "#F97316"
GREEN = "#51CF66"
RED = "#FF6B6B"
GREY = "#868E96"
BLUE = "#74C0FC"


class App(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)
        self.title("yt-dlp GUI")
        self.minsize(600, 500)
        self.url = tk.StringVar()
        self.out_dir = Path.home() / "Downloads"
        self.out = tk.StringVar(value=str(self.out_dir))
        self.choice = tk.StringVar()
        self.extract_format = tk.StringVar(value="mp3")
        self.last_drop = None
        self.progress_value = tk.DoubleVar()
        self.status = tk.StringVar(value="Paste a link, then fetch.")
        self.log = queue.Queue()
        self.proc = None
        self.worker = None
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=("#F3F6FB", "#1F1F1F"))
        self.build()
        self.after(80, self.poll_log)

    def build(self):
        pad = ctk.CTkFrame(self, corner_radius=20)
        pad.pack(fill="both", expand=True, padx=18, pady=18)

        row = ctk.CTkFrame(pad, fg_color="transparent")
        row.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(row, text="URL").pack(side="left", padx=(0, 10))
        self.url_entry = ctk.CTkEntry(row, textvariable=self.url, corner_radius=12, height=34)
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.url_entry.bind("<Return>", lambda e: self.fetch())
        self.url_entry.bind("<Command-v>", self.on_paste_key)
        self.url_entry.bind("<Control-v>", self.on_paste_key)
        ctk.CTkButton(row, text="Paste & Fetch", command=self.paste_url, corner_radius=12, height=34, width=124,
                       fg_color=BLUE, text_color="#1A0F02", hover_color="#4DABF7").pack(side="left")

        body = ctk.CTkFrame(pad, corner_radius=16)
        body.pack(fill="both", expand=True, pady=(0, 12))
        ctk.CTkLabel(body, text="Quality", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=16, pady=(14, 8))
        self.quality_inner = ctk.CTkScrollableFrame(body, fg_color="transparent", corner_radius=0)
        self.quality_inner.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        footer = ctk.CTkFrame(pad, fg_color="transparent")
        footer.pack(fill="x", pady=(0, 8))
        dir_row = ctk.CTkFrame(footer, fg_color="transparent")
        dir_row.pack(fill="x")
        ctk.CTkLabel(dir_row, text="Output").pack(side="left", padx=(0, 10))
        ctk.CTkEntry(dir_row, textvariable=self.out, corner_radius=12, height=34).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(dir_row, text="Browse", command=self.browse, corner_radius=12, height=34, width=96,
                       fg_color=GREY, text_color="#FFFFFF", hover_color="#6C757D").pack(side="left")

        actions = ctk.CTkFrame(footer, fg_color="transparent")
        actions.pack(fill="x", pady=10)
        ctk.CTkButton(actions, text="Download", command=self.download, corner_radius=12, height=36, width=118,
                       fg_color=GREEN, text_color="#FFFFFF", hover_color="#37B24D").pack(side="left")
        self.cancel = ctk.CTkButton(actions, text="Cancel", command=self.cancel_download, corner_radius=12, height=36, width=96,
                                     fg_color=RED, text_color="#FFFFFF", hover_color="#E03131", state="disabled")
        self.cancel.pack(side="left", padx=10)
        self.bar = ctk.CTkProgressBar(actions, variable=self.progress_value, width=220, corner_radius=8,
                                      progress_color=ORANGE)
        self.bar.pack(side="left", padx=10)

        drop = ctk.CTkFrame(pad, corner_radius=16)
        drop.pack(fill="x", pady=(8, 8))
        ctk.CTkLabel(drop, text="Extract audio from video file", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=16, pady=(14, 8))
        self.drop_zone = ctk.CTkLabel(drop, text="Drag and drop a video here\n(or click to select)",
                                      corner_radius=12, fg_color=("#ECEFF4", "#2A2A2A"), text_color=("gray25", "gray85"),
                                      height=88, cursor="hand2")
        self.drop_zone.pack(fill="x", padx=16, pady=(0, 10))
        fmt_row = ctk.CTkFrame(drop, fg_color="transparent")
        fmt_row.pack(fill="x", padx=16, pady=(0, 14))
        ctk.CTkLabel(fmt_row, text="Output format").pack(side="left", padx=(0, 10))
        ctk.CTkRadioButton(fmt_row, text="MP3", variable=self.extract_format, value="mp3").pack(side="left", padx=(0, 14))
        ctk.CTkRadioButton(fmt_row, text="M4A", variable=self.extract_format, value="m4a").pack(side="left")
        ctk.CTkButton(fmt_row, text="Select and extract", command=self.select_and_extract, corner_radius=12, height=34, width=150).pack(side="right")

        if DND_FILES_AVAILABLE:
            self.drop_zone.drop_target_register(DND_FILES)
            self.drop_zone.dnd_bind("<<Drop>>", self.on_drop)
        self.drop_zone.bind("<Button-1>", lambda e: self.select_and_extract())

        ctk.CTkLabel(pad, textvariable=self.status, wraplength=560).pack(fill="x", pady=(4, 0))

        import tkinter as tk
        badge = tk.Label(self, text='#ckpt-yt-dlp-"customtkinter" v0.1.8', bg=ORANGE, fg="#1A0F02",
                         font=("Courier", 11), cursor="hand2", padx=10, pady=6)
        badge.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)
        badge.bind("<Button-1>", lambda e: messagebox.showinfo("Changes", "v0.1.8: migrated to CustomTkinter."))

    def valid_url(self, url):
        parsed = urlparse(url.strip())
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)

    def browse(self):
        chosen = filedialog.askdirectory(initialdir=self.out.get())
        if chosen:
            self.out.set(chosen)

    def fetch(self):
        url = self.url.get().strip()
        if not self.valid_url(url):
            self.status.set("Enter a valid http(s) URL.")
            return
        self.status.set("Fetching formats...")
        self.clear_quality()
        self.start_worker(self.fetch_worker, url)

    def fetch_worker(self, url):
        cmd = ["yt-dlp", "--no-playlist", "--dump-single-json", url]
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            self.log.put(("error", p.stderr.strip() or "Fetch failed."))
            return
        try:
            data = json.loads(p.stdout)
        except json.JSONDecodeError:
            self.log.put(("error", "Could not parse yt-dlp output."))
            return
        heights = sorted({f.get("height") for f in data.get("formats", []) if f.get("height")}, reverse=True)
        standard = sorted({h for h in heights if h in LABELS}, reverse=True)
        if not standard:
            standard = heights
        title = data.get("title", "")
        self.log.put(("formats", standard, title))

    def clear_quality(self):
        for child in self.quality_inner.winfo_children():
            child.destroy()

    def render_quality(self, heights, title):
        self.clear_quality()
        ctk.CTkLabel(self.quality_inner, text=title[:70] if title else "Available options",
                     anchor="w").pack(anchor="w", pady=(0, 6))
        if heights:
            ctk.CTkRadioButton(self.quality_inner, text="Best (highest available)", variable=self.choice,
                                value="v:best").pack(anchor="w", padx=4, pady=2)
            for h in heights:
                label = LABELS.get(h, f"{h}")
                ctk.CTkRadioButton(self.quality_inner, text=f"{label} video + audio", variable=self.choice,
                                    value=f"v:{h}").pack(anchor="w", padx=4, pady=2)
        ctk.CTkFrame(self.quality_inner, height=1, fg_color=("gray80", "gray30")).pack(fill="x", pady=8)
        ctk.CTkRadioButton(self.quality_inner, text="Audio only: M4A", variable=self.choice, value="a:m4a").pack(anchor="w", padx=4, pady=2)
        ctk.CTkRadioButton(self.quality_inner, text="Audio only: MP3", variable=self.choice, value="a:mp3").pack(anchor="w", padx=4, pady=2)
        if heights:
            self.choice.set("v:best")
        else:
            self.choice.set("a:m4a")
        self.status.set("Formats loaded.")

    def download(self):
        url = self.url.get().strip()
        if not self.valid_url(url):
            self.status.set("Enter a valid http(s) URL.")
            return
        selected = self.choice.get()
        if not selected:
            self.status.set("Choose a quality or audio option.")
            return
        out_dir = Path(self.out.get()).expanduser()
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.status.set(f"Output folder error: {e}")
            return
        self.bar.set(0)
        self.status.set("Starting download...")
        self.cancel.configure(state="normal")
        self.start_worker(self.download_worker, url, selected, str(out_dir))

    def download_worker(self, url, selected, out_dir):
        if selected.startswith("v:"):
            kind = selected.split(":", 1)[1]
            if kind == "best":
                fmt = "bestvideo+bestaudio/best"
                bitrate = "40M"
            else:
                h = kind
                fmt = f"bestvideo[height<={h}]+bestaudio/best[height<={h}]"
                bitrate = {"360": "2M", "480": "3M", "720": "5M", "1080": "8M", "1440": "16M", "2160": "40M", "4320": "80M"}.get(h, "8M")
            template = str(Path(out_dir) / "%(title)s [%(height)sp].%(ext)s")
            post = f"Merger+ffmpeg:-c:v h264_videotoolbox -b:v {bitrate} -c:a aac -b:a 192k -movflags +faststart"
            cmd = ["yt-dlp", "--no-playlist", "-f", fmt, "--merge-output-format", "mp4", "--postprocessor-args", post, "-o", template, url]
        else:
            audio_format = selected.split(":", 1)[1]
            template = str(Path(out_dir) / "%(title)s.%(ext)s")
            cmd = ["yt-dlp", "--no-playlist", "-x", "--audio-format", audio_format, "--audio-quality", "0", "-o", template, url]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            self.log.put(("line", line))
        rc = self.proc.wait()
        self.proc = None
        if rc == 0:
            self.log.put(("done", "Download complete."))
        else:
            self.log.put(("error", f"yt-dlp exited {rc}."))

    def cancel_download(self):
        if self.proc:
            self.proc.terminate()
            self.status.set("Cancelled.")
            self.cancel.configure(state="disabled")

    def paste_url(self):
        try:
            import tkinter as tk
            self.url.set(self.clipboard_get().strip())
            self.status.set("Pasted from clipboard; fetching...")
            self.fetch()
        except Exception:
            self.status.set("Clipboard is empty or unavailable.")

    def on_paste_key(self, event):
        self.after(50, self.auto_fetch_after_paste)
        return None

    def auto_fetch_after_paste(self):
        if self.valid_url(self.url.get()):
            self.fetch()

    def on_drop(self, event):
        files = self.tk.splitlist(event.data)
        for path in files:
            self.start_audio_extraction(path)
            break

    def select_and_extract(self):
        path = filedialog.askopenfilename(title="Select a video", filetypes=[("Video files", "*.mp4 *.mkv *.mov *.webm *.avi *.m4v"), ("All files", "*.*")])
        if path:
            self.start_audio_extraction(path)

    def start_audio_extraction(self, path):
        self.last_drop = path
        self.status.set(f"Extracting audio from {Path(path).name}...")
        threading.Thread(target=self.extract_audio_worker, args=(path, self.extract_format.get(), self.out.get()), daemon=True).start()

    def extract_audio_worker(self, path, audio_format, out_dir):
        source = Path(path)
        out_dir = Path(out_dir).expanduser()
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.log.put(("error", f"Output folder error: {e}"))
            return
        output = out_dir / f"{source.stem}.{audio_format}"
        if audio_format == "mp3":
            cmd = ["ffmpeg", "-y", "-i", str(source), "-vn", "-c:a", "libmp3lame", "-q:a", "2", str(output)]
        else:
            cmd = ["ffmpeg", "-y", "-i", str(source), "-vn", "-c:a", "aac", "-b:a", "192k", str(output)]
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode == 0:
            self.log.put(("done", f"Audio saved: {output}"))
        else:
            tail = (p.stderr or "Extract failed").splitlines()[-3:]
            self.log.put(("error", " | ".join(tail)))

    def start_worker(self, target, *args):
        self.cancel.configure(state="disabled")
        self.worker = threading.Thread(target=target, args=args, daemon=True)
        self.worker.start()

    def poll_log(self):
        try:
            while True:
                item = self.log.get_nowait()
                kind = item[0]
                if kind == "line":
                    text = item[1]
                    m = re.search(r"\[download\]\s+(\d+(?:\.\d+)?)%", text)
                    if m:
                        self.progress_value.set(float(m.group(1)))
                        self.bar.set(float(m.group(1)) / 100.0)
                    self.status.set(text[:150])
                elif kind == "formats":
                    self.render_quality(item[1], item[2])
                elif kind == "done":
                    self.progress_value.set(100)
                    self.bar.set(1.0)
                    self.status.set(item[1])
                    self.cancel.configure(state="disabled")
                elif kind == "error":
                    self.status.set(item[1])
                    self.cancel.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(80, self.poll_log)


DND_FILES_AVAILABLE = True

if __name__ == "__main__":
    import tkinter as tk
    App().mainloop()
