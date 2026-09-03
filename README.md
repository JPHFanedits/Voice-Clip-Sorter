<div align="center">

<img src="./Voice%20Clip%20Sorter%20Icon.png" alt="Voice Clip Sorter icon" width="140">

# Voice Clip Sorter

**A fast, focused Windows app for reviewing and organizing voice-clip takes.**

[![Version](https://img.shields.io/badge/version-1.0.0-6F9ED6)](#)
[![Platform](https://img.shields.io/badge/platform-Windows-65C746)](#)
[![Audio](https://img.shields.io/badge/audio-WAV%20%7C%20MP3%20%7C%20OGG-9FB0C2)](#)

</div>

Voice Clip Sorter lets you listen through a folder of voice clips in filename order and quickly move each take into **Keep** or **Rejected**. Files are moved rather than deleted, so rejected takes remain available if you need them later.

## Features

- Review WAV, MP3, and OGG clips.
- Begin from any clip using a standard file picker.
- Process files in natural filename order (`take2` before `take10`).
- Move accepted clips into a neighboring `Keep` folder.
- Move rejected clips into a neighboring `Rejected` folder.
- Automatically advance after every Keep or Reject decision.
- Revisit previous clips, including clips that have already been moved.
- See live Unsorted, Rejected, and Kept totals.
- Identify clip status at a glance with consistent status colors.
- Enable optional autoplay for every clip change.
- Adjust playback volume.
- Resume the most recent sorting session.
- Remember autoplay and volume preferences between runs.
- Avoid overwrites by assigning a numbered filename when necessary.
- Use a standalone Windows executable—Python is not required for normal use.

Clip-status colors are:

- ⚪ **White** — Unsorted
- 🔴 **Red** — Rejected
- 🟢 **Green** — Kept

## Download and run

1. Download `Voice Clip Sorter v1.0.0.exe` from the repository's [Releases](../../releases) page.
2. Run the executable.
3. Select **Choose Starting Clip** and choose the first clip you want to review.

The app scans supported audio files directly inside the selected clip's folder. It does **not** scan subfolders.

> [!NOTE]
> The executable is not code-signed. Windows SmartScreen may display a warning the first time it is opened.

## Using the app

After selecting a starting clip, use the transport controls to listen and navigate:

| Control | Action |
|---|---|
| ⏪ | Play or select the previous clip |
| ▶ / ⏸ | Play or pause the current clip |
| ⏩ | Play or select the next clip |
| **Keep** | Move the current clip into `Keep`, then advance |
| **Reject** | Move the current clip into `Rejected`, then advance |

When autoplay is disabled, changing clips leaves playback stopped until you press Play. When autoplay is enabled, selecting, resuming, navigating to, or advancing to a clip starts it automatically. Playback stops at the end of the clip.

## Keyboard shortcuts

| Key | Action |
|---|---|
| `K` | Keep the current clip |
| `R` | Reject the current clip |
| `Left Arrow` | Previous clip |
| `Right Arrow` | Next clip |
| `Space` | Play or pause |

## Folder behavior

If the selected clip is located in:

```text
My Voice Clips/
├── line_001_take_01.wav
├── line_001_take_02.wav
└── line_001_take_03.wav
```

Voice Clip Sorter creates the destination folders beside the original clips:

```text
My Voice Clips/
├── Keep/
│   └── line_001_take_02.wav
├── Rejected/
│   └── line_001_take_01.wav
└── line_001_take_03.wav
```

No clip is permanently deleted. If a file with the same name already exists in the destination, the incoming clip is renamed—for example, `line_001_take_01 (2).wav`—instead of overwriting the existing file.

## Saved data

The app stores session and preference data locally at:

```text
%LOCALAPPDATA%\VoiceClipSorter\
```

This data includes:

- The current session queue and position
- Autoplay preference
- Volume preference

Audio files are never copied into the settings folder.

## Development

### Requirements

- Windows 10 or later
- Python 3.11+
- [pygame](https://www.pygame.org/) 2.5+
- [PyInstaller](https://pyinstaller.org/) 6+
- Pillow, if regenerating `.ico` assets

Install the development dependencies:

```powershell
py -m pip install pygame pyinstaller pillow
```

Run from source:

```powershell
py voice_clip_sorter.py
```

Run the tests:

```powershell
py -m unittest -v test_voice_clip_sorter.py
```

### Build the standalone executable

From the source directory, run:

```powershell
py -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name "Voice Clip Sorter v1.0.0" `
  --icon "assets\voice_clip_sorter.ico" `
  --version-file "version_info.txt" `
  --add-data "assets;assets" `
  voice_clip_sorter.py
```

The packaged executable is written to `dist\Voice Clip Sorter v1.0.0.exe`.

## Project structure

```text
.
├── assets/
│   ├── voice_clip_sorter.ico
│   ├── voice_clip_sorter.png
│   └── voice_clip_sorter_256.png
├── voice_clip_sorter.py
├── test_voice_clip_sorter.py
├── version_info.txt
└── README.md
```

## Contributing

Bug reports and focused pull requests are welcome. When reporting playback issues, include the audio format, Windows version, and whether the problem occurs in the packaged app or when running from source.
