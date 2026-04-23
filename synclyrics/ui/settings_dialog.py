from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                              QComboBox, QCheckBox, QPushButton, QColorDialog, QFrame, QSlider, QScrollArea, QWidget)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

class SettingsDialog(QDialog):
    settings_changed = pyqtSignal(dict)
    
    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self.setWindowTitle("CONFIG")
        self.setFixedSize(540, 750)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.FramelessWindowHint)
        
        self.setStyleSheet("""
            QDialog { background-color: #0d0d0d; color: #ffffff; border: 2px solid #292929; border-radius: 12px; }
            QWidget { background-color: transparent; color: #ffffff; }
            QLabel { color: #f0f0f0; font-size: 13px; font-weight: bold; background: transparent; }
            QLabel[header="true"] { color: #bb9af7; font-size: 16px; margin-top: 10px; font-family: monospace; }
            QComboBox { 
                background: #1a1a1a; color: #ffffff; 
                border: 1px solid #333333; padding: 4px;
                font-family: inherit; font-size: 13px; border-radius: 4px;
            }
            QComboBox QAbstractItemView { background: #1a1a1a; selection-background-color: #333333; }
            QCheckBox { font-size: 13px; spacing: 8px; color: #f0f0f0; font-family: inherit; }
            QCheckBox::indicator { width: 14px; height: 14px; background: #1a1a1a; border: 1px solid #7aa2f7; border-radius: 3px; }
            QCheckBox::indicator:checked { background: #7aa2f7; }
            QPushButton { 
                background: #1a1a1a; color: #ffffff; border: 1px solid #333333; padding: 6px; font-family: inherit; font-weight: bold; border-radius: 4px;
            }
            QPushButton:hover { background: #333333; }
            QPushButton#primaryBtn { background: #7aa2f7; color: #ffffff; border: 2px solid white; font-weight: 800; }
            QPushButton#primaryBtn:hover { background: #94b9ff; border-color: #ffffff; }
            QSlider::groove:horizontal { background: #1a1a1a; height: 6px; border-radius: 3px; }
            QSlider::handle:horizontal { background: #7aa2f7; width: 14px; height: 14px; margin: -4px 0; border-radius: 7px; }
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { width: 8px; background: transparent; }
            QScrollBar::handle:vertical { background: #333333; border-radius: 4px; }
        """)
        
        self.settings = current_settings or {}
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(25, 25, 25, 25)
        
        # APPEARANCE
        h1 = QLabel("~ / APPEARANCE")
        h1.setProperty("header", True)
        content_layout.addWidget(h1)
        
        align_layout = QHBoxLayout()
        align_layout.addWidget(QLabel("TEXT ALIGN:"))
        self.align_cb = QComboBox()
        self.align_cb.setFixedWidth(150)
        self.align_cb.addItems(["Left", "Center", "Right"])
        self.align_cb.setCurrentText(self.settings.get("alignment", "Left"))
        align_layout.addWidget(self.align_cb)
        content_layout.addLayout(align_layout)
        
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("RICE THEME:"))
        self.theme_cb = QComboBox()
        self.theme_cb.setFixedWidth(180)
        self.theme_cb.addItems(["tokyo-night", "nord", "gruvbox", "rose-pine", "catppuccin-mocha", "everforest", "oxocarbon", "sweet", "synthwave", "custom"])
        self.theme_cb.setCurrentText(self.settings.get("theme", "tokyo-night"))
        theme_layout.addWidget(self.theme_cb)
        content_layout.addLayout(theme_layout)
        
        # ADVANCED CUSTOM THEME
        self.custom_box = QFrame()
        self.custom_box.setStyleSheet("background: transparent; border: none;")
        custom_vbox = QVBoxLayout(self.custom_box)
        custom_vbox.setContentsMargins(0, 5, 0, 5)
        custom_vbox.setSpacing(10)
        
        self.color_text = self._create_color_row(custom_vbox, "MAIN TEXT COLOR:", "custom_text_color", "#ffffff")
        self.color_muted = self._create_color_row(custom_vbox, "MUTED TEXT COLOR:", "custom_text_muted", "#666666")
        self.color_accent = self._create_color_row(custom_vbox, "ACCENT COLOR:", "custom_accent_color", "#7aa2f7")
        self.color_secondary = self._create_color_row(custom_vbox, "SECONDARY ACCENT:", "custom_secondary_color", "#bb9af7")
        self.color_bg = self._create_color_row(custom_vbox, "BACKGROUND COLOR:", "custom_bg_color", "#0b0b0b")
        self.color_surface = self._create_color_row(custom_vbox, "SURFACE COLOR (BORDERS):", "custom_surface_color", "#1e1e1e")
        
        content_layout.addWidget(self.custom_box)
        self.theme_cb.currentTextChanged.connect(lambda t: self.custom_box.setVisible(t == "custom"))
        self.custom_box.setVisible(self.theme_cb.currentText() == "custom")
        
        # MODULES
        h2 = QLabel("~ / MODULES")
        h2.setProperty("header", True)
        content_layout.addWidget(h2)
        
        self.on_top_chk = QCheckBox("FLOAT ALWAYS ON TOP")
        self.on_top_chk.setChecked(self.settings.get("always_on_top", True))
        content_layout.addWidget(self.on_top_chk)
        
        self.romanize_chk = QCheckBox("FETCH ROMANIZATION")
        self.romanize_chk.setChecked(self.settings.get("romanize", True))
        content_layout.addWidget(self.romanize_chk)
        
        self.visualizer_chk = QCheckBox("WAVEFORM VISUALIZER")
        self.visualizer_chk.setChecked(self.settings.get("visualizer", True))
        content_layout.addWidget(self.visualizer_chk)
        
        vis_type_layout = QHBoxLayout()
        vis_type_layout.addWidget(QLabel("VISUALIZER STYLE:"))
        self.vis_type_cb = QComboBox()
        self.vis_type_cb.setFixedWidth(150)
        self.vis_type_cb.addItems(["fluid-wave", "classic-bars", "cyber-bars", "radial-sunburst", 
                                   "neon-strings", "digital-dots", "milkdrop"])
        self.vis_type_cb.setCurrentText(self.settings.get("vis_type", "fluid-wave"))
        vis_type_layout.addWidget(self.vis_type_cb)
        content_layout.addLayout(vis_type_layout)
        
        # === MILKDROP SETTINGS (collapsible) ===
        self.milkdrop_box = QFrame()
        self.milkdrop_box.setStyleSheet("""
            QFrame { 
                background: rgba(122, 162, 247, 0.05); 
                border: 1px solid rgba(122, 162, 247, 0.15); 
                border-radius: 8px; 
                padding: 4px;
            }
        """)
        md_vbox = QVBoxLayout(self.milkdrop_box)
        md_vbox.setContentsMargins(12, 10, 12, 10)
        md_vbox.setSpacing(10)
        
        md_header = QLabel("⟡ MILKDROP CONFIG")
        md_header.setStyleSheet("color: #bb9af7; font-size: 12px; font-family: monospace; font-weight: bold; border: none;")
        md_vbox.addWidget(md_header)
        
        self.md_random_chk = QCheckBox("RANDOMIZE PRESETS (CYCLE)")
        self.md_random_chk.setChecked(self.settings.get("md_random_cycle", True))
        md_vbox.addWidget(self.md_random_chk)
        
        # Cycle interval
        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("CYCLE INTERVAL:"))
        self.md_interval_val = QLabel(f"{self.settings.get('md_cycle_interval', 15)}s")
        interval_row.addStretch()
        interval_row.addWidget(self.md_interval_val)
        md_vbox.addLayout(interval_row)
        
        self.md_interval_slider = QSlider(Qt.Orientation.Horizontal)
        self.md_interval_slider.setRange(5, 120)
        self.md_interval_slider.setValue(self.settings.get("md_cycle_interval", 15))
        self.md_interval_slider.valueChanged.connect(lambda v: self.md_interval_val.setText(f"{v}s"))
        md_vbox.addWidget(self.md_interval_slider)
        
        # Preset selector
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("PRESET:"))
        self.md_preset_cb = QComboBox()
        self.md_preset_cb.setFixedWidth(280)
        self.md_preset_cb.setEditable(True)
        self.md_preset_cb.lineEdit().setPlaceholderText("type to search...")
        
        # Populate from stored preset list
        preset_list = self.settings.get("md_presets_list", [])
        if preset_list:
            self.md_preset_cb.addItems(preset_list)
        current_preset = self.settings.get("md_preset", "")
        if current_preset:
            self.md_preset_cb.setCurrentText(current_preset)
        
        preset_row.addWidget(self.md_preset_cb)
        md_vbox.addLayout(preset_row)
        
        # Toggle interval slider based on random checkbox
        self.md_random_chk.toggled.connect(lambda checked: self.md_interval_slider.setEnabled(checked))
        self.md_interval_slider.setEnabled(self.md_random_chk.isChecked())
        
        content_layout.addWidget(self.milkdrop_box)
        
        # Show/hide milkdrop settings
        self.vis_type_cb.currentTextChanged.connect(self._on_vis_type_changed)
        self.milkdrop_box.setVisible(self.vis_type_cb.currentText() == "milkdrop")
        
        # FX INTENSITY
        # Offset
        offset_layout = QHBoxLayout()
        offset_layout.addWidget(QLabel("DEFAULT LYRIC OFFSET (s)"))
        self.offset_slider = QSlider(Qt.Orientation.Horizontal)
        self.offset_slider.setRange(-50, 50)  # -5.0 to 5.0
        self.offset_slider.setValue(int(float(self.settings.get("default_offset", 0.0)) * 10))
        offset_layout.addWidget(self.offset_slider)
        self.offset_val_lbl = QLabel(f"{self.offset_slider.value()/10.0:+.1f}s")
        self.offset_slider.valueChanged.connect(lambda v: self.offset_val_lbl.setText(f"{v/10.0:+.1f}s"))
        offset_layout.addWidget(self.offset_val_lbl)
        content_layout.addLayout(offset_layout)

        content_layout.addSpacing(10)
        self.vig_slider = self._add_slider_row(content_layout, "VIGNETTE INTENSITY (POWER)", "vignette_intensity")
        self.glow_slider = self._add_slider_row(content_layout, "GLOW INTENSITY (DREAMY)", "glow_intensity")
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # FOOTER
        footer = QFrame()
        footer.setFixedHeight(60)
        footer.setStyleSheet("background: #0d0d0d; border-top: 1px solid #333333;")
        footer_layout = QHBoxLayout(footer)
        
        cancel_btn = QPushButton("CANCEL")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("APPLY CONFIG")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._save)
        
        footer_layout.addStretch()
        footer_layout.addWidget(cancel_btn)
        footer_layout.addWidget(save_btn)
        layout.addWidget(footer)

    def _on_vis_type_changed(self, vis_type):
        self.milkdrop_box.setVisible(vis_type == "milkdrop")

    def update_milkdrop_presets(self, preset_names):
        """Called externally to populate the preset dropdown after async load."""
        current = self.md_preset_cb.currentText()
        self.md_preset_cb.clear()
        self.md_preset_cb.addItems(preset_names)
        if current:
            self.md_preset_cb.setCurrentText(current)

    def _create_color_row(self, layout, label, key, default):
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        btn = QPushButton()
        btn.setProperty("isColor", True)
        btn.setFixedSize(60, 24)
        color = self.settings.get(key, default)
        btn.color = color
        self._set_btn_color(btn, color)
        btn.clicked.connect(lambda: self._pick_color(btn))
        row.addStretch()
        row.addWidget(btn)
        layout.addLayout(row)
        return btn

    def _add_slider_row(self, layout, title, key):
        vbox = QVBoxLayout()
        row = QHBoxLayout()
        row.addWidget(QLabel(title))
        val_lbl = QLabel(f"{self.settings.get(key, 0)}%")
        row.addStretch()
        row.addWidget(val_lbl)
        vbox.addLayout(row)
        
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(self.settings.get(key, 0))
        slider.valueChanged.connect(lambda v: val_lbl.setText(f"{v}%"))
        vbox.addWidget(slider)
        layout.addLayout(vbox)
        return slider

    def _set_btn_color(self, btn, color):
        btn.setStyleSheet(f"background-color: {color}; border-radius: 4px; border: 2px solid rgba(255,255,255,0.2);")
        btn.color = color

    def _pick_color(self, btn):
        color = QColorDialog.getColor(initial=QColor(btn.color), parent=self)
        if color.isValid():
            c_name = color.name()
            self._set_btn_color(btn, c_name)

    def _save(self):
        new_settings = {
            "alignment": self.align_cb.currentText(),
            "theme": self.theme_cb.currentText(),
            "custom_text_color": self.color_text.color,
            "custom_text_muted": self.color_muted.color,
            "custom_accent_color": self.color_accent.color,
            "custom_secondary_color": self.color_secondary.color,
            "custom_bg_color": self.color_bg.color,
            "custom_surface_color": self.color_surface.color,
            "always_on_top": self.on_top_chk.isChecked(),
            "romanize": self.romanize_chk.isChecked(),
            "visualizer": self.visualizer_chk.isChecked(),
            "vis_type": self.vis_type_cb.currentText(),
            "vignette_intensity": self.vig_slider.value(),
            "glow_intensity": self.glow_slider.value(),
            # Milkdrop settings
            "md_random_cycle": self.md_random_chk.isChecked(),
            "md_cycle_interval": self.md_interval_slider.value(),
            "md_preset": self.md_preset_cb.currentText(),
            "default_offset": self.offset_slider.value() / 10.0
        }
        self.settings_changed.emit(new_settings)
        self.accept()
