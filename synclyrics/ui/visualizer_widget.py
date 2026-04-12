import numpy as np
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QLinearGradient, QBrush, QPen
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, pyqtProperty, QPropertyAnimation, QEasingCurve
import threading
import subprocess
import time

class VisualizerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.num_points = 120 
        self.heights = np.zeros(self.num_points)
        self.target_heights = np.zeros(self.num_points)
        
        self.audio_thread = None
        self.running = False
        
        self.color_primary = QColor("#bb9af7")
        self.color_secondary = QColor("#7aa2f7")
        self.color_bg = QColor("#1a1b26")
        self.enabled = True
        self.vis_type = "fluid-wave"
        self.vignette_intensity = 0 # 0-100
        
        self.idle_phase = 0.0
        self._opacity = 1.0 # Background & Overall opacity
        self._waves_opacity = 1.0 # Only the moving waves
        
        self.start_audio_capture()

    def set_colors(self, primary: str, secondary: str):
        self.color_primary = QColor(primary)
        self.color_secondary = QColor(secondary)
        
    def set_bg_color(self, bg_hex: str):
        self.color_bg = QColor(bg_hex)

    @pyqtProperty(float)
    def opacity(self):
        return self._opacity

    @opacity.setter
    def opacity(self, val):
        self._opacity = val
        self.update()

    @pyqtProperty(float)
    def waves_opacity(self): return self._waves_opacity
    @waves_opacity.setter
    def waves_opacity(self, val):
        self._waves_opacity = val
        self.update()

    def set_enabled(self, val: bool):
        self.enabled = val

    def set_type(self, vtype: str):
        self.vis_type = vtype

    def set_vignette(self, val: int):
        self.vignette_intensity = val

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
        cmd = ["parec", "--format=float32le", "--rate=44100", "--channels=1", "--latency-msec=10", "--monitor-stream"]
        cmd2 = ["parec", "--format=float32le", "--rate=44100", "--channels=1", "--latency-msec=10", "-d", "@DEFAULT_SINK@.monitor"]
        
        process = None
        
        while self.running:
            try:
                process = subprocess.Popen(cmd2, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                max_val = 60.0
                
                while self.running and process.poll() is None:
                    data = process.stdout.read(CHUNK * 4) 
                    if not data:
                        break
                        
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
                    # Trigger update from UI thread only if visible
                    if self.isVisible() and self._opacity > 0.05:
                        QTimer.singleShot(0, self.update)
                    
            except Exception:
                pass
            
            if process:
                process.kill()
            if self.running:
                time.sleep(2.0)
                
        if process:
            process.kill()

    def paintEvent(self, event):
        if self._opacity <= 0.001: return
        
        painter = QPainter()
        if not painter.begin(self):
            return
            
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        w = self.width()
        h = self.height()
        
        # Draw background with main opacity
        painter.setOpacity(self._opacity)
        painter.fillRect(0, 0, w, h, self.color_bg)
        
        # Draw waves with waves_opacity
        painter.setOpacity(self._waves_opacity * self._opacity)
        
        # Premium Vignette
        if self.vignette_intensity > 0:
            # Much more aggressive alpha scaling
            vig_alpha = int(self.vignette_intensity * 2.2) 
            vignette = QLinearGradient(0, 0, 0, h)
            vignette.setColorAt(0, QColor(0,0,0, int(vig_alpha * 0.7)))
            vignette.setColorAt(0.3, QColor(0,0,0,0))
            vignette.setColorAt(0.7, QColor(0,0,0,0))
            vignette.setColorAt(1, QColor(0,0,0, vig_alpha))
            painter.fillRect(0, 0, w, h, vignette)
            
            side_alpha = int(vig_alpha * 0.8)
            side_vignette = QLinearGradient(0, 0, w, 0)
            side_vignette.setColorAt(0, QColor(0,0,0, side_alpha))
            side_vignette.setColorAt(0.2, QColor(0,0,0,0))
            side_vignette.setColorAt(0.8, QColor(0,0,0,0))
            side_vignette.setColorAt(1, QColor(0,0,0, side_alpha))
            painter.fillRect(0, 0, w, h, side_vignette)
        
        if not self.enabled: 
            return
            
        self.heights += (self.target_heights - self.heights) * 0.15
        self.idle_phase += 0.02
        
        combined = np.maximum(self.heights + (np.sin(np.linspace(0, np.pi * 3, self.num_points) + self.idle_phase) * 0.05), 0.0)
        max_amp = h * 0.5
        
        if self.vis_type == "fluid-wave":
            for layer in range(3):
                path = QPainterPath()
                path.moveTo(-20, h + 20)
                step = (w + 40) / (self.num_points - 1)
                phase = self.idle_phase + (layer * 2.0)
                amp = 1.0 - (layer * 0.2)
                
                c_heights = self.heights * amp
                idle_wave = np.sin(np.linspace(0, np.pi * 3, self.num_points) + phase) * (0.05 + layer*0.02)
                cmb = np.maximum(c_heights + idle_wave, 0.0)
                
                base_h = h * 0.7
                pts = [(-20 + (i * step), base_h - (cmb[i] * max_amp)) for i in range(self.num_points)]
                    
                path.lineTo(pts[0][0], pts[0][1])
                for i in range(self.num_points - 1):
                    x1, y1 = pts[i]
                    x2, y2 = pts[i+1]
                    cx = (x1 + x2) / 2
                    path.cubicTo(cx, y1, cx, y2, x2, y2)
                    
                path.lineTo(w + 20, h + 20)
                path.closeSubpath()
                
                grad = QLinearGradient(0, 0, 0, h)
                c1 = QColor(self.color_primary)
                c1.setAlpha([40, 25, 15][layer]) # Reduced from [80, 50, 30]
                grad.setColorAt(0, c1)
                grad.setColorAt(1, QColor(0,0,0,0))
                
                painter.setBrush(QBrush(grad))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawPath(path)
                
        elif self.vis_type == "classic-bars":
            painter.setPen(Qt.PenStyle.NoPen)
            grad = QLinearGradient(0, 0, 0, h)
            c1 = QColor(self.color_primary)
            c1.setAlpha(60)
            c2 = QColor(self.color_secondary)
            c2.setAlpha(20)
            grad.setColorAt(0, c1)
            grad.setColorAt(1, c2)
            painter.setBrush(QBrush(grad))
            
            bar_w = w / self.num_points
            for i in range(self.num_points):
                h_val = combined[i] * max_amp * 1.5
                rect = QRectF(i * bar_w, h - h_val, bar_w - 1, h_val)
                painter.fillRect(rect, grad)
                
        elif self.vis_type == "cyber-bars":
            bar_w = w / self.num_points
            for i in range(self.num_points):
                h_val = combined[i] * max_amp * 1.5
                x = (i * bar_w) + (bar_w/2)
                c_sec = QColor(self.color_secondary)
                c_sec.setAlpha(100)
                painter.setPen(QPen(c_sec, 2))
                painter.drawLine(int(x), int(h), int(x), int(h - h_val))
                painter.setPen(Qt.PenStyle.NoPen)
                c_prim = QColor(self.color_primary)
                c_prim.setAlpha(150)
                painter.setBrush(c_prim)
                painter.drawEllipse(QPointF(x, h - h_val), 3, 3)
                
        elif self.vis_type == "radial-sunburst":
            cx, cy = w/2, h/2
            bass = np.mean(combined[:10])
            base_r = min(w, h) * 0.15 + (bass * -60.0)
            if base_r < 10: base_r = 10
            
            painter.translate(cx, cy)
            
            painter.setPen(Qt.PenStyle.NoPen)
            c_bg = QColor(self.color_secondary)
            c_bg.setAlpha(20) # Reduced from 40
            painter.setBrush(c_bg)
            painter.drawEllipse(QPointF(0,0), base_r, base_r)
            
            c_line = QColor(self.color_primary)
            c_line.setAlpha(120)
            painter.setPen(QPen(c_line, 2))
            for i in range(self.num_points):
                ang = (i / self.num_points) * 2 * np.pi
                r_out = base_r + (combined[i] * max_amp * 0.8)
                x1, y1 = np.cos(ang)*base_r, np.sin(ang)*base_r
                x2, y2 = np.cos(ang)*r_out, np.sin(ang)*r_out
                painter.drawLine(QPointF(x1,y1), QPointF(x2,y2))
            painter.translate(-cx, -cy)

        elif self.vis_type == "neon-strings":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            from PyQt6.QtGui import QPolygonF
            for layer in range(3):
                pen = QPen(QColor(self.color_primary) if layer%2==0 else QColor(self.color_secondary))
                pen.setWidth(2)
                c = pen.color()
                c.setAlpha(80 - (layer*20)) # Reduced from 150 - (layer*40)
                pen.setColor(c)
                painter.setPen(pen)
                
                base_y = h/2 + (layer*10 - 10)
                step = w / (self.num_points - 1)
                
                pts = []
                for i in range(self.num_points):
                    x = i * step
                    y = base_y - (combined[i] * max_amp * (1.0 - layer*0.15)) * (np.sin(self.idle_phase + i + layer))
                    pts.append(QPointF(x, y))
                painter.drawPolyline(QPolygonF(pts))
                
        elif self.vis_type == "digital-dots":
            step_w = w / self.num_points
            dot_h = 8
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(self.color_primary))
            for i in range(0, self.num_points, 2):
                h_val = combined[i] * max_amp * 1.5
                num_dots = int(h_val / dot_h)
                x = i * step_w
                for d in range(0, num_dots, 2):
                    y = h - (d * dot_h) - dot_h
                    painter.drawRect(int(x), int(y), int(step_w*2 - 2), int(dot_h - 2))
