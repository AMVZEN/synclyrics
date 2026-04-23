import requests
import threading
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSlider, QFrame
from PyQt6.QtGui import QColor, QFont, QPixmap, QImage, QPainter, QPainterPath
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, pyqtProperty, QByteArray
import subprocess
import os
import urllib.parse

# Font fallback chain — use full names that Qt actually resolves
_FONT_FAMILY = "'JetBrainsMono Nerd Font', 'JetBrainsMono NF', 'Fira Code', 'Cascadia Code', monospace"

class TrackInfoWidget(QWidget):
    sync_requested = pyqtSignal()
    offset_changed = pyqtSignal(float)
    _art_loaded = pyqtSignal(QByteArray)  # raw image bytes, marshalled to main thread
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(0)
        self._opacity = 1.0
        self._last_sec = -1
        self._setup_ui()
        self.track_length = 0.0
        self.current_offset = 0.0
        self.is_scrubbing = False
        self._art_loaded.connect(self._on_art_bytes_received)

    @pyqtProperty(float)
    def opacity(self): return self._opacity
    @opacity.setter
    def opacity(self, v):
        self._opacity = v
        self.update()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 10, 15, 10)
        
        self.frame = QFrame()
        self.frame.setStyleSheet("background-color: transparent;")
        frame_layout = QHBoxLayout(self.frame)
        frame_layout.setContentsMargins(5, 5, 5, 5)
        frame_layout.setSpacing(18)
        
        self.art_label = QLabel()
        self.art_label.setFixedSize(64, 64)
        self.art_label.setStyleSheet("background-color: rgba(255,255,255,0.03); border-radius: 8px;")
        frame_layout.addWidget(self.art_label)
        
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        self.title_label = QLabel("No track playing")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        info_layout.addWidget(self.title_label)
        
        self.artist_label = QLabel("Waiting for MPRIS sync...")
        self.artist_label.setStyleSheet("font-size: 14px; opacity: 0.7;")
        info_layout.addWidget(self.artist_label)
        
        frame_layout.addLayout(info_layout)
        frame_layout.addStretch()
        
        self.play_pause_btn = QPushButton("󰐊") 
        self.play_pause_btn.setFixedSize(48, 48)
        self.play_pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_pause_btn.clicked.connect(self._toggle_playback)
        frame_layout.addWidget(self.play_pause_btn)
        
        self.controls_layout = QHBoxLayout()
        self.controls_layout.setSpacing(10)
        
        self.btn_sync = QPushButton("󰑐")
        self.btn_sync.setFixedSize(32, 48)
        self.btn_sync.clicked.connect(self.sync_requested.emit)
        
        self.btn_offset_minus = QPushButton("-")
        self.btn_offset_minus.setFixedSize(24, 48)
        self.btn_offset_minus.clicked.connect(lambda: self._adjust_offset(-0.5))
        
        self.offset_label = QLabel("±0.0s")
        self.offset_label.setFixedWidth(50)
        self.offset_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.btn_offset_plus = QPushButton("+")
        self.btn_offset_plus.setFixedSize(24, 48)
        self.btn_offset_plus.clicked.connect(lambda: self._adjust_offset(0.5))
        
        self.controls_layout.addWidget(self.btn_sync)
        self.controls_layout.addWidget(self.btn_offset_minus)
        self.controls_layout.addWidget(self.offset_label)
        self.controls_layout.addWidget(self.btn_offset_plus)
        frame_layout.addLayout(self.controls_layout)
        
        main_layout.addWidget(self.frame)
        
        prog_layout = QHBoxLayout()
        prog_layout.setContentsMargins(5, 10, 5, 0)
        
        self.time_lbl_curr = QLabel("0:00")
        prog_layout.addWidget(self.time_lbl_curr)
        
        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, 1000)
        self.progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self.progress_slider.sliderReleased.connect(self._on_slider_released)
        prog_layout.addWidget(self.progress_slider)
        
        self.time_lbl_total = QLabel("0:00")
        prog_layout.addWidget(self.time_lbl_total)
        
        main_layout.addLayout(prog_layout)

    def update_track(self, info: dict):
        if not info:
            self.title_label.setText("No track playing")
            self.artist_label.setText("Waiting for MPRIS sync...")
            self.progress_slider.setValue(0)
            self.time_lbl_curr.setText("0:00")
            self.time_lbl_total.setText("0:00")
            self.track_length = 0.0
            self.art_label.clear()
            return
            
        title = info.get("title", "")
        self.title_label.setText(title if len(title) < 40 else title[:37] + "...")
        self.artist_label.setText(info.get("artist", "Unknown Artist"))
        
        self.track_length = float(info.get("length", 0.0))
        if self.track_length > 0:
            m, s = divmod(int(self.track_length), 60)
            self.time_lbl_total.setText(f"{m}:{s:02d}")
            
        art_url = info.get("artUrl", "")
        if art_url:
            threading.Thread(target=self._load_art_async, args=(art_url,), daemon=True).start()
            
    def update_position(self, pos: float):
        if self.track_length > 0 and not self.is_scrubbing:
            curr_sec = int(pos)
            if curr_sec != self._last_sec:
                m, s = divmod(curr_sec, 60)
                self.time_lbl_curr.setText(f"{m}:{s:02d}")
                self._last_sec = curr_sec
                
            ratio = min(1.0, max(0.0, pos / self.track_length))
            self.progress_slider.blockSignals(True)
            self.progress_slider.setValue(int(ratio * 1000))
            self.progress_slider.blockSignals(False)

    def set_state(self, state: str):
        self.play_pause_btn.setText("󰏤" if state == "Playing" else "󰐊")

    def _load_art_async(self, url: str):
        """Runs in a background thread — loads raw bytes then signals the main thread."""
        try:
            raw_bytes = None
            if url.startswith("file://"):
                path = urllib.parse.unquote(url[7:])
                if os.path.exists(path):
                    with open(path, "rb") as f:
                        raw_bytes = f.read()
                # Some players local paths are just paths
            elif url.startswith("/"):
                if os.path.exists(url):
                    with open(url, "rb") as f:
                        raw_bytes = f.read()
            elif url.startswith("http"):
                r = requests.get(url, timeout=3)
                if r.status_code == 200:
                    raw_bytes = r.content
            else:
                # Last resort: try as relative or full path
                if os.path.exists(url):
                    with open(url, "rb") as f:
                        raw_bytes = f.read()

            if raw_bytes:
                # Signal the main thread with the raw bytes (thread-safe)
                self._art_loaded.emit(QByteArray(raw_bytes))
            else:
                # Clear art if load failed
                self._art_loaded.emit(QByteArray())
        except Exception:
            self._art_loaded.emit(QByteArray())

    def _on_art_bytes_received(self, data: QByteArray):
        """Runs on main thread — safe to create QImage/QPixmap here."""
        img = QImage()
        img.loadFromData(data)
        if not img.isNull():
            self._set_pixmap(QPixmap.fromImage(img))

    def _set_pixmap(self, p: QPixmap):
        scaled = p.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        res = QPixmap(64,64)
        res.fill(Qt.GlobalColor.transparent)
        pt = QPainter(res)
        pt.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, 64, 64, 8, 8)
        pt.setClipPath(path)
        pt.drawPixmap((64-scaled.width())//2, (64-scaled.height())//2, scaled)
        pt.end()
        self.art_label.setPixmap(res)

    def _on_slider_pressed(self): self.is_scrubbing = True
    def _on_slider_released(self):
        if self.track_length > 0:
            new_pos = (self.progress_slider.value() / 1000.0) * self.track_length
            subprocess.run(["playerctl", "position", str(new_pos)], stderr=subprocess.DEVNULL)
        self.is_scrubbing = False

    def _toggle_playback(self): subprocess.run(["playerctl", "play-pause"], stderr=subprocess.DEVNULL)
    def _adjust_offset(self, delta: float):
        self.current_offset += delta
        self.offset_label.setText(f"{'+' if self.current_offset > 0 else ''}{self.current_offset:.1f}s")
        self.offset_changed.emit(self.current_offset)

    def set_theme(self, primary_hex: str, secondary_hex: str):
        self.play_pause_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; border: none;
                color: {primary_hex}; font-size: 32px; padding-bottom: 4px;
                font-family: {_FONT_FAMILY};
            }}
            QPushButton:hover {{ color: {secondary_hex}; font-size: 36px; }}
        """)
        
        self.progress_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background-color: rgba(255,255,255,0.06); height: 4px; border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background-color: {secondary_hex}; height: 4px; border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background-color: {primary_hex}; width: 12px; height: 12px;
                margin: -4px 0; border-radius: 6px;
            }}
            QSlider::handle:horizontal:hover {{
                background-color: #ffffff; width: 14px; height: 14px; margin: -5px 0;
            }}
        """)
        
        self.title_label.setStyleSheet(f"color: {primary_hex}; font-weight: 800; font-size: 16px; font-family: {_FONT_FAMILY};")
        self.artist_label.setStyleSheet(f"color: {secondary_hex}; font-size: 14px; font-family: {_FONT_FAMILY};")
        self.time_lbl_curr.setStyleSheet(f"color: {secondary_hex}; font-size: 11px;")
        self.time_lbl_total.setStyleSheet(f"color: {secondary_hex}; font-size: 11px;")
        
        btn_style = f"""
            QPushButton {{ 
                background: transparent; border: none; color: {secondary_hex}; 
                font-family: {_FONT_FAMILY}; font-size: 14px;
            }}
            QPushButton:hover {{ color: {primary_hex}; }}
        """
        self.btn_sync.setStyleSheet(btn_style + "QPushButton { font-size: 18px; }")
        self.btn_offset_minus.setStyleSheet(btn_style)
        self.btn_offset_plus.setStyleSheet(btn_style)
        self.offset_label.setStyleSheet(f"color: {secondary_hex}; font-family: monospace; font-size: 11px;")

    def reset_offset(self):
        self.current_offset = 0.0
        self.offset_label.setText("±0.0s")
        self.offset_changed.emit(0.0)

    def set_offset_value(self, value: float):
        """Set offset to a specific value (e.g. the default 1.5s)."""
        self.current_offset = value
        self.offset_label.setText(f"{'+' if value > 0 else ''}{value:.1f}s")
        self.offset_changed.emit(value)
