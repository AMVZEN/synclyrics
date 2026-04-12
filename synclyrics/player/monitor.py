import subprocess
import json
import time
from PyQt6.QtCore import QThread, pyqtSignal

class PlayerMonitor(QThread):
    """Polls playerctl for playback status, metadata and position in a background thread."""
    
    # Emits dict with keys: artist, title, album, artUrl, length, player_name
    track_changed = pyqtSignal(dict)
    # Emits current position in seconds
    position_updated = pyqtSignal(float)
    # Playing / Paused / Stopped
    state_changed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = False
        
        self.current_artist = None
        self.current_title = None
        self.current_state = "Stopped"
        self.last_switch_time = 0
        self.grace_period_sec = 1.0 # Ignore wild position jumps right after song switch
        self.active_player = None
        self.last_reported_pos = -1.0
        self.last_report_time = time.time()
        self.last_info = {}
        
    def run(self):
        self.running = True
        last_poll_time = 0.0
        while self.running:
            now = time.time()
            if now - last_poll_time > 0.25: # Check DBus 4 times per second
                self._poll()
                last_poll_time = time.time()
            
            # Dead-reckoning: Interpolate the position flawlessly at ~30 FPS
            if self.current_state == "Playing" and self.last_reported_pos >= 0.0:
                elapsed = time.time() - self.last_report_time
                self.position_updated.emit(self.last_reported_pos + elapsed)
                
            time.sleep(0.03)
            
    def stop(self):
        self.running = False
        self.wait()
        
    def get_active_player(self) -> str:
        try:
             # Gets the player that most recently had a valid state
             out = subprocess.check_output(
                 ["playerctl", "-l"], 
                 stderr=subprocess.DEVNULL,
                 text=True
             )
             players = out.strip().split('\n')
             return players[0] if players and players[0] else ""
        except subprocess.SubprocessError:
             return ""

    def _poll(self):
        try:
            player_arg = []
            
            # Combined metadata + position call
            fmt = '{"artist":"{{artist}}", "title":"{{title}}", "album":"{{album}}", "artUrl":"{{mpris:artUrl}}", "length":"{{mpris:length}}", "status":"{{status}}", "position":"{{position}}"}'
            meta_out = subprocess.check_output(["playerctl", "metadata", "--format", fmt], stderr=subprocess.DEVNULL, text=True).strip()
            if not meta_out:
                self._handle_stopped()
                return
                
            try:
                 meta = json.loads(meta_out)
            except json.JSONDecodeError:
                 return # Transient error
            
            status = meta.get("status", "Stopped")
            artist = meta.get("artist", "").strip()
            title = meta.get("title", "").strip()
            length_us = meta.get("length", 0)
            
            try:
                length_sec = float(length_us) / 1000000.0 if length_us else 0
            except ValueError:
                length_sec = 0

            # State Changed
            if status != self.current_state:
                self.current_state = status
                self.state_changed.emit(status)
                
            # Track Changed
            if artist != self.current_artist or title != self.current_title:
                self.current_artist = artist
                self.current_title = title
                self.last_switch_time = time.time()
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
                try:
                    p_val = float(meta.get("position", 0))
                    position = p_val / 1000000.0 if p_val > 100000 else p_val
                    self.last_reported_pos = position
                    self.last_report_time = time.time()
                except:
                    pass

        except subprocess.SubprocessError:
             self._handle_stopped()
             
    def _handle_stopped(self):
         if self.current_state != "Stopped":
             self.current_state = "Stopped"
             self.state_changed.emit("Stopped")
         if self.current_title is None and self.current_artist is None:
             pass # Already stopped
         else:
             self.current_title = None
             self.current_artist = None
             self.last_reported_pos = -1.0
             self.last_info = {}
             # Emit empty to clear UI
             self.track_changed.emit({})
