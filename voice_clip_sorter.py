from __future__ import annotations

import json
import os
import re
import shutil
import ctypes
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame


APP_NAME = "Voice Clip Sorter"
APP_VERSION = "1.0.0"
APP_BACKGROUND = "#101B2B"
APP_SURFACE = "#1A2C43"
APP_SURFACE_HOVER = "#274563"
APP_BLUE = "#6F9ED6"
APP_GREEN = "#65C746"
APP_TEXT = "#EEF4FA"
APP_MUTED = "#9FB0C2"
APP_RED = "#E96872"
WINDOWS_APP_ID = f"VoiceClipSorter.App.{APP_VERSION}"
SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".ogg"}
STATE_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "VoiceClipSorter"
STATE_FILE = STATE_DIR / "session.json"
PREFERENCES_FILE = STATE_DIR / "preferences.json"


def discover_clips(folder: Path) -> list[Path]:
    """Return supported audio files directly inside folder, in filename order."""
    return sorted(
        (
            path.resolve()
            for path in folder.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ),
        key=lambda path: filename_sort_key(path.name),
    )


def filename_sort_key(filename: str) -> tuple:
    """Match the natural numbered ordering people expect in Windows Explorer."""
    return tuple(
        int(part) if part.isdigit() else part.casefold()
        for part in re.split(r"(\d+)", filename)
    )


def available_destination(folder: Path, filename: str) -> Path:
    """Choose a destination without overwriting an existing file."""
    candidate = folder / filename
    if not candidate.exists():
        return candidate

    source_name = Path(filename)
    number = 2
    while True:
        candidate = folder / f"{source_name.stem} ({number}){source_name.suffix}"
        if not candidate.exists():
            return candidate
        number += 1


def format_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def classification_counts(clips: list[Path], source_dir: Path | None) -> dict[str, int]:
    counts = {"unsorted": 0, "rejected": 0, "keep": 0}
    if source_dir is None:
        return counts
    source_dir = source_dir.resolve()
    for clip in clips:
        if clip.parent.resolve() == source_dir:
            counts["unsorted"] += 1
        elif clip.parent.name.casefold() == "rejected":
            counts["rejected"] += 1
        elif clip.parent.name.casefold() == "keep":
            counts["keep"] += 1
        else:
            counts["unsorted"] += 1
    return counts


def load_preferences(path: Path = PREFERENCES_FILE) -> dict[str, bool | float]:
    defaults: dict[str, bool | float] = {"autoplay": False, "volume": 1.0}
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
        defaults["autoplay"] = bool(saved.get("autoplay", False))
        defaults["volume"] = max(0.0, min(1.0, float(saved.get("volume", 1.0))))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    return defaults


def resource_path(relative_path: str) -> Path:
    """Resolve an asset both in source and in a bundled PyInstaller app."""
    return Path(__file__).resolve().parent / relative_path


