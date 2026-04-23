import sys
import os
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                            QLabel, QPushButton, QApplication, QSizeGrip, QGraphicsOpacityEffect)
from PyQt6.QtCore import Qt, QSettings, QPropertyAnimation, QEasingCurve, QTimer, pyqtProperty
from PyQt6.QtGui import QKeyEvent
from synclyrics.ui.lyrics_widget import LyricsWidget
from synclyrics.ui.visualizer_widget import VisualizerWidget
from synclyrics.ui.track_info_widget import TrackInfoWidget
from synclyrics.ui.theme import ThemeManager

from synclyrics.player.monitor import PlayerMonitor
from synclyrics.lyrics.fetcher import LyricsFetcher, FetchRequest
from synclyrics.lyrics.romanizer import Romanizer
import subprocess

# Optional milkdrop import
try:
    from synclyrics.ui.milkdrop_widget import MilkdropWidget, HAS_WEBENGINE
except ImportError:
    HAS_WEBENGINE = False
    MilkdropWidget = None

class ModernTitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(0)
        self.setMaximumHeight(30)
        self._opacity = 1.0
        self.parent_window = parent
        self._setup_ui()

    @pyqtProperty(float)
    def opacity(self): return self._opacity
    @opacity.setter
    def opacity(self, v):
        self._opacity = v
        self.update()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 10, 0)
        
        self.title = QLabel("~ / usr / bin / synclyrics")
        self.title.setStyleSheet("font-family: monospace; font-weight: bold; font-size: 11px; opacity: 0.6;")
        layout.addWidget(self.title)
        
        layout.addStretch()
        
        self.btn_settings = QPushButton("☰")
        self.btn_minimize = QPushButton("—")
        self.btn_close = QPushButton("✕")
        
        for btn in (self.btn_settings, self.btn_minimize, self.btn_close):
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(btn)
            
        self.btn_minimize.clicked.connect(self.parent_window.showMinimized)
        self.btn_close.clicked.connect(self.parent_window.close)
        self.btn_settings.clicked.connect(self.parent_window.open_settings)
        
        self.start_pos = None

    def set_colors(self, primary, error):
        self.title.setStyleSheet(f"color: {primary}; font-family: monospace; font-weight: bold; font-size: 11px; opacity: 0.6;")
        self.btn_settings.setStyleSheet(f"QPushButton {{ color: {primary}; border:none; font-size:16px; background:transparent;}} QPushButton:hover {{ color: white; }}")
        self.btn_minimize.setStyleSheet(f"QPushButton {{ color: {primary}; border:none; font-size:16px; font-weight:bold; background:transparent;}} QPushButton:hover {{ color: white; }}")
        self.btn_close.setStyleSheet(f"QPushButton {{ color: {error}; border:none; font-size:16px; font-weight:bold; background:transparent;}} QPushButton:hover {{ color: white; }}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.start_pos is not None:
            delta = event.globalPosition().toPoint() - self.start_pos
            self.parent_window.move(self.parent_window.pos() + delta)
            self.start_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.start_pos = None

class MainWindow(QMainWindow):
    DEFAULT_OFFSET = 1.5

    def __init__(self):
        super().__init__()
        
        self.qsettings = QSettings("SyncLyrics", "App")
        
        self._set_flags()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(550, 800)
        
        self._all_lyrics_results = []
        self._current_result_idx = 0
        self._track_lyric_memory = {}
        self._milkdrop_preset_names = []
        
        # Base container
        self.base_container = QWidget()
        self.setCentralWidget(self.base_container)
        
        self.layout_root = QGridLayout(self.base_container)
        self.layout_root.setContentsMargins(0, 0, 0, 0)
        self.layout_root.setSpacing(0)
        
        # Layer 0: Background Visualizer (native)
        self.central_bg = VisualizerWidget(self)
        self.layout_root.addWidget(self.central_bg, 0, 0)
        
        # Layer 0.5: Milkdrop Visualizer (WebEngine overlay)
        self.milkdrop = None
        if HAS_WEBENGINE and MilkdropWidget:
            self.milkdrop = MilkdropWidget(self)
            self.milkdrop.presets_loaded.connect(self._on_milkdrop_presets_loaded)
            self.layout_root.addWidget(self.milkdrop, 0, 0)
            self.milkdrop.hide()
        
        # Layer 1: Foreground Content
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        self.layout_root.addWidget(self.content_widget, 0, 0)
        
        self.title_bar = ModernTitleBar(self)
        self.content_layout.addWidget(self.title_bar)
        
        self.track_info = TrackInfoWidget(self)
        self.content_layout.addWidget(self.track_info)
        
        self.lyrics_widget = LyricsWidget(self)
        self.content_layout.addWidget(self.lyrics_widget, 1)
        
        self.grip = QSizeGrip(self)
        self.grip.setFixedSize(16, 16)
        
        self.player_monitor = PlayerMonitor(self)
        self.player_monitor.track_changed.connect(self._on_track_changed)
        self.player_monitor.position_updated.connect(self._on_position_updated)
        self.player_monitor.state_changed.connect(self.track_info.set_state)
        
        self.track_info.sync_requested.connect(self._manual_sync)
        self.track_info.offset_changed.connect(self.lyrics_widget.set_offset)
        
        # UI State cycle (4 modes now)
        self.ui_state = 0 
        self.cycle_btn = QPushButton("󰒲", self.content_widget) 
        self.cycle_btn.setFixedSize(32, 32)
        self.cycle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cycle_btn.setToolTip("Cycle UI Modes (Stealth)")
        self.cycle_btn.clicked.connect(self._cycle_ui_state)
        self.cycle_btn.raise_()
        
        # "Try other lyrics" button
        self.alt_lyrics_btn = QPushButton("⟳ ALT", self.content_widget)
        self.alt_lyrics_btn.setFixedSize(64, 28)
        self.alt_lyrics_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.alt_lyrics_btn.setToolTip("Cycle through alternative lyrics sources")
        self.alt_lyrics_btn.clicked.connect(self._cycle_lyrics_source)
        self.alt_lyrics_btn.raise_()
        self.alt_lyrics_btn.hide()
        
        self.fetcher_thread = None
        ThemeManager.get().register_callback(self._apply_theme)
        
        self._load_settings()
        self.player_monitor.start()

    def _on_milkdrop_presets_loaded(self, names):
        self._milkdrop_preset_names = names

    def _is_milkdrop_active(self):
        vis_type = self.qsettings.value("vis_type", "fluid-wave")
        vis_enabled = self.qsettings.value("visualizer", True, type=bool)
        return vis_type == "milkdrop" and vis_enabled and self.milkdrop is not None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        rect = self.rect()
        self.grip.move(rect.right() - 16, rect.bottom() - 16)
        self.cycle_btn.move(rect.right() - 40, rect.bottom() - 40)
        self.alt_lyrics_btn.move(12, rect.bottom() - 36)

    def _set_flags(self):
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        if self.qsettings.value("always_on_top", True, type=bool):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    def _load_settings(self):
        theme_name = self.qsettings.value("theme", "tokyo-night")
        if theme_name == "custom":
            ThemeManager.get().set_custom_color(
                "#7aa2f7",
                text_main=self.qsettings.value("custom_text_color", "#ffffff"),
                text_muted=self.qsettings.value("custom_text_muted", "#666666"),
                primary=self.qsettings.value("custom_accent_color", "#7aa2f7"),
                secondary=self.qsettings.value("custom_secondary_color", "#bb9af7"),
                bg=self.qsettings.value("custom_bg_color", "#0b0b0b"),
                surface=self.qsettings.value("custom_surface_color", "#1e1e1e")
            )
        else:
            ThemeManager.get().set_preset(theme_name)
            
        self.lyrics_widget.set_alignment(self.qsettings.value("alignment", "Left"))
        
        vis_enabled = self.qsettings.value("visualizer", True, type=bool)
        vis_type = self.qsettings.value("vis_type", "fluid-wave")
        
        # Handle milkdrop vs native visualizer switching
        if vis_type == "milkdrop" and self.milkdrop:
            self.central_bg.set_enabled(False)
            self.milkdrop.show()
            self.milkdrop.start_audio()
            # Apply milkdrop settings
            md_random = self.qsettings.value("md_random_cycle", True, type=bool)
            md_interval = self.qsettings.value("md_cycle_interval", 15, type=int)
            md_preset = self.qsettings.value("md_preset", "")
            self.milkdrop.set_random_cycle(md_random, md_interval)
            if md_preset and not md_random:
                self.milkdrop.load_preset(md_preset)
            # Blur when lyrics are visible (state 0 or 1)
            self._update_milkdrop_blur()
        else:
            self.central_bg.set_enabled(vis_enabled)
            self.central_bg.set_type(vis_type)
            if self.milkdrop:
                self.milkdrop.hide()
                self.milkdrop.stop_audio()
        
        self.central_bg.set_vignette(self.qsettings.value("vignette_intensity", 0, type=int))
        self.lyrics_widget.set_glow(self.qsettings.value("glow_intensity", 0, type=int))

    def _update_milkdrop_blur(self):
        """Set milkdrop blur based on whether lyrics are currently visible."""
        if not self.milkdrop or not self._is_milkdrop_active():
            return
        # States where lyrics are visible: 0, 1, 3
        # State 2: vis only → no blur
        lyrics_visible = self.ui_state != 2
        self.milkdrop.set_blur(lyrics_visible)

    def _apply_theme(self, theme):
        self.central_bg.setObjectName("CentralBG")
        sheet = f"""
            #CentralBG {{
                border: 2px solid {theme.surface_alt};
                border-radius: 12px;
            }}
        """
        self.central_bg.setStyleSheet(sheet)
        self.central_bg.set_colors(theme.primary, theme.secondary)
        self.central_bg.set_bg_color(theme.background)
        
        self.lyrics_widget.set_theme(theme.text_main, theme.text_muted, theme.primary)
        self.track_info.set_theme(theme.primary, theme.secondary)
        self.title_bar.set_colors(theme.text_muted, theme.error)
        
        self.cycle_btn.setStyleSheet(f"""
            QPushButton {{ 
                background-color: rgba(0,0,0,0.1); border: 2px solid {theme.surface_alt}; 
                border-radius: 16px; color: {theme.primary}; font-size: 16px; 
            }}
            QPushButton:hover {{ background-color: {theme.surface_alt}; color: #ffffff; }}
        """)
        
        self.alt_lyrics_btn.setStyleSheet(f"""
            QPushButton {{ 
                background-color: rgba(0,0,0,0.4); 
                border: 1px solid {theme.surface_alt}; 
                border-radius: 6px; 
                color: {theme.text_muted}; 
                font-size: 10px;
                font-family: 'JetBrainsMono NF', monospace;
                font-weight: bold;
                padding: 2px 6px;
            }}
            QPushButton:hover {{ 
                background-color: {theme.surface_alt}; 
                color: {theme.primary}; 
            }}
        """)

    def open_settings(self):
        from synclyrics.ui.settings_dialog import SettingsDialog
        current = {
            "alignment": self.qsettings.value("alignment", "Left"),
            "theme": self.qsettings.value("theme", "tokyo-night"),
            "custom_text_color": self.qsettings.value("custom_text_color", "#ffffff"),
            "custom_text_muted": self.qsettings.value("custom_text_muted", "#666666"),
            "custom_accent_color": self.qsettings.value("custom_accent_color", "#7aa2f7"),
            "custom_secondary_color": self.qsettings.value("custom_secondary_color", "#bb9af7"),
            "custom_bg_color": self.qsettings.value("custom_bg_color", "#0b0b0b"),
            "custom_surface_color": self.qsettings.value("custom_surface_color", "#1e1e1e"),
            "always_on_top": self.qsettings.value("always_on_top", True, type=bool),
            "romanize": self.qsettings.value("romanize", True, type=bool),
            "visualizer": self.qsettings.value("visualizer", True, type=bool),
            "vis_type": self.qsettings.value("vis_type", "fluid-wave"),
            "vignette_intensity": self.qsettings.value("vignette_intensity", 0, type=int),
            "glow_intensity": self.qsettings.value("glow_intensity", 0, type=int),
            # Milkdrop
            "md_random_cycle": self.qsettings.value("md_random_cycle", True, type=bool),
            "md_cycle_interval": self.qsettings.value("md_cycle_interval", 15, type=int),
            "md_preset": self.qsettings.value("md_preset", ""),
            "md_presets_list": self._milkdrop_preset_names,
            "default_offset": self.qsettings.value("default_offset", 0.0, type=float),
        }
        
        dlg = SettingsDialog(self, current)
        ThemeManager.get().register_callback(lambda t: self._color_dlg(dlg, t))
        self._color_dlg(dlg, ThemeManager.get().theme)
        
        # If milkdrop presets load while dialog is open, update it
        if self.milkdrop:
            self.milkdrop.presets_loaded.connect(dlg.update_milkdrop_presets)
        
        dlg.settings_changed.connect(self._save_settings)
        dlg.exec()

    def _color_dlg(self, dlg, t):
        dlg.setStyleSheet(dlg.styleSheet().replace("#0d0d0d", t.background).replace("#7aa2f7", t.primary).replace("#333333", t.surface).replace("#bb9af7", t.secondary))
        
    def _save_settings(self, new_settings):
        for k, v in new_settings.items():
            self.qsettings.setValue(k, v)
        try:
             self._set_flags()
             self.show()
             self._load_settings()
        except: pass

    def _on_track_changed(self, info: dict):
        self.track_info.update_track(info)
        if not info:
             self.lyrics_widget.set_lyrics(None)
             self.track_info.reset_offset()
             self._all_lyrics_results = []
             self._current_result_idx = 0
             self.alt_lyrics_btn.hide()
             return
             
        default_offset = self.qsettings.value("default_offset", 0, type=float)
        self.track_info.set_offset_value(default_offset)
        self._fetch_lyrics(info)

    def _manual_sync(self):
        info = self.player_monitor.last_info
        if info:
            self._fetch_lyrics(info)

    def _fetch_lyrics(self, info: dict):
        from synclyrics.lyrics.parser import LyricsResult
        empty = LyricsResult(plain_text="[ Fetching latest lyrics... ]")
        self.lyrics_widget.set_lyrics(empty)
        self.lyrics_widget.update_position(0.0)
        self.alt_lyrics_btn.hide()
        
        if self.fetcher_thread and self.fetcher_thread.isRunning():
            self.fetcher_thread.terminate()
            
        should_romanize = self.qsettings.value("romanize", True, type=bool)
        req = FetchRequest(
            artist=info.get("artist", ""), 
            title=info.get("title", ""), 
            album=info.get("album", ""), 
            duration=info.get("length", 0.0),
            romanize=should_romanize
        )
        self.fetcher_thread = LyricsFetcher(req)
        self.fetcher_thread.lyrics_ready.connect(self._on_lyrics_ready)
        self.fetcher_thread.error_occurred.connect(self._on_lyrics_error)
        self.fetcher_thread.start()

    def _on_lyrics_error(self, message):
        self.lyrics_widget.set_error(message)

    def _on_lyrics_ready(self, results_list, default_idx, req):
        self._all_lyrics_results = results_list
        
        track_key = (req.artist.lower().strip(), req.title.lower().strip())
        if track_key in self._track_lyric_memory:
            preferred = self._track_lyric_memory[track_key]
            if preferred < len(results_list):
                default_idx = preferred
        
        self._current_result_idx = default_idx
        self.lyrics_widget.set_lyrics(results_list[default_idx])
        
        if len(results_list) > 1:
            self.alt_lyrics_btn.setText(f"⟳ 1/{len(results_list)}")
            self.alt_lyrics_btn.show()
        else:
            self.alt_lyrics_btn.hide()

    def _cycle_lyrics_source(self):
        if len(self._all_lyrics_results) <= 1:
            return
        
        self._current_result_idx = (self._current_result_idx + 1) % len(self._all_lyrics_results)
        result = self._all_lyrics_results[self._current_result_idx]
        self.lyrics_widget.set_lyrics(result)
        
        total = len(self._all_lyrics_results)
        self.alt_lyrics_btn.setText(f"⟳ {self._current_result_idx + 1}/{total}")
        
        info = self.player_monitor.last_info
        if info:
            track_key = (info.get("artist", "").lower().strip(), 
                        info.get("title", "").lower().strip())
            self._track_lyric_memory[track_key] = self._current_result_idx

    def _on_position_updated(self, pos: float):
        self.track_info.update_position(pos)
        self.lyrics_widget.update_position(pos)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Space:
            try: subprocess.run(["playerctl", "play-pause"])
            except: pass
        elif event.key() == Qt.Key.Key_Escape:
            if self.ui_state != 0:
                self.ui_state = 3  # So next cycle is 0
                self._cycle_ui_state()
        elif event.key() == Qt.Key.Key_R:
            self._manual_sync()
        elif event.key() == Qt.Key.Key_N:
            self._cycle_lyrics_source()
        else:
            super().keyPressEvent(event)

    def _cycle_ui_state(self):
        num_states = 4 if self._is_milkdrop_active() else 3
        self.ui_state = (self.ui_state + 1) % num_states
        
        from PyQt6.QtCore import QParallelAnimationGroup
        self.anim_group = QParallelAnimationGroup()
        
        if self._is_milkdrop_active():
            # 4-state cycle for milkdrop
            states = [
                # title,       track,        lyrics, vis, waves
                [(1.0, 30),  (1.0, 120),    1.0,   1.0,  1.0],  # 0: All (blurred)
                [(0.0, 0),   (0.0, 0),      1.0,   1.0,  1.0],  # 1: Lyrics+Vis (blurred)
                [(0.0, 0),   (0.0, 0),      0.0,   1.0,  1.0],  # 2: Vis Only (clear!)
                [(0.0, 0),   (0.0, 0),      1.0,   1.0,  0.0],  # 3: Lyrics Only
            ]
        else:
            # Original 3-state cycle for native visualizers
            states = [
                [(1.0, 30),  (1.0, 120), 1.0, 1.0, 1.0],  # 0: All
                [(0.0, 0),   (0.0, 0),   1.0, 1.0, 1.0],  # 1: Lyrics + Vis
                [(0.0, 0),   (0.0, 0),   1.0, 1.0, 0.0],  # 2: Lyrics (BG Only)
            ]
        
        t_title, t_track, o_lyrics, o_vis, o_waves = states[self.ui_state]
        
        self.anim_group.addAnimation(self._animate_widget_stealth(self.title_bar, t_title[0], t_title[1]))
        self.anim_group.addAnimation(self._animate_widget_stealth(self.track_info, t_track[0], t_track[1]))
        
        self.anim_group.addAnimation(self._create_opacity_anim(self.lyrics_widget, o_lyrics))
        self.anim_group.addAnimation(self._create_opacity_anim(self.central_bg, o_vis))
        
        waves_anim = QPropertyAnimation(self.central_bg, b"waves_opacity")
        waves_anim.setDuration(400)
        waves_anim.setStartValue(self.central_bg.waves_opacity)
        waves_anim.setEndValue(o_waves)
        waves_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.anim_group.addAnimation(waves_anim)
        
        # Milkdrop blur: blur when lyrics visible, clear when vis-only
        self._update_milkdrop_blur()
        
        self.anim_group.start()

    def _animate_widget_stealth(self, widget, target_opacity, normal_height):
        target_height = normal_height if target_opacity > 0.5 else 0
        h_anim = QPropertyAnimation(widget, b"maximumHeight")
        h_anim.setDuration(400)
        h_anim.setStartValue(widget.height())
        h_anim.setEndValue(target_height)
        h_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        
        self.anim_group.addAnimation(self._create_opacity_anim(widget, target_opacity))
        return h_anim

    def _create_opacity_anim(self, widget, target):
        if hasattr(widget, "opacity") and not isinstance(widget, QGraphicsOpacityEffect):
            anim = QPropertyAnimation(widget, b"opacity")
            anim.setStartValue(widget.opacity)
        else:
            eff = widget.graphicsEffect()
            if not eff or not isinstance(eff, QGraphicsOpacityEffect):
                eff = QGraphicsOpacityEffect(widget)
                widget.setGraphicsEffect(eff)
            anim = QPropertyAnimation(eff, b"opacity")
            anim.setStartValue(eff.opacity())
            
        anim.setDuration(400)
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        
        if target > 0.01:
            widget.show()
            if widget == self.lyrics_widget:
                QTimer.singleShot(50, lambda: self.lyrics_widget.update_position(self.player_monitor.last_reported_pos))
        
        def on_finished():
            if target < 0.01 and widget not in (self.central_bg, self.content_widget):
                widget.hide()
                
        anim.finished.connect(on_finished)
        return anim

    def closeEvent(self, event):
        if self.player_monitor:
            self.player_monitor.stop()
        if self.fetcher_thread and self.fetcher_thread.isRunning():
            self.fetcher_thread.terminate()
            self.fetcher_thread.wait()
        if self.central_bg:
            self.central_bg.stop_audio_capture()
        if self.milkdrop:
            self.milkdrop.cleanup()
        super().closeEvent(event)
