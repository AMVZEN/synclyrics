from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QLabel
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, pyqtProperty, QEasingCurve
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from typing import List
import math
import time
import bisect
from synclyrics.lyrics.parser import LyricsResult, LyricLine

class SquiggleWidget(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.phase = 0.0
        self.main_opacity = 0.0
        self.setMinimumHeight(24) # Smaller squiggle
        self.setMaximumHeight(24)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_phase)
        # Don't start until needed
        self.color_active = QColor("#ffffff")
        self.color_inactive = QColor("#555555")
        self.is_highlit = False

    def _update_phase(self):
        self.phase += 0.08 # Slower wiggle
        self.update()

    def set_main_opacity(self, val, highlighted=False):
        self.main_opacity = val
        self.is_highlit = highlighted
        if val > 0.1:
            if not self.timer.isActive(): self.timer.start(30)
        else:
            if self.timer.isActive(): self.timer.stop()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        path = QPainterPath()
        w = self.width()
        h = self.height()
        mid_y = h / 2
        
        # Center the squiggle and limit its width to e.g. 250px
        s_width = 250
        start_x = (w - s_width) / 2
        
        path.moveTo(start_x, mid_y)
        for x in range(int(start_x), int(start_x + s_width), 5):
            # Tapered amplitude to avoid cut-off look
            rx = (x - start_x) / s_width # 0.0 -> 1.0
            taper = math.sin(rx * math.pi) # Smooth arc multiplier
            
            y = mid_y + math.sin((x / 30.0) + self.phase) * (10 * taper)
            path.lineTo(x, y)
        
        c = QColor(self.color_active if self.is_highlit else self.color_inactive)
        c.setAlpha(int(255 * self.main_opacity)) # Only show if main_opacity > 0
        
        pen = QPen(c, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(path)

class AnimatedScrollArea(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scroll_value = 0
        self.animation = QPropertyAnimation(self, b"scroll_value")
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.setDuration(400) # Smooth hyprland easing

    @pyqtProperty(int)
    def scroll_value(self): return self.verticalScrollBar().value()

    @scroll_value.setter
    def scroll_value(self, val): self.verticalScrollBar().setValue(val)

    def smooth_scroll_to(self, target_y):
        vbar = self.verticalScrollBar()
        current = vbar.value()
        target = target_y - (self.viewport().height() // 2)
        target = max(0, min(target, vbar.maximum()))
        self.animation.stop()
        self.animation.setStartValue(current)
        self.animation.setEndValue(target)
        self.animation.start()

class LyricLabel(QLabel):
    def __init__(self, text="", parent=None, font_size=18, color_active="#ffffff", color_inactive="#666666"):
        super().__init__(text, parent)
        self._active_factor = 0.0 # 0.0 (muted) -> 1.0 (active)
        self.base_font_size = font_size
        self.color_active = QColor(color_active)
        self.color_inactive = QColor(color_inactive)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        self.anim = QPropertyAnimation(self, b"activeFactor")
        self.anim.setDuration(250)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    @pyqtProperty(float)
    def activeFactor(self):
        return self._active_factor

    @activeFactor.setter
    def activeFactor(self, val):
        self._active_factor = val
        self._apply_style()

    def _apply_style(self):
        # Interpolate font size
        size = self.base_font_size + (4 * self._active_factor)
        
        # Interpolate color
        r = int(self.color_inactive.red() + (self.color_active.red() - self.color_inactive.red()) * self._active_factor)
        g = int(self.color_inactive.green() + (self.color_active.green() - self.color_inactive.green()) * self._active_factor)
        b = int(self.color_inactive.blue() + (self.color_active.blue() - self.color_inactive.blue()) * self._active_factor)
        
        # Interpolate weight
        weight = 500 + int(300 * self._active_factor)
        
        self.setStyleSheet(f"""
            color: rgb({r}, {g}, {b});
            font-size: {size}px;
            font-family: "JetBrainsMono NF", "FiraCode Nerd Font", monospace;
            font-weight: {weight};
            background: transparent;
            padding: 8px 14px;
        """)

    def update_colors(self, active, inactive):
        self.color_active = QColor(active)
        self.color_inactive = QColor(inactive)
        self._apply_style()

    def set_active(self, active: bool):
        target = 1.0 if active else 0.0
        if self.anim.endValue() == target: return
        self.anim.stop()
        self.anim.setStartValue(self._active_factor)
        self.anim.setEndValue(target)
        self.anim.start()

class LyricsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_area = AnimatedScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll_area.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 3px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.05);
                min-height: 20px;
                border-radius: 1px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255, 255, 255, 0.2);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.content_layout.setSpacing(12) 
        self.content_layout.setContentsMargins(30, 200, 30, 200) 
        
        self.scroll_area.setWidget(self.content_widget)
        self.layout.addWidget(self.scroll_area)
        
        self.line_labels: List[QLabel] = []
        self.current_lyrics: LyricsResult = None
        self.current_active_idx = -1
        
        self.alignment = Qt.AlignmentFlag.AlignLeft
        self.font_size = 18 
        
        self.color_active = "#ffffff"
        self.color_inactive = "#aaaaaa"
        self.color_accent = "#ffffff"
        self.lyric_offset = 0.0 # Manual offset in seconds
        self.glow_intensity = 0 # 0-100
        self.rendered_lines: List[LyricLine] = []
        self.lyric_times: List[float] = []
        self.last_word_idx = -1
        self._opacity = 1.0
        
    @pyqtProperty(float)
    def opacity(self): return self._opacity
    @opacity.setter
    def opacity(self, v):
        self._opacity = v
        self.update()

    def set_theme(self, text_main, text_muted, primary_accent):
        self.color_active = text_main
        self.color_inactive = text_muted
        self.color_accent = primary_accent
        
        # Propagate to existing labels
        for lbl in self.line_labels:
            if isinstance(lbl, LyricLabel):
                lbl.update_colors(text_main, text_muted)
            elif isinstance(lbl, SquiggleWidget):
                lbl.color_active = QColor(text_main)
                lbl.color_inactive = QColor(text_muted)
        
        self._update_highlight()
        
    def set_alignment(self, align_str: str):
        if align_str == "Left": self.alignment = Qt.AlignmentFlag.AlignLeft
        elif align_str == "Right": self.alignment = Qt.AlignmentFlag.AlignRight
        else: self.alignment = Qt.AlignmentFlag.AlignCenter
        for label in self.line_labels:
            label.setAlignment(self.alignment | Qt.AlignmentFlag.AlignVCenter)
        self._update_highlight() # Force redraw with new border positions
            
    def set_lyrics(self, result: LyricsResult):
        self.current_lyrics = result
        self.current_active_idx = -1
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.line_labels.clear()
        self.rendered_lines = []
        
        if result and (result.has_line_sync or result.has_word_sync):
            self.content_layout.setContentsMargins(30, 200, 30, 200) 
            self._render_synced(result.synced_lines)
        elif result and result.plain_text:
            self.content_layout.setContentsMargins(30, 40, 30, 40)
            self._render_plain(result.plain_text)
        
        else:
            lbl = QLabel("[ empty buffer ]")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {self.color_inactive}; font-size: {self.font_size}px; font-family: monospace; opacity: 0.5;")
            self.content_layout.addWidget(lbl)
            
        # Cache timestamps for O(log N) binary search
        self.lyric_times = [l.start_time for l in self.rendered_lines]

    def set_error(self, message: str):
        self.current_lyrics = None
        self.current_active_idx = -1
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.line_labels.clear()
        self.rendered_lines = []
        
        lbl = QLabel(f"[ {message} ]")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color: #ff5555; font-size: {self.font_size}px; font-family: monospace; opacity: 0.8;")
        self.content_layout.addWidget(lbl)

    def set_offset(self, offset: float):
        self.lyric_offset = offset

    def set_glow(self, val: int):
        self.glow_intensity = val
        self._update_highlight()

    def _render_synced(self, lines: List[LyricLine]):
        self.rendered_lines = []
        for i in range(len(lines)):
            line = lines[i]
            self.rendered_lines.append(line)
            if i < len(lines) - 1:
                next_line = lines[i+1]
                gap = next_line.start_time - line.start_time
                if gap > 7.0:
                    # Insert squiggle 3.5 seconds before next line starts
                    # but also at least 3.5 seconds after current line starts
                    squiggle_time = max(line.start_time + 3.5, next_line.start_time - 3.5)
                    self.rendered_lines.append(LyricLine(text="...", start_time=squiggle_time))
                    # Cap current line end_time so it doesn't overlap with squiggle
                    line.end_time = squiggle_time
        
        for line in self.rendered_lines:
            main_text = (line.text or "...").strip()
            rom_text = line.romanized_text
            
            if main_text == "...":
                lbl = SquiggleWidget()
                lbl.color_active = QColor(self.color_active)
                lbl.color_inactive = QColor(self.color_inactive)
            else:
                lbl = LyricLabel(main_text, self, self.font_size, self.color_active, self.color_inactive)
                if rom_text:
                    html = f"<div>{main_text}</div><div style='font-size: {self.font_size-4}px; opacity: 0.5;'>↳ {rom_text}</div>"
                    lbl.setText(html)
                
            lbl.setAlignment(self.alignment | Qt.AlignmentFlag.AlignVCenter)
            lbl.setWordWrap(True)
            
            # Left padding for non-active lines (space for left border when active)
            lbl.setStyleSheet(f"color: {self.color_inactive}; font-size: {self.font_size}px; font-family: monospace; padding-left: 10px; background: transparent;")
            
            if rom_text:
                html = f"<div>{main_text}</div><div style='font-size: {self.font_size-4}px; opacity: 0.5;'>↳ {rom_text}</div>"
                lbl.setText(html)
            else:
                lbl.setText(main_text)
                
            from PyQt6.QtWidgets import QGraphicsDropShadowEffect
            effect = QGraphicsDropShadowEffect(lbl)
            effect.setBlurRadius(15)
            effect.setOffset(0, 2)
            effect.setColor(QColor(0, 0, 0, 240))
            lbl.setGraphicsEffect(effect)
                
            self.content_layout.addWidget(lbl)
            self.line_labels.append(lbl)

    def _render_plain(self, text: str):
        lines = text.splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                self.content_layout.addSpacing(15)
                continue
            
            lbl = LyricLabel(line, self, self.font_size, self.color_active, self.color_inactive)
            lbl.set_active(True)
            lbl.setAlignment(self.alignment | Qt.AlignmentFlag.AlignVCenter)
            
            from PyQt6.QtWidgets import QGraphicsDropShadowEffect
            effect = QGraphicsDropShadowEffect(lbl)
            effect.setBlurRadius(15)
            effect.setOffset(0, 2)
            effect.setColor(QColor(0, 0, 0, 240))
            lbl.setGraphicsEffect(effect)
            self.content_layout.addWidget(lbl)
            self.line_labels.append(lbl)
            
        # Add some extra space at bottom for scrolling
        self.content_layout.addSpacing(120)

    def update_position(self, pos_sec: float):
        pos_sec += self.lyric_offset
        if not self.rendered_lines: return
        
        # Binary search: O(log N) - using cached timestamps
        idx = bisect.bisect_right(self.lyric_times, pos_sec) - 1
        active_idx = max(0, idx) if idx >= 0 else -1
                
        if active_idx != self.current_active_idx:
            prev_idx = self.current_active_idx
            self.current_active_idx = active_idx
            
            # Only update the labels that changed state
            self._update_highlight_pair(prev_idx, active_idx)
            
            if active_idx >= 0 and active_idx < len(self.line_labels):
                lbl = self.line_labels[active_idx]
                self.scroll_area.smooth_scroll_to(lbl.pos().y() + (lbl.height() // 2))
            else:
                self.scroll_area.smooth_scroll_to(0)
            
            # Reset word sync tracking
            self.last_word_idx = -1
        
        # Word-by-word update: only if there are words and the line is active
        if active_idx >= 0 and active_idx < len(self.rendered_lines):
            line = self.rendered_lines[active_idx]
            if line.words:
                self._update_word_highlight(active_idx, pos_sec, line)

    def _update_word_highlight(self, idx: int, pos_sec: float, line: LyricLine):
        # find current active word index
        word_idx = -1
        for i, word in enumerate(line.words):
            if pos_sec >= word.start_time and pos_sec < word.end_time:
                word_idx = i
                break
            elif pos_sec >= word.end_time:
                word_idx = i # treat past words as possible active matches if none current
        
        # Only rebuild HTML if the active word has changed
        if word_idx == self.last_word_idx:
            return
        self.last_word_idx = word_idx
        
        lbl = self.line_labels[idx]
        text_parts = []
        for i, word in enumerate(line.words):
            if i == word_idx and pos_sec >= word.start_time and pos_sec < word.end_time:
                text_parts.append(f"<b style='color: {self.color_accent};'>{word.text}</b>")
            elif i <= word_idx:
                text_parts.append(f"<span style='color: {self.color_active};'>{word.text}</span>")
            else:
                text_parts.append(f"<span style='color: {self.color_inactive};'>{word.text}</span>")
        
        html = f"<div>{' '.join(text_parts)}</div>"
        if line.romanized_text:
             html += f"<div style='font-size: {self.font_size-4}px; opacity: 0.5;'>↳ {line.romanized_text}</div>"
        
        lbl.setText(html)

    def _update_highlight_pair(self, old_idx: int, new_idx: int):
        # Update only affected labels to save CPU
        targets = set()
        if old_idx >= 0: targets.add(old_idx)
        if new_idx >= 0: targets.add(new_idx)
        
        for idx in targets:
            if idx < len(self.line_labels):
                self._update_single_label(idx, idx == new_idx)

    def _update_highlight(self):
        for i in range(len(self.line_labels)):
            self._update_single_label(i, i == self.current_active_idx)

    def _update_single_label(self, i: int, is_active: bool):
        lbl = self.line_labels[i]
        
        if isinstance(lbl, LyricLabel):
            lbl.set_active(is_active)
            
        if isinstance(lbl, SquiggleWidget):
            lbl.set_main_opacity(1.0 if is_active else 0.0, highlighted=is_active)
            if not is_active: return

        eff = lbl.graphicsEffect()
        if is_active and eff and self.glow_intensity > 0:
            c = QColor(self.color_accent)
            c.setAlpha(min(255, int(self.glow_intensity * 3.5))) 
            eff.setColor(c)
            eff.setBlurRadius(int(self.glow_intensity * 0.6) + 10)
        elif eff:
            eff.setColor(QColor(0, 0, 0, 240))
            eff.setBlurRadius(15)
