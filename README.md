# 🎶 SyncLyrics

**SyncLyrics** is a premium, developer-centric desktop lyrics player for Linux. It provides a high-fidelity, synchronized karaoke experience with professional-grade audio visualizers and a sleek design.

<img width="1879" height="989" alt="Example" src="https://github.com/user-attachments/assets/995e21f2-778c-48a7-b95f-d7e6521b2033" />

## ✨ Features

- **MilkDrop Visualizer**: Integrated Butterchurn WebGL visualizer with thousands of dynamic presets.
- **Multi-Source Support**: Fetches from LRCLib, NetEase, and OvH with the ability to cycle through providers and translations.
- **Smart Romanization**: Automatic script detection for **Japanese (Hepburn)** and **Chinese (Pinyin)**.
- **Hi-Fi Aesthetics**: Translucent layouts, smooth animations, and dynamic blur that adapts to the UI state.
- **MPRIS Integration**: Follows Spotify, VLC, MPD, Audacious, and any other player speaking MPRIS.
- **Persistent Settings**: Remembers your theme, position, default offset, and preferred visualizers.

## 🚀 Installation

### Arch Linux (AUR)
The easiest way on Arch is via the AUR:

```bash
yay -S synclyrics
```

### Manual Installation (Local Build)

1. **Clone and Install**:
   ```bash
   git clone https://github.com/AMVZEN/synclyrics.git
   cd synclyrics
   pip install -e ".[all]"
   ```

2. **System Requirements**: 
   Ensure you have `playerctl` and `libpulse` installed for audio capture.

## ⌨️ Usage & Hotkeys

- **`Space`**: Play/Pause.
- **`Esc`**: Toggle UI Modes (All Info → Lyrics+Vis → Visualizer Only → Lyrics Only).
- **`N`**: Cycle through available lyric sources/versions (Bottom-Left button).
- **`R`**: Force resync/refresh lyrics.
- **`Ctrl + S`**: Open Settings.

## 🛠 Configuration

Manage theme colors, vignette intensity, dream-glow effects, and default synchronization offsets directly from the built-in Settings dialog.

---
Created with ❤️ by [AMVZEN](https://github.com/AMVZEN)
