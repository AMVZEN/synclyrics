import subprocess
import json
import time
from PyQt6.QtCore import QThread, pyqtSignal

class PlayerMonitor(QThread):
    """Polls playerctl for playback status, metadata and position in a background thread."""
    
    track_changed = pyqtSignal(dict)
    position_updated = pyqtSignal(float)
    state_changed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = False
        
        self.current_artist = None
        self.current_title = None
        self.current_state = "Stopped"
        self.last_switch_time = 0
        self.grace_period_sec = 1.0 
        self.active_player = None
        self.last_reported_pos = -1.0
        self.last_report_time = time.time()
        self.last_info = {}
        
    def run(self):
        self.running = True
        last_poll_time = 0.0
        while self.running:
            now = time.time()
            # Poll at 4Hz (every 250ms)
            if now - last_poll_time > 0.25:
                self._poll()
                last_poll_time = time.time()
            
            # Dead-reckoning interpolation for smooth 60fps-like updates
            if self.current_state == "Playing" and self.last_reported_pos >= 0.0:
                elapsed = time.time() - self.last_report_time
                self.position_updated.emit(self.last_reported_pos + elapsed)
                
            # Sleep slightly more to reduce idle CPU (10ms is plenty for smooth interpolation)
            time.sleep(0.01)
            
    def stop(self):
        self.running = False
        self.wait()

    def _get_best_player(self) -> str:
        """Finds the most 'relevant' player to avoid background browser tabs."""
        try:
            out = subprocess.check_output(["playerctl", "-l"], stderr=subprocess.DEVNULL, text=True).strip()
            if not out: return ""
            players = out.split('\n')
            
            # 1. Prefer players currently "Playing"
            states = {}
            for p in players:
                try:
                    s = subprocess.check_output(["playerctl", "-p", p, "status"], stderr=subprocess.DEVNULL, text=True).strip()
                    states[p] = s
                except: states[p] = "Stopped"
            
            playing = [p for p, s in states.items() if s == "Playing"]
            if playing:
                # 2. Prefer dedicated apps over browsers
                dedicated = [p for p in playing if any(x in p.lower() for x in ["spotify", "vlc", "mpd", "audacious"])]
                return dedicated[0] if dedicated else playing[0]
            
            return players[0]
        except: return ""

    def _normalize_time(self, val) -> float:
        """Robustly converts playerctl output to seconds."""
        if not val: return 0.0
        try:
            f_val = float(val)
            # MPRIS Spec: position/length are in MICROSECONDS.
            # If value is massive (> 10,000,000), it's definitely microseconds.
            # If a song is e.g. 5 seconds, it's 5,000,000 us.
            # Heuristic: if > 1000, treat as microseconds. 
            # If < 1000, it might be raw seconds (some buggy players).
            if f_val > 5000: # 5ms in microseconds is 5000. 
                return f_val / 1000000.0
            return f_val
        except: return 0.0

    def _poll(self):
        try:
            # We don't specify -p to let playerctl pick the best one, 
            # or we could use _get_best_player if it gets stuck on the wrong one.
            fmt = '{"artist":"{{artist}}", "title":"{{title}}", "album":"{{album}}", "artUrl":"{{mpris:artUrl}}", "length":"{{mpris:length}}", "status":"{{status}}", "position":"{{position}}"}'
            
            # Optimization: Fetch metadata only for the 'active' player to avoid cross-talk
            cmd = ["playerctl", "metadata", "--format", fmt]
            meta_out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
            
            if not meta_out:
                self._handle_stopped()
                return
                
            try:
                 meta = json.loads(meta_out)
            except json.JSONDecodeError:
                 return
            
            status = meta.get("status", "Stopped")
            artist = meta.get("artist", "").strip()
            title = meta.get("title", "").strip()
            
            length_sec = self._normalize_time(meta.get("length"))

            # State Changed
            if status != self.current_state:
                self.current_state = status
                self.state_changed.emit(status)
                
            # Track Changed
            if artist != self.current_artist or title != self.current_title:
                self.current_artist = artist
                self.current_title = title
                self.last_reported_pos = -1.0
                
                track_info = {
                    "artist": artist,
                    "title": title,
                    "album": meta.get("album", ""),
                    "artUrl": meta.get("artUrl", ""),
                    "length": length_sec
                }
                self.last_info = track_info
                self.track_changed.emit(track_info)
                
            if status == "Playing":
                # Normalize position properly
                pos_raw = meta.get("position", 0)
                self.last_reported_pos = self._normalize_time(pos_raw)
                self.last_report_time = time.time()

        except subprocess.SubprocessError:
             self._handle_stopped()
             
    def _handle_stopped(self):
        if self.current_state != "Stopped":
            self.current_state = "Stopped"
            self.state_changed.emit("Stopped")
        if self.current_title is not None:
            self.current_title = None
            self.current_artist = None
            self.last_reported_pos = -1.0
            self.last_info = {}
            self.track_changed.emit({})

