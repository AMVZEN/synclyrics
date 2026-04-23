import os
import json
import numpy as np
import threading
import subprocess
import time
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal, pyqtProperty

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineSettings
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False


class MilkdropWidget(QWidget):
    """QWebEngineView wrapper for Butterchurn (MilkDrop) visualizer."""
    presets_loaded = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._opacity = 1.0
        self._blurred = False
        self._running = False
        self._audio_thread = None
        self._random_cycle = True
        self._cycle_interval = 15
        self._current_preset = ""
        self._page_ready = False

        self._freq_data = np.zeros(512, dtype=np.uint8)
        self._time_data = np.full(1024, 128, dtype=np.uint8)
        self._preset_names = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if not HAS_WEBENGINE:
            return

        self.web_view = QWebEngineView()
        self.web_view.setStyleSheet("background: black;")
        s = self.web_view.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        layout.addWidget(self.web_view)

        self._data_timer = QTimer(self)
        self._data_timer.timeout.connect(self._send_audio_data)

        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "milkdrop.html"))
        self.web_view.load(QUrl.fromLocalFile(html_path))
        self.web_view.loadFinished.connect(self._on_page_loaded)

    def _on_page_loaded(self, ok):
        if not ok:
            return
        self._page_ready = True
        # Delayed preset fetch — give butterchurn time to initialize
        QTimer.singleShot(2000, self._fetch_presets)

    def _fetch_presets(self):
        if not self._page_ready:
            return
        self.web_view.page().runJavaScript(
            "getPresetNames()",
            lambda result: self._handle_presets(result)
        )

    def _handle_presets(self, names):
        self._preset_names = names or []
        self.presets_loaded.emit(self._preset_names)
        # Now start everything
        self.start_audio()
        if self._random_cycle:
            self._apply_random_cycle(True)
        if self._current_preset:
            self.load_preset(self._current_preset)
        if self._blurred:
            self._run_js(f"setBlur(true)")

    def get_preset_names(self):
        return list(self._preset_names)

    # --- Audio Capture ---
    def start_audio(self):
        if self._running:
            return
        self._running = True
        self._audio_thread = threading.Thread(target=self._audio_loop, daemon=True)
        self._audio_thread.start()
        self._data_timer.start(33)  # ~30fps

    def stop_audio(self):
        self._running = False
        self._data_timer.stop()
        if self._audio_thread:
            self._audio_thread.join(timeout=2)

    def _audio_loop(self):
        CHUNK = 1024
        cmd = ["parec", "--format=float32le", "--rate=44100", "--channels=1",
               "--latency-msec=10", "-d", "@DEFAULT_SINK@.monitor"]
        process = None
        while self._running:
            try:
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                while self._running and process.poll() is None:
                    data = process.stdout.read(CHUNK * 4)
                    if not data:
                        break
                    audio = np.frombuffer(data, dtype=np.float32)

                    # Time domain → uint8 (centered at 128)
                    td = np.clip((audio * 128 + 128), 0, 255).astype(np.uint8)
                    if len(td) < 1024:
                        td = np.pad(td, (0, 1024 - len(td)), constant_values=128)
                    self._time_data = td[:1024]

                    # FFT → frequency byte data
                    fft = np.abs(np.fft.rfft(audio))
                    with np.errstate(divide='ignore'):
                        db = 20 * np.log10(fft + 1e-10)
                    db = np.clip(db, -100, -30)
                    fb = ((db + 100) / 70 * 255).astype(np.uint8)
                    if len(fb) > 512:
                        idx = np.linspace(0, len(fb) - 1, 512, dtype=int)
                        fb = fb[idx]
                    elif len(fb) < 512:
                        fb = np.pad(fb, (0, 512 - len(fb)))
                    self._freq_data = fb
            except Exception:
                pass
            if process:
                process.kill()
            if self._running:
                time.sleep(1.0)
        if process:
            try: process.kill()
            except: pass

    def _send_audio_data(self):
        if not self._page_ready:
            return
        f = ','.join(map(str, self._freq_data.tolist()))
        t = ','.join(map(str, self._time_data[::2].tolist()))  # Downsample time to 512
        self._run_js(f"setAudioData([{f}],[{t}])")

    # --- Controls ---
    def set_blur(self, blurred: bool):
        self._blurred = blurred
        if self._page_ready:
            self._run_js(f"setBlur({'true' if blurred else 'false'})")

    def load_preset(self, name: str, blend: float = 2.0):
        self._current_preset = name
        if self._page_ready:
            self._run_js(f"loadPreset({json.dumps(name)},{blend})")

    def set_random_cycle(self, enabled: bool, interval_sec: int = 15):
        self._random_cycle = enabled
        self._cycle_interval = interval_sec
        if self._page_ready:
            self._apply_random_cycle(enabled)

    def _apply_random_cycle(self, enabled):
        if enabled:
            self._run_js(f"startRandomCycle({self._cycle_interval * 1000})")
        else:
            self._run_js("stopRandomCycle()")

    @pyqtProperty(float)
    def opacity(self):
        return self._opacity

    @opacity.setter
    def opacity(self, val):
        self._opacity = val

    def _run_js(self, code):
        if HAS_WEBENGINE and hasattr(self, 'web_view') and self._page_ready:
            try:
                self.web_view.page().runJavaScript(code)
            except Exception:
                pass

    def cleanup(self):
        self.stop_audio()
        if HAS_WEBENGINE and hasattr(self, 'web_view'):
            self._run_js("stopRandomCycle()")
