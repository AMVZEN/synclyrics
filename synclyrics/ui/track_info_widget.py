import requests
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSlider, QFrame
from PyQt6.QtGui import QColor, QFont, QPixmap, QImage, QPainter, QPainterPath
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, pyqtProperty
import subprocess

class TrackInfoWidget(QWidget):
    sync_requested = pyqtSignal()
    offset_changed = pyqtSignal(float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(0)
        self._opacity = 1.0
        self._setup_ui()

    @pyqtProperty(float)
    def opacity(self): return self._opacity
    @opacity.setter
    def opacity(self, v):
        self._opacity = v
        self.update()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 10, 15, 10)
        
        # Transparent overlay container
        self.frame = QFrame()
        self.frame.setStyleSheet("background-color: transparent;")
        frame_layout = QHBoxLayout(self.frame)
        frame_layout.setContentsMargins(5, 5, 5, 5)
        frame_layout.setSpacing(18)
        
        # Album Art
        self.art_label = QLabel()
        self.art_label.setFixedSize(64, 64)
        self.art_label.setStyleSheet("background-color: rgba(255,255,255,0.03); border-radius: 8px;")
        frame_layout.addWidget(self.art_label)
        
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        self.title_label = QLabel("No track playing")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 16px; font-family: 'JetBrainsMono NF', 'FiraCode Nerd Font', monospace;")
        info_layout.addWidget(self.title_label)
        
        self.artist_label = QLabel("Waiting for MPRIS sync...")
        self.artist_label.setStyleSheet("font-size: 14px; font-family: 'JetBrainsMono NF', 'FiraCode Nerd Font', monospace; opacity: 0.7;")
        info_layout.addWidget(self.artist_label)
        
        frame_layout.addLayout(info_layout)
        frame_layout.addStretch()
        
        # Play/Pause button
        self.play_pause_btn = QPushButton("󰐊") # Nerd Font Play
        self.play_pause_btn.setFixedSize(48, 48)
        self.play_pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_pause_btn.clicked.connect(self._toggle_playback)
        frame_layout.addWidget(self.play_pause_btn)
        
        # Controls (Sync, Offset)
        self.controls_layout = QHBoxLayout()
        self.controls_layout.setSpacing(10)
        
        self.btn_sync = QPushButton("󰑐") # Sync icon
        self.btn_sync.setToolTip("Refresh Lyrics (Sync)")
        self.btn_sync.setFixedSize(32, 48)
        self.btn_sync.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sync.clicked.connect(self.sync_requested.emit)
        
        self.btn_offset_minus = QPushButton("-")
        self.btn_offset_minus.setToolTip("Subtract 0.5s offset")
        self.btn_offset_minus.setFixedSize(24, 48)
        self.btn_offset_minus.clicked.connect(lambda: self._adjust_offset(-0.5))
        
        self.offset_label = QLabel("±0.0s")
        self.offset_label.setFixedWidth(50)
        self.offset_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.offset_label.setStyleSheet("font-family: monospace; font-size: 11px;")
        
        self.btn_offset_plus = QPushButton("+")
        self.btn_offset_plus.setToolTip("Add 0.5s offset")
        self.btn_offset_plus.setFixedSize(24, 48)
        self.btn_offset_plus.clicked.connect(lambda: self._adjust_offset(0.5))
        
        self.controls_layout.addWidget(self.btn_sync)
        self.controls_layout.addWidget(self.btn_offset_minus)
        self.controls_layout.addWidget(self.offset_label)
        self.controls_layout.addWidget(self.btn_offset_plus)
        
        frame_layout.addLayout(self.controls_layout)
        
        main_layout.addWidget(self.frame)
        
        prog_layout = QHBoxLayout()
        prog_layout.setContentsMargins(5, 15, 5, 0)
        
        self.time_lbl_curr = QLabel("0:00")
        self.time_lbl_curr.setStyleSheet("font-size: 11px; font-family: 'JetBrainsMono NF', 'FiraCode Nerd Font', monospace; font-weight: bold; padding-right: 8px;")
        prog_layout.addWidget(self.time_lbl_curr)
        
        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, 1000)
        self.progress_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self.progress_slider.sliderReleased.connect(self._on_slider_released)
        prog_layout.addWidget(self.progress_slider)
        
        self.time_lbl_total = QLabel("0:00")
        self.time_lbl_total.setStyleSheet("font-size: 11px; font-family: 'JetBrainsMono NF', 'FiraCode Nerd Font', monospace; font-weight: bold; padding-left: 8px;")
        prog_layout.addWidget(self.time_lbl_total)
        
        main_layout.addLayout(prog_layout)
        
        self.track_length = 0.0
        self.current_offset = 0.0
        self.is_scrubbing = False

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
        
        if not self.is_scrubbing:
            self.progress_slider.setValue(0)
            self.time_lbl_curr.setText("0:00")
        
        self.track_length = float(info.get("length", 0.0))
        if self.track_length > 0:
            m, s = divmod(int(self.track_length), 60)
            self.time_lbl_total.setText(f"{m}:{s:02d}")
            
        art_url = info.get("artUrl", "")
        if art_url:
            self._load_art(art_url)
            
    def update_position(self, pos: float):
        if self.track_length > 0 and not self.is_scrubbing:
            m, s = divmod(int(pos), 60)
            self.time_lbl_curr.setText(f"{m}:{s:02d}")
            ratio = min(1.0, max(0.0, pos / self.track_length))
            
            self.progress_slider.blockSignals(True)
            self.progress_slider.setValue(int(ratio * 1000))
            self.progress_slider.blockSignals(False)

    def set_state(self, state: str):
        if state == "Playing":
            self.play_pause_btn.setText("󰏤") # Nerd Font Pause
        else:
            self.play_pause_btn.setText("󰐊") # Nerd Font Play

    def set_theme(self, primary_hex: str, secondary_hex: str):
        self.play_pause_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; border: none;
                color: {primary_hex}; font-size: 32px; padding-bottom: 4px;
                font-family: 'JetBrainsMono NF', 'FiraCode Nerd Font', monospace;
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
        
        self.title_label.setStyleSheet(f"color: {primary_hex}; font-weight: 800; font-size: 16px; font-family: 'JetBrainsMono NF', monospace;")
        self.artist_label.setStyleSheet(f"color: {secondary_hex}; font-size: 14px; font-family: 'JetBrainsMono NF', monospace;")
        self.time_lbl_curr.setStyleSheet(f"color: {secondary_hex}; font-size: 11px;")
        self.time_lbl_total.setStyleSheet(f"color: {secondary_hex}; font-size: 11px;")
        
        btn_style = f"""
            QPushButton {{ 
                background: transparent; border: none; color: {secondary_hex}; 
                font-family: "JetBrainsMono NF", monospace; font-size: 14px;
            }}
            QPushButton:hover {{ color: {primary_hex}; }}
        """
        self.btn_sync.setStyleSheet(btn_style + "QPushButton { font-size: 18px; }")
        self.btn_offset_minus.setStyleSheet(btn_style)
        self.btn_offset_plus.setStyleSheet(btn_style)
        self.offset_label.setStyleSheet(f"color: {secondary_hex}; font-family: monospace; font-size: 11px;")

    def _on_slider_pressed(self):
        self.is_scrubbing = True

    def _on_slider_released(self):
        if self.track_length > 0:
            ratio = self.progress_slider.value() / 1000.0
            new_pos = ratio * self.track_length
            try:
                subprocess.run(["playerctl", "position", str(new_pos)])
            except: pass
        self.is_scrubbing = False

    def _load_art(self, url: str):
        if url.startswith("file://"):
            p = QPixmap(url[7:])
            self._set_pixmap(p)
        elif url.startswith("http"):
            try:
                r = requests.get(url, timeout=2)
                i = QImage()
                i.loadFromData(r.content)
                self._set_pixmap(QPixmap.fromImage(i))
            except: pass

    def _set_pixmap(self, pixmap: QPixmap):
        if not pixmap.isNull():
            scaled = pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            rounded = QPixmap(64, 64)
            rounded.fill(Qt.GlobalColor.transparent)
            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(0, 0, 64, 64, 8, 8)
            painter.setClipPath(path)
            x = (64 - scaled.width()) // 2
            y = (64 - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
            painter.end()
            self.art_label.setPixmap(rounded)

    def _toggle_playback(self):
        try: subprocess.run(["playerctl", "play-pause"])
        except: pass

    def _adjust_offset(self, delta: float):
        self.current_offset += delta
        self.offset_label.setText(f"{'+' if self.current_offset > 0 else ''}{self.current_offset:.1f}s")
        self.offset_changed.emit(self.current_offset)
        
    def reset_offset(self):
        self.current_offset = 0.0
        self.offset_label.setText("±0.0s")
        self.offset_changed.emit(0.0)
