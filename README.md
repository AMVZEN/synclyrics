# 🎶 SyncLyrics

**SyncLyrics** is a premium, terminal-inspired desktop lyrics player for Linux. It provides a high-fidelity, synchronized karaoke experience with a built-in fluid audio visualizer and a sleek, translucent design.

![SyncLyrics Screenshot]([https://github.com/AMVZEN/synclyrics/raw/main/icon.png](https://github.com/AMVZEN/synclyrics/blob/main/Example.png))

## ✨ Features

- **Fluid Audio Visualizer**: Real-time audio analysis with smooth wave animations.
- **Ui Mode Cycle**: Toggle between multiple UI states (All Info → Lyrics+Vis → Lyrics only).
- **Mpris Integration**: Automatically detects and follows playback from Spotify, VLC, MPD, and more.
- **Nerd Font Support**: Utilizes premium iconography for a modern developer aesthetic.

## 🚀 Installation

### Arch Linux (AUR)
The easiest way to install SyncLyrics on Arch is via the AUR:

```bash
yay -S synclyrics
```

### Manual Installation (Local Build)
Compile and run SyncLyrics from source:

1. **Clone the repository**:
   ```bash
   git clone https://github.com/AMVZEN/synclyrics.git
   cd synclyrics
   ```

2. **Install dependencies**:
   Ensure you have `python`, `python-pyqt6`, `numpy`, and `pyaudio` installed.
   ```bash
   pip install .
   ```

3. **Run**:
   ```bash
   synclyrics
   ```

## 🛠 Usage

- **Ui Toggle (󰒲)**: Click the moon icon to cycle through UI visibility modes.
- **Sync Button (󰑐)**: Manually force a lyric refresh/sync with the current player.
- **Offset Controls (±)**: Adjust lyric timing on the fly if the sync is slightly off.

## 📦 Requirements

- **Python 3.10+**
- **Nerd Fonts**: (Recommended: JetBrainsMono NF) for correct icon rendering.
- **System tools**: `playerctl` and PulseAudio/PipeWire for the visualizer.

---
Created with ❤️ by [AMVZEN](https://github.com/AMVZEN)
