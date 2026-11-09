import json
import queue
import re
import subprocess
import threading
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlparse
import tkinter as tk
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_FILES_AVAILABLE = True
    APP_BASE = TkinterDnD.Tk
except ImportError:
    DND_FILES_AVAILABLE = False
    APP_BASE = tk.Tk



LABELS = {4320: "8k", 2160: "4k", 1440: "2k", 1080: "1080", 720: "720", 480: "480", 360: "360"}
BG = "#e0e5ec"
BG_DARK = "#d1d9e6"
FG = "#2d3436"
MUTED = "#636e72"
SHADOW_DARK = "#a3b1c6"
SHADOW_LIGHT = "#ffffff"
ACCENT = "#F97316"

def rounded_rect(canvas, x1, y1, x2, y2, r, **kw):
    points = [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r, x2,y2-r, x2,y2,
              x2-r,y2, x1+r,y2, x1,y2, x1,y2-r, x1,y1+r, x1,y1]
    return canvas.create_polygon(points, smooth=True, **kw)


class NeuButton(tk.Canvas):
    def __init__(self, parent, text="", command=None, width=110, height=36, radius=22, font=("Helvetica", 10, "bold"), color=None, text_color=None):
        super().__init__(parent, width=width, height=height, bg=BG, highlightthickness=0, cursor="hand2")
        self.text = text
        self.command = command
        self.radius = radius
        self.font = font
        self.color = color or BG
        self.text_color = text_color or ("#FFFFFF" if color and color != BG else FG)
        self._pressed = False
        self._enabled = True
        self.bind("<ButtonPress-1>", lambda e: self._set(True) if self._enabled else None)
        self.bind("<ButtonRelease-1>", lambda e: (self._set(False), command() if (command and self._enabled) else None))
        self.bind("<Leave>", lambda e: self._set(False))
        self.draw()

    def _set(self, pressed):
        if not self._enabled:
            return
        self._pressed = pressed
        self.draw()

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)
        self._pressed = False
        self.configure(cursor="hand2" if enabled else "arrow")
        self.draw()

    def _dark(self, hexcolor):
        if hexcolor == BG:
            return BG_DARK
        hexcolor = hexcolor.lstrip("#")
        r = max(0, int(hexcolor[0:2], 16) - 35)
        g = max(0, int(hexcolor[2:4], 16) - 35)
        b = max(0, int(hexcolor[4:6], 16) - 35)
        return f"#{r:02x}{g:02x}{b:02x}"

    def draw(self):
        self.delete("all")
        w = int(self["width"]); h = int(self["height"]); r = self.radius
        color = self.color
        dark = self._dark(color)
        if not self._enabled:
            rounded_rect(self, 2, 3, w-2, h-1, r, fill=BG_DARK, outline=SHADOW_DARK, width=0)
            self.create_text(w//2, h//2, text=self.text, fill=MUTED, font=self.font)
            return
        if color == BG:
            if self._pressed:
                rounded_rect(self, 4, 4, w-2, h-2, r, fill=BG_DARK, outline=SHADOW_DARK, width=1)
                rounded_rect(self, 3, 3, w-3, h-3, r, fill=BG, outline="", width=0)
            else:
                rounded_rect(self, 3, 4, w-1, h, r, fill=SHADOW_DARK, outline="", width=0)
                rounded_rect(self, 1, 2, w-3, h-2, r, fill=SHADOW_LIGHT, outline="", width=0)
                rounded_rect(self, 2, 3, w-2, h-1, r, fill=BG, outline="", width=0)
        else:
            offset = 2 if not self._pressed else 0
            rounded_rect(self, 3, 5, w-1, h+1, r, fill=dark, outline="", width=0)
            rounded_rect(self, 2-offset, 2-offset, w-2-offset, h-2-offset, r, fill=color, outline="", width=0)
        self.create_text(w//2, h//2, text=self.text, fill=self.text_color, font=self.font)






class App(APP_BASE):
    def __init__(self):
        super().__init__()
        self.title("yt-dlp GUI")
        self.minsize(560, 430)
        self.url = tk.StringVar()
        self.out_dir = Path.home() / "Downloads"
        self.out = tk.StringVar(value=str(self.out_dir))
        self.choice = tk.StringVar()
        self.extract_format = tk.StringVar(value="mp3")
        self.last_drop = None
        self.progress_value = tk.DoubleVar()
        self.status = tk.StringVar(value="Paste a link, then Fetch.")
        self.log = queue.Queue()
        self.proc = None
        self.worker = None
        self.configure(bg=BG)
        style = ttk.Style(self)
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure('TFrame', background=BG)
        style.configure('TLabel', background=BG, foreground=FG)
        style.configure('TLabelframe', background=BG, bordercolor=SHADOW_DARK, relief='flat')
        style.configure('TLabelframe.Label', background=BG, foreground=FG)
        style.configure('TEntry', fieldbackground=BG, foreground=FG, borderwidth=0, insertcolor=FG)
        style.configure('TRadiobutton', background=BG, foreground=FG)
        style.configure('TProgressbar', background=ACCENT, troughcolor=BG_DARK, borderwidth=0)
        self.build()
        self.after(80, self.poll_log)

    def build(self):
        pad = ttk.Frame(self, padding=14)
        pad.pack(fill="both", expand=True)
        row = ttk.Frame(pad)
        row.pack(fill="x")
        ttk.Label(row, text="URL").pack(side="left")
        url_entry = ttk.Entry(row, textvariable=self.url, width=56)
        url_entry.pack(side="left", fill="x", expand=True, padx=10)
        url_entry.bind("<Return>", lambda e: self.fetch())
        url_entry.bind("<Command-v>", self.on_paste_key)
        url_entry.bind("<Control-v>", self.on_paste_key)
        NeuButton(row, text="Paste & Fetch", command=self.paste_url, width=124, height=34, color="#74C0FC", text_color="#1A0F02").pack(side="left")
        body = ttk.Frame(pad)
        body.pack(fill="both", expand=True, pady=12)
        self.quality_box = tk.Frame(body, bg=BG, highlightthickness=1, highlightbackground=SHADOW_DARK, bd=0)
        self.quality_box.pack(fill="both", expand=True)
        qtitle = tk.Label(self.quality_box, text="Quality", bg=BG, fg=FG, font=("Helvetica", 12, "bold"))
        qtitle.pack(anchor="w", padx=12, pady=(10, 4))
        self.quality_inner = tk.Frame(self.quality_box, bg=BG)
        self.quality_inner.pack(fill="both", expand=True, padx=8, pady=(0, 10))
        footer = ttk.Frame(pad)
        footer.pack(fill="x", pady=(8, 0))
        dir_row = ttk.Frame(footer)
        dir_row.pack(fill="x")
        ttk.Label(dir_row, text="Output").pack(side="left")
        ttk.Entry(dir_row, textvariable=self.out, width=46).pack(side="left", fill="x", expand=True, padx=10)
        NeuButton(dir_row, text="Browse", command=self.browse, width=92, height=34, color="#868E96", text_color="#FFFFFF").pack(side="left")
        actions = ttk.Frame(footer)
        actions.pack(fill="x", pady=10)
        NeuButton(actions, text="Download", command=self.download, width=118, height=36, color="#51CF66", text_color="#FFFFFF").pack(side="left")
        self.cancel = NeuButton(actions, text="Cancel", command=self.cancel_download, width=96, height=36, color="#FF6B6B", text_color="#FFFFFF")
        self.cancel.pack(side="left", padx=10)
        self.cancel_state = False
        self.bar = ttk.Progressbar(actions, variable=self.progress_value, maximum=100, length=200)
        self.bar.pack(side="left", padx=10)
        drop = tk.Frame(pad, bg=BG, highlightthickness=1, highlightbackground=SHADOW_DARK, bd=0)
        drop.pack(fill="x", pady=(10, 6))
        dtitle = tk.Label(drop, text="Extract audio from video file", bg=BG, fg=FG, font=("Helvetica", 12, "bold"))
        dtitle.pack(anchor="w", padx=12, pady=(10, 4))
        self.drop_zone = tk.Label(drop, text="Drag and drop a video here\n(or click to select)", bg=BG_DARK, fg=MUTED, relief="flat", borderwidth=0, width=46, height=5, cursor="hand2", font=("Helvetica", 11))
        self.drop_zone.pack(fill="x", padx=12, pady=(0, 10))
        fmt_row = ttk.Frame(drop)
        fmt_row.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Label(fmt_row, text="Output format").pack(side="left")
        ttk.Radiobutton(fmt_row, text="MP3", variable=self.extract_format, value="mp3").pack(side="left", padx=10)
        ttk.Radiobutton(fmt_row, text="M4A", variable=self.extract_format, value="m4a").pack(side="left")
        NeuButton(fmt_row, text="Select and extract", command=self.select_and_extract, width=150, height=34).pack(side="right")
        if DND_FILES_AVAILABLE:
            self.drop_zone.drop_target_register(DND_FILES)
            self.drop_zone.dnd_bind("<<Drop>>", self.on_drop)
        self.drop_zone.bind("<Button-1>", lambda e: self.select_and_extract())
        status_wrap = tk.Frame(pad, bg=BG)
        status_wrap.pack(fill="x")
        ttk.Label(status_wrap, textvariable=self.status, wraplength=520).pack(fill="x")
        badge = tk.Label(self, text='#ckpt-yt-dlp-"clean-accent-ui" v0.1.7', bg=ACCENT, fg="#1A0F02", font=("Courier", 11), cursor="hand2", padx=10, pady=6)
        badge.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)
        badge.bind("<Button-1>", lambda e: messagebox.showinfo("Changes", "v0.1.5: neumorphic GUI styling."))

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
        ttk.Label(self.quality_inner, text=title[:70] if title else "Available options").pack(anchor="w", pady=(0, 4))
        if heights:
            ttk.Radiobutton(self.quality_inner, text="Best (highest available)", variable=self.choice, value="v:best").pack(anchor="w", padx=8)
            for h in heights:
                label = LABELS.get(h, f"{h}")
                ttk.Radiobutton(self.quality_inner, text=f"{label} video + audio", variable=self.choice, value=f"v:{h}").pack(anchor="w", padx=8)
        ttk.Separator(self.quality_inner, orient="horizontal").pack(fill="x", padx=8, pady=6)
        ttk.Radiobutton(self.quality_inner, text="Audio only: M4A", variable=self.choice, value="a:m4a").pack(anchor="w", padx=8)
        ttk.Radiobutton(self.quality_inner, text="Audio only: MP3", variable=self.choice, value="a:mp3").pack(anchor="w", padx=8)
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
        self.bar["value"] = 0
        self.status.set("Starting download...")
        self.cancel.set_enabled(True)
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
            self.cancel.set_enabled(False)

    def paste_url(self):
        try:
            self.url.set(self.clipboard_get().strip())
            self.status.set("Pasted from clipboard; fetching...")
            self.fetch()
        except tk.TclError:
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
        self.cancel.set_enabled(False)
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
                    self.status.set(text[:150])
                elif kind == "formats":
                    self.render_quality(item[1], item[2])
                elif kind == "done":
                    self.progress_value.set(100)
                    self.status.set(item[1])
                    self.cancel.set_enabled(False)
                elif kind == "error":
                    self.status.set(item[1])
                    self.cancel.set_enabled(False)
        except queue.Empty:
            pass
        self.after(80, self.poll_log)


if __name__ == "__main__":
    App().mainloop()
