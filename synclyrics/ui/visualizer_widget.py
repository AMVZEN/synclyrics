import numpy as np
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QLinearGradient, QBrush, QPen, QPolygonF
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, pyqtProperty, QPropertyAnimation, QEasingCurve
import threading
import subprocess
import time

class VisualizerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.num_points = 80 # Reduced from 120 for performance
        self.heights = np.zeros(self.num_points)
        self.target_heights = np.zeros(self.num_points)
        
        self.audio_thread = None
        self.running = False
        
        self.color_primary = QColor("#bb9af7")
        self.color_secondary = QColor("#7aa2f7")
        self.color_bg = QColor("#1a1b26")
        self.enabled = True
        self.vis_type = "fluid-wave"
        self.vignette_intensity = 0 
        
        self.idle_phase = 0.0
        self._opacity = 1.0 
        self._waves_opacity = 1.0 
        
        # Performance Cache
        self._cached_bg_brush = QBrush(self.color_bg)
        self._cached_grad = None
        self._cached_pens = {}
        self._last_w, self._last_h = 0, 0
        
        # FPS Control
        self.fps_timer = QTimer(self)
        self.fps_timer.timeout.connect(self._on_tick)
        self.fps_timer.start(16) # ~60 FPS
        
        self.start_audio_capture()

    def set_colors(self, primary: str, secondary: str):
        self.color_primary = QColor(primary)
        self.color_secondary = QColor(secondary)
        self._cached_grad = None # Force rebuild
        
    def set_bg_color(self, bg_hex: str):
        self.color_bg = QColor(bg_hex)
        self._cached_bg_brush = QBrush(self.color_bg)

    @pyqtProperty(float)
    def opacity(self): return self._opacity
    @opacity.setter
    def opacity(self, val):
        self._opacity = val
        # No immediate update() - wait for tick

    @pyqtProperty(float)
    def waves_opacity(self): return self._waves_opacity
    @waves_opacity.setter
    def waves_opacity(self, val):
        self._waves_opacity = val

    def set_enabled(self, val: bool):
        self.enabled = val
        self.update()

    def set_type(self, vtype: str):
        self.vis_type = vtype
        self.update()

    def set_vignette(self, val: int):
        self.vignette_intensity = val
        self.update()

    def _on_tick(self):
        """Standardized update interval for smooth motion."""
        if not self.enabled or self._opacity < 0.01:
            return
            
        # Physics / Smoothing
        self.heights += (self.target_heights - self.heights) * 0.15
        self.idle_phase += 0.02
        
        if self.isVisible():
            self.update()

    def start_audio_capture(self):
        if self.running: return
        self.running = True
        self.audio_thread = threading.Thread(target=self._audio_capture_loop, daemon=True)
        self.audio_thread.start()
        
    def stop_audio_capture(self):
        self.running = False
        if self.audio_thread:
            self.audio_thread.join()

    def _audio_capture_loop(self):
        CHUNK = 512
        cmd2 = ["parec", "--format=float32le", "--rate=44100", "--channels=1", "--latency-msec=10", "-d", "@DEFAULT_SINK@.monitor"]
        
        process = None
        while self.running:
            try:
                process = subprocess.Popen(cmd2, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                max_val = 60.0
                
                while self.running and process.poll() is None:
                    data = process.stdout.read(CHUNK * 4) 
                    if not data: break
                        
                    if not self.enabled:
                        time.sleep(0.1)
                        continue
                        
                    audio_data = np.frombuffer(data, dtype=np.float32)
                    fft_data = np.abs(np.fft.rfft(audio_data))
                    
                    fft_len = len(fft_data)
                    max_freq_idx = min(fft_len, int(fft_len * 0.4)) 
                    indices = np.logspace(np.log10(1), np.log10(max_freq_idx), num=self.num_points, dtype=int)
                    
                    bins = []
                    for i in range(len(indices)-1):
                        bins.append(np.mean(fft_data[indices[i]:max(indices[i]+1, indices[i+1])]))
                    while len(bins) < self.num_points: bins.append(0.0)
                    bins = np.array(bins)
                    
                    with np.errstate(divide='ignore'):
                        y = 10 * np.log10(bins + 1e-6) 
                        
                    y[np.isinf(y)] = 0
                    y = np.clip(y, 0, max_val)
                    if np.max(y) > 0 and np.max(y) < max_val * 0.5:
                         y = y * 1.5
                         
                    half = self.num_points // 2
                    sub_y = y[:half]
                    scaled = (sub_y / max_val) 
                    
                    target = np.zeros(self.num_points)
                    target[:half] = scaled[::-1]
                    target[half:] = scaled
                    self.target_heights = target
                    
            except: pass
            if process: process.kill()
            if self.running: time.sleep(1.0)
                
        if process: process.kill()

    def paintEvent(self, event):
        if self._opacity <= 0.001: return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        w, h = self.width(), self.height()
        if w != self._last_w or h != self._last_h:
            self._cached_grad = None # Signal resize
            self._last_w, self._last_h = w, h
        
        # BG
        painter.setOpacity(self._opacity)
        painter.fillRect(0, 0, w, h, self._cached_bg_brush)
        
        # Waves Opacity
        final_waves_opacity = self._waves_opacity * self._opacity
        painter.setOpacity(final_waves_opacity)
        
        # Vignette (Only rebuild if needed)
        if self.vignette_intensity > 0:
            vig_alpha = int(self.vignette_intensity * 2.1)
            vg = QLinearGradient(0, 0, 0, h)
            vg.setColorAt(0, QColor(0,0,0, int(vig_alpha * 0.6)))
            vg.setColorAt(0.3, QColor(0,0,0,0))
            vg.setColorAt(0.7, QColor(0,0,0,0))
            vg.setColorAt(1, QColor(0,0,0, vig_alpha))
            painter.fillRect(0, 0, w, h, vg)
        
        if not self.enabled: return
            
        combined = np.maximum(self.heights + (np.sin(np.linspace(0, np.pi * 3, self.num_points) + self.idle_phase) * 0.05), 0.0)
        max_amp = h * 0.4 # Reduced from 0.5 to stay lower
        base_h_val = h * 0.8 # Lowered base line
        
        if self.vis_type == "fluid-wave":
            step = (w + 40) / (self.num_points - 1)
            for layer in range(3):
                path = QPainterPath()
                path.moveTo(-20, h + 20)
                phase = self.idle_phase + (layer * 2.0)
                amp = 1.0 - (layer * 0.2)
                
                cmb = np.maximum((self.heights * amp) + np.sin(np.linspace(0, np.pi * 3, self.num_points) + phase) * (0.05 + layer*0.02), 0.0)
                
                path.lineTo(-20, base_h_val - (cmb[0] * max_amp))
                for i in range(self.num_points - 1):
                    x1 = -20 + (i * step)
                    y1 = base_h_val - (cmb[i] * max_amp)
                    x2 = -20 + ((i+1) * step)
                    y2 = base_h_val - (cmb[i+1] * max_amp)
                    cx = (x1 + x2) / 2
                    path.cubicTo(cx, y1, cx, y2, x2, y2)
                    
                path.lineTo(w + 20, h + 20)
                path.closeSubpath()
                
                grad = QLinearGradient(0, 0, 0, h)
                c1 = QColor(self.color_primary)
                c1.setAlpha([45, 30, 20][layer])
                grad.setColorAt(0, c1)
                grad.setColorAt(1, Qt.GlobalColor.transparent)
                painter.fillPath(path, grad)
                
        elif self.vis_type == "classic-bars":
            bar_w = w / self.num_points
            gap = 2
            painter.setOpacity(final_waves_opacity * 0.6) # Lower opacity for bars
            for i in range(self.num_points):
                h_val = combined[i] * max_amp * 1.8
                rect = QRectF(i * bar_w + gap, h - h_val - 20, bar_w - gap*2, h_val)
                
                grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
                grad.setColorAt(0, self.color_primary)
                grad.setColorAt(1, self.color_secondary)
                painter.setBrush(grad)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(rect, 3, 3)
                
        elif self.vis_type == "neon-strings":
            painter.setOpacity(final_waves_opacity * 0.5)
            step = w / (self.num_points - 1)
            base_y = h * 0.6
            for layer in range(3):
                path = QPainterPath()
                phase = self.idle_phase + (layer * 1.5)
                amp = 1.0 - (layer * 0.2)
                cmb = (self.heights * amp) + np.sin(np.linspace(0, np.pi * 2, self.num_points) + phase) * 0.04
                
                pts = [QPointF(i*step, base_y - (cmb[i] * max_amp)) for i in range(self.num_points)]
                path.moveTo(pts[0])
                for i in range(len(pts)-1):
                    cx = (pts[i].x() + pts[i+1].x()) / 2
                    path.cubicTo(cx, pts[i].y(), cx, pts[i+1].y(), pts[i+1].x(), pts[i+1].y())
                
                pen = QPen(self.color_primary if layer % 2 == 0 else self.color_secondary, 2)
                painter.setPen(pen)
                painter.drawPath(path)
                
        elif self.vis_type == "cyber-bars":
            bar_w = w / self.num_points
            painter.setOpacity(final_waves_opacity * 0.5)
            for i in range(self.num_points):
                h_val = combined[i] * max_amp * 1.6
                rect = QRectF(i * bar_w, h - h_val - 40, bar_w - 2, h_val)
                # Bottom part
                painter.fillRect(rect, self.color_secondary)
                # Top accent
                painter.fillRect(QRectF(i * bar_w, h - h_val - 44, bar_w - 2, 3), self.color_primary)
                
        elif self.vis_type == "digital-dots":
            dot_size = 6
            step = w / (self.num_points - 1)
            painter.setOpacity(final_waves_opacity * 0.7)
            for i in range(self.num_points):
                h_val = combined[i] * max_amp * 1.5
                center_y = h - h_val - 50
                painter.setBrush(self.color_primary)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(i * step, center_y), dot_size/2, dot_size/2)
                # Subtle vertical line connecting
                painter.setOpacity(final_waves_opacity * 0.2)
                painter.fillRect(QRectF(i * step - 0.5, center_y + 10, 1, h - center_y), self.color_secondary)
                painter.setOpacity(final_waves_opacity * 0.7)
                
        elif self.vis_type == "radial-sunburst":
            painter.setOpacity(final_waves_opacity * 0.35)
            center = QPointF(w/2, h/2)
            inner_radius = 60
            outer_base = 120
            
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            for i in range(self.num_points):
                angle = (i / self.num_points) * 360
                # Wave effect: use heights
                val = self.heights[i]
                length = outer_base + (val * 120)
                
                rad = np.radians(angle - 90) # Start from top
                start_p = center + QPointF(np.cos(rad) * inner_radius, np.sin(rad) * inner_radius)
                end_p = center + QPointF(np.cos(rad) * length, np.sin(rad) * length)
                
                pen = QPen(self.color_primary if i % 2 == 0 else self.color_secondary, 2)
                painter.setPen(pen)
                painter.drawLine(start_p, end_p)
                
                # Add a "tip" dot for premium look
                if val > 0.1:
                    painter.setBrush(self.color_primary)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(end_p, 2, 2)