class VoiceClipSorter(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("780x520")
        self.minsize(700, 520)
        self.configure(bg=APP_BACKGROUND)
        try:
            app_icon = str(resource_path("assets/voice_clip_sorter.ico"))
            self.iconbitmap(app_icon)
            self.iconbitmap(default=app_icon)
            self._window_icon = tk.PhotoImage(file=str(resource_path("assets/voice_clip_sorter_256.png")))
            self.iconphoto(True, self._window_icon)
        except (OSError, tk.TclError):
            pass

        self.source_dir: Path | None = None
        self.clips: list[Path] = []
        self.index = 0
        self.duration = 0.0
        self.paused = False
        self.audio_ready = False
        self.completed = False
        preferences = load_preferences()
        self.autoplay_var = tk.BooleanVar(value=bool(preferences["autoplay"]))
        self.volume_var = tk.DoubleVar(value=float(preferences["volume"]) * 100)
        self.volume_text_var = tk.StringVar(value=f"{round(self.volume_var.get())}%")

        self._configure_style()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Left>", lambda _event: self.previous_clip())
        self.bind("<Right>", lambda _event: self.next_clip())
        self.bind("<space>", lambda _event: self.toggle_pause())
        self.bind("k", lambda _event: self.keep_clip())
        self.bind("r", lambda _event: self.reject_clip())
        self.bind("K", lambda _event: self.keep_clip())
        self.bind("R", lambda _event: self.reject_clip())
        self.after(150, self._update_progress)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("App.TFrame", background=APP_BACKGROUND)
        style.configure(
            "Title.TLabel", background=APP_BACKGROUND, foreground=APP_TEXT, font=("Segoe UI", 21, "bold")
        )
        style.configure(
            "Version.TLabel", background=APP_SURFACE, foreground=APP_BLUE, font=("Segoe UI", 9, "bold"), padding=(8, 3)
        )
        style.configure(
            "Clip.TLabel", background=APP_BACKGROUND, foreground=APP_TEXT, font=("Segoe UI", 15, "bold")
        )
        style.configure(
            "Keep.Clip.TLabel", background=APP_BACKGROUND, foreground=APP_GREEN, font=("Segoe UI", 15, "bold")
        )
        style.configure(
            "Rejected.Clip.TLabel", background=APP_BACKGROUND, foreground=APP_RED, font=("Segoe UI", 15, "bold")
        )
        style.configure(
            "Info.TLabel", background=APP_BACKGROUND, foreground=APP_MUTED, font=("Segoe UI", 10)
        )
        style.configure(
            "Unsorted.Count.TLabel", background=APP_BACKGROUND, foreground=APP_TEXT, font=("Segoe UI", 10, "bold")
        )
        style.configure(
            "Rejected.Count.TLabel", background=APP_BACKGROUND, foreground=APP_RED, font=("Segoe UI", 10, "bold")
        )
        style.configure(
            "Keep.Count.TLabel", background=APP_BACKGROUND, foreground=APP_GREEN, font=("Segoe UI", 10, "bold")
        )
        style.configure(
            "Keep.Action.TButton", font=("Segoe UI", 12, "bold"), padding=(18, 12),
            background="#274D3B", foreground="#CFF4D0", bordercolor="#376B50"
        )
        style.map("Keep.Action.TButton", background=[("active", "#32654A")])
        style.configure(
            "Reject.Action.TButton", font=("Segoe UI", 12, "bold"), padding=(18, 12),
            background="#4B303B", foreground="#FFD8DC", bordercolor="#70414D"
        )
        style.map("Reject.Action.TButton", background=[("active", "#653B47")])
        style.configure(
            "Nav.TButton", font=("Segoe UI", 10), padding=(14, 9), background=APP_SURFACE,
            foreground=APP_TEXT, bordercolor="#304B67"
        )
        style.map("Nav.TButton", background=[("active", APP_SURFACE_HOVER)])
        style.configure(
            "App.TCheckbutton", background=APP_BACKGROUND, foreground=APP_TEXT, font=("Segoe UI", 10)
        )
        style.map("App.TCheckbutton", background=[("active", APP_BACKGROUND)], foreground=[("active", APP_TEXT)])
        style.configure(
            "Horizontal.TProgressbar", background=APP_GREEN, troughcolor=APP_SURFACE, bordercolor=APP_SURFACE
        )

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, style="App.TFrame", padding=(28, 22))
        outer.pack(fill="both", expand=True)

        title_row = ttk.Frame(outer, style="App.TFrame")
        title_row.pack(fill="x")
        ttk.Label(title_row, text=APP_NAME, style="Title.TLabel").pack(side="left")
        ttk.Label(title_row, text=f"v{APP_VERSION}", style="Version.TLabel").pack(side="left", padx=(12, 0), pady=(6, 0))

        session_controls = ttk.Frame(outer, style="App.TFrame")
        session_controls.pack(fill="x", pady=(9, 11))
        self.resume_button = ttk.Button(
            session_controls, text="Resume Last Session", command=self.resume_session, style="Nav.TButton"
        )
        self.resume_button.pack(side="right")
        ttk.Button(
            session_controls, text="Choose Starting Clip…", command=self.choose_clip, style="Nav.TButton"
        ).pack(side="right", padx=(0, 8))
        try:
            session_available = STATE_FILE.is_file()
        except OSError:
            session_available = False
        if not session_available:
            self.resume_button.configure(state="disabled")

        self.folder_var = tk.StringVar(value="Choose a starting clip to begin")
        ttk.Label(outer, textvariable=self.folder_var, style="Info.TLabel", wraplength=750).pack(
            anchor="w", pady=(0, 16)
        )

        self.clip_var = tk.StringVar(value="No clip selected")
        self.clip_label = ttk.Label(outer, textvariable=self.clip_var, style="Clip.TLabel", wraplength=750)
        self.clip_label.pack(anchor="w")

        self.counter_var = tk.StringVar(value="")
        ttk.Label(outer, textvariable=self.counter_var, style="Info.TLabel").pack(anchor="w", pady=(5, 16))

        counts = ttk.Frame(outer, style="App.TFrame")
        counts.pack(anchor="e", pady=(0, 8))
        self.unsorted_count_var = tk.StringVar(value="Unsorted  0")
        self.rejected_count_var = tk.StringVar(value="Rejected  0")
        self.keep_count_var = tk.StringVar(value="Kept  0")
        ttk.Label(counts, textvariable=self.unsorted_count_var, style="Unsorted.Count.TLabel").pack(
            side="left", padx=(0, 18)
        )
        ttk.Label(counts, textvariable=self.rejected_count_var, style="Rejected.Count.TLabel").pack(
            side="left", padx=(0, 18)
        )
        ttk.Label(counts, textvariable=self.keep_count_var, style="Keep.Count.TLabel").pack(side="left")

        self.progress = ttk.Progressbar(outer, mode="determinate", maximum=100)
        self.progress.pack(fill="x")
        self.time_var = tk.StringVar(value="0:00 / 0:00")
        ttk.Label(outer, textvariable=self.time_var, style="Info.TLabel").pack(anchor="e", pady=(5, 12))

        playback_options = ttk.Frame(outer, style="App.TFrame")
        playback_options.pack(fill="x", pady=(0, 15))
        ttk.Checkbutton(
            playback_options,
            text="Autoplay clips",
            variable=self.autoplay_var,
            command=self._save_preferences,
            style="App.TCheckbutton",
        ).pack(side="left")
        ttk.Label(playback_options, text="Volume", style="Info.TLabel").pack(side="left", padx=(28, 8))
        ttk.Scale(
            playback_options,
            from_=0,
            to=100,
            variable=self.volume_var,
            command=self._volume_changed,
            length=220,
        ).pack(side="left", fill="x", expand=True)
        ttk.Label(playback_options, textvariable=self.volume_text_var, style="Info.TLabel", width=5).pack(
            side="left", padx=(8, 0)
        )

        decisions = ttk.Frame(outer, style="App.TFrame")
        decisions.pack(fill="x", pady=(0, 18))
        self.keep_button = ttk.Button(
            decisions, text="Keep  (K)", command=self.keep_clip, style="Keep.Action.TButton", state="disabled"
        )
        self.keep_button.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.reject_button = ttk.Button(
            decisions, text="Reject  (R)", command=self.reject_clip, style="Reject.Action.TButton", state="disabled"
        )
        self.reject_button.pack(side="left", fill="x", expand=True, padx=(10, 0))

        navigation = ttk.Frame(outer, style="App.TFrame")
        navigation.pack()
        self.previous_button = self._transport_button(navigation, "⏪", self.previous_clip)
        self.previous_button.pack(side="left", padx=11)
        self.play_pause_button = self._transport_button(navigation, "▶", self.toggle_pause, accent=True)
        self.play_pause_button.pack(side="left", padx=11)
        self.next_button = self._transport_button(navigation, "⏩", self.next_clip)
        self.next_button.pack(side="left", padx=11)

    def _transport_button(
        self, parent: tk.Widget, symbol: str, command, *, accent: bool = False
    ) -> tk.Button:
        background = "#3F863B" if accent else APP_SURFACE
        active_background = APP_GREEN if accent else APP_SURFACE_HOVER
        return tk.Button(
            parent,
            text=symbol,
            command=command,
            state="disabled",
            font=("Segoe UI Symbol", 20, "bold"),
            width=4,
            height=1,
            relief="flat",
            borderwidth=0,
            background=background,
            foreground=APP_TEXT,
            activebackground=active_background,
            activeforeground="#ffffff",
            disabledforeground="#5D7084",
            cursor="hand2",
            takefocus=True,
        )

    def _ensure_audio(self) -> bool:
        if self.audio_ready:
            return True
        try:
            pygame.mixer.init()
            pygame.mixer.music.set_volume(self.volume_var.get() / 100.0)
            self.audio_ready = True
            return True
        except pygame.error as exc:
            messagebox.showerror(APP_NAME, f"Audio playback could not be started.\n\n{exc}")
            return False

    def choose_clip(self) -> None:
        chosen = filedialog.askopenfilename(
            title="Choose the first voice clip",
            filetypes=[
                ("Voice clips", "*.wav *.mp3 *.ogg"),
                ("WAV files", "*.wav"),
                ("MP3 files", "*.mp3"),
                ("OGG files", "*.ogg"),
            ],
        )
        if not chosen:
            return

        selected = Path(chosen).resolve()
        clips = discover_clips(selected.parent)
        try:
            start_index = clips.index(selected)
        except ValueError:
            messagebox.showerror(APP_NAME, "The selected file is not a supported WAV, MP3, or OGG clip.")
            return

        self._stop_audio()
        self.source_dir = selected.parent
        (self.source_dir / "Keep").mkdir(exist_ok=True)
        (self.source_dir / "Rejected").mkdir(exist_ok=True)
        self.clips = clips
        self.index = start_index
        self.completed = False
        self._save_state()
        self._show_current()

    def resume_session(self) -> None:
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            source_dir = Path(data["source_dir"])
            saved_clips = [Path(value) for value in data["clips"]]
            old_index = int(data.get("index", 0))
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            messagebox.showerror(APP_NAME, "The saved session could not be read.")
            return

        if not source_dir.is_dir():
            messagebox.showerror(APP_NAME, "The folder from the saved session is no longer available.")
            return

        existing: list[Path] = []
        adjusted_index = 0
        for position, path in enumerate(saved_clips):
            if path.is_file():
                if position < old_index:
                    adjusted_index += 1
                existing.append(path.resolve())
        if not existing:
            messagebox.showerror(APP_NAME, "None of the clips from the saved session could be found.")
            return

        self._stop_audio()
        self.source_dir = source_dir.resolve()
        self.clips = existing
        self.index = min(adjusted_index, len(existing) - 1)
        self.completed = bool(data.get("completed", False))
        self._show_current()

    def _show_current(self) -> None:
        if not self.clips or self.source_dir is None:
            return
        self.index = max(0, min(self.index, len(self.clips) - 1))
        current = self.clips[self.index]
        self.folder_var.set(str(self.source_dir))
        self.clip_var.set(current.name)
        location = current.parent.name if current.parent != self.source_dir else "Unsorted"
        self._set_clip_color(location)
        completion = " — end reached" if self.completed and self.index == len(self.clips) - 1 else ""
        self.counter_var.set(f"Clip {self.index + 1} of {len(self.clips)}  •  {location}{completion}")
        self._update_counts()
        self._update_buttons()
        self.progress["value"] = 0
        self.time_var.set("0:00 / 0:00")
        if self.autoplay_var.get() and not self.completed:
            self._start_current()

    def play_current(self) -> None:
        if self.paused and self.audio_ready:
            pygame.mixer.music.unpause()
            self.paused = False
            self._set_transport_playing(True)
            return
        self._start_current()

    def _start_current(self) -> None:
        if not self.clips or not self._ensure_audio():
            return
        path = self.clips[self.index]
        if not path.is_file():
            messagebox.showwarning(APP_NAME, f"This clip can no longer be found:\n\n{path}")
            return
        try:
            pygame.mixer.music.load(str(path))
            self.duration = float(pygame.mixer.Sound(str(path)).get_length())
            pygame.mixer.music.set_volume(self.volume_var.get() / 100.0)
            pygame.mixer.music.play()
            self.paused = False
            self._set_transport_playing(True)
            self.progress["value"] = 0
            self.time_var.set(f"0:00 / {format_time(self.duration)}")
        except pygame.error as exc:
            messagebox.showerror(APP_NAME, f"This clip could not be played:\n\n{path.name}\n\n{exc}")

    def pause_current(self) -> None:
        if not self.clips or not self.audio_ready or self.paused:
            return
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
            self.paused = True
            self._set_transport_playing(False)

    def toggle_pause(self) -> None:
        if self.paused:
            self.play_current()
        elif self.audio_ready and pygame.mixer.music.get_busy():
            self.pause_current()
        else:
            self.play_current()

    def previous_clip(self) -> None:
        if not self.clips or self.index <= 0:
            return
        self._stop_audio()
        self.index -= 1
        self.completed = False
        self._save_state()
        self._show_current()

    def next_clip(self) -> None:
        if not self.clips or self.index >= len(self.clips) - 1:
            return
        self._stop_audio()
        self.index += 1
        self.completed = False
        self._save_state()
        self._show_current()

    def keep_clip(self) -> None:
        self._classify_current("Keep")

    def reject_clip(self) -> None:
        self._classify_current("Rejected")

    def _classify_current(self, folder_name: str) -> None:
        if not self.clips or self.source_dir is None:
            return
        source = self.clips[self.index]
        if not source.exists():
            messagebox.showwarning(APP_NAME, f"This clip can no longer be found:\n\n{source}")
            return

        destination_folder = self.source_dir / folder_name
        destination_folder.mkdir(exist_ok=True)
        self._stop_audio()
        try:
            if source.parent.resolve() == destination_folder.resolve():
                destination = source
            else:
                destination = available_destination(destination_folder, source.name)
                shutil.move(str(source), str(destination))
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"The clip could not be moved.\n\n{exc}")
            if self.autoplay_var.get():
                self.play_current()
            return

        self.clips[self.index] = destination.resolve()
        if self.index < len(self.clips) - 1:
            self.index += 1
            self.completed = False
            self._save_state()
            self._show_current()
        else:
            self.completed = True
            self._save_state()
            self._show_current_without_playing()
            messagebox.showinfo(APP_NAME, "You have reached the end of this set of clips.")

    def _show_current_without_playing(self) -> None:
        current = self.clips[self.index]
        self.clip_var.set(current.name)
        location = current.parent.name if self.source_dir and current.parent != self.source_dir else "Unsorted"
        self._set_clip_color(location)
        self.counter_var.set(f"Clip {self.index + 1} of {len(self.clips)}  •  {location} — end reached")
        self._update_counts()
        self.progress["value"] = 0
        self.time_var.set("0:00 / 0:00")
        self._update_buttons()

    def _update_buttons(self) -> None:
        active = bool(self.clips)
        standard_state = "normal" if active else "disabled"
        self.keep_button.configure(state=standard_state)
        self.reject_button.configure(state=standard_state)
        self.play_pause_button.configure(state=standard_state)
        self.previous_button.configure(state="normal" if active and self.index > 0 else "disabled")
        self.next_button.configure(
            state="normal" if active and self.index < len(self.clips) - 1 else "disabled"
        )

    def _update_progress(self) -> None:
        if self.audio_ready and self.duration > 0:
            milliseconds = pygame.mixer.music.get_pos()
            if milliseconds >= 0:
                elapsed = min(milliseconds / 1000.0, self.duration)
                self.progress["value"] = elapsed / self.duration * 100
                self.time_var.set(f"{format_time(elapsed)} / {format_time(self.duration)}")
            if not self.paused and not pygame.mixer.music.get_busy():
                self._set_transport_playing(False)
        self.after(150, self._update_progress)

    def _stop_audio(self) -> None:
        if self.audio_ready:
            pygame.mixer.music.stop()
            try:
                pygame.mixer.music.unload()
            except pygame.error:
                pass
        self.paused = False
        self.duration = 0.0
        self._set_transport_playing(False)

    def _set_transport_playing(self, playing: bool) -> None:
        if hasattr(self, "play_pause_button"):
            self.play_pause_button.configure(text="⏸" if playing else "▶")

    def _set_clip_color(self, location: str) -> None:
        if location.casefold() == "keep":
            self.clip_label.configure(style="Keep.Clip.TLabel")
        elif location.casefold() == "rejected":
            self.clip_label.configure(style="Rejected.Clip.TLabel")
        else:
            self.clip_label.configure(style="Clip.TLabel")

    def _update_counts(self) -> None:
        counts = classification_counts(self.clips, self.source_dir)
        self.unsorted_count_var.set(f"Unsorted  {counts['unsorted']}")
        self.rejected_count_var.set(f"Rejected  {counts['rejected']}")
        self.keep_count_var.set(f"Kept  {counts['keep']}")

    def _volume_changed(self, value: str) -> None:
        volume = max(0.0, min(100.0, float(value)))
        self.volume_text_var.set(f"{round(volume)}%")
        if self.audio_ready:
            pygame.mixer.music.set_volume(volume / 100.0)
        self._save_preferences()

    def _save_preferences(self) -> None:
        data = {
            "autoplay": bool(self.autoplay_var.get()),
            "volume": max(0.0, min(1.0, self.volume_var.get() / 100.0)),
        }
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            temporary = PREFERENCES_FILE.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
            temporary.replace(PREFERENCES_FILE)
        except OSError:
            pass

    def _save_state(self) -> None:
        if self.source_dir is None or not self.clips:
            return
        data = {
            "source_dir": str(self.source_dir),
            "clips": [str(path) for path in self.clips],
            "index": self.index,
            "completed": self.completed,
        }
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            temporary = STATE_FILE.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
            temporary.replace(STATE_FILE)
            self.resume_button.configure(state="normal")
        except OSError:
            # Sorting remains usable even when Windows blocks session persistence.
            pass

    def _on_close(self) -> None:
        self._save_preferences()
        self._save_state()
        self._stop_audio()
        if self.audio_ready:
            pygame.mixer.quit()
        self.destroy()


if __name__ == "__main__":
    if os.name == "nt":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WINDOWS_APP_ID)
        except (AttributeError, OSError):
            pass
    app = VoiceClipSorter()
    app.mainloop()
