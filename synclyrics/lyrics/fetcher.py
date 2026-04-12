import requests
from PyQt6.QtCore import QThread, pyqtSignal
from dataclasses import dataclass
from typing import Optional
from .parser import LrcParser, LyricsResult
from .romanizer import Romanizer

@dataclass
class FetchRequest:
    artist: str
    title: str
    album: str = ""
    duration: float = 0.0
    romanize: bool = True

class LyricsFetcher(QThread):
    lyrics_ready = pyqtSignal(object, FetchRequest) # (LyricsResult, original_request)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, request: FetchRequest):
        super().__init__()
        self.request = request
        
    def run(self):
        try:
            # 1. Try LRCLIB direct get
            result = self._fetch_lrclib_get()
            if result:
                self._romanize_if_needed(result)
                self.lyrics_ready.emit(result, self.request)
                return
                
            # 2. Try LRCLIB search fallback
            result = self._fetch_lrclib_search()
            if result:
                self._romanize_if_needed(result)
                self.lyrics_ready.emit(result, self.request)
                return
                
            # 3. Try NetEase Music (Backup)
            result = self._fetch_netease()
            if result:
                self._romanize_if_needed(result)
                self.lyrics_ready.emit(result, self.request)
                return
                
            # 4. Try lyrics.ovh (Last resort for plain lyrics)
            result = self._fetch_ovh()
            if result:
                self._romanize_if_needed(result)
                self.lyrics_ready.emit(result, self.request)
                return
                
            self.lyrics_ready.emit(LyricsResult(plain_text="No lyrics found"), self.request)
            
        except Exception as e:
            self.error_occurred.emit(str(e))
            
    def _fetch_lrclib_get(self) -> Optional[LyricsResult]:
        url = "https://lrclib.net/api/get"
        params = {
            "track_name": self.request.title,
            "artist_name": self.request.artist
        }
        if self.request.album:
            params["album_name"] = self.request.album
        if self.request.duration > 0:
            params["duration"] = int(self.request.duration)
            
        headers = {"User-Agent": "SyncLyrics v1.1.0"}
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return LrcParser.parse(
                    plain_lyrics=data.get("plainLyrics", ""),
                    synced_lyrics=data.get("syncedLyrics", "")
                )
        except requests.exceptions.RequestException:
            pass
        return None
        
    def _fetch_lrclib_search(self) -> Optional[LyricsResult]:
        url = "https://lrclib.net/api/search"
        params = {
            "track_name": self.request.title,
            "artist_name": self.request.artist
        }
        
        headers = {"User-Agent": "SyncLyrics v1.1.0"}
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
        except requests.exceptions.RequestException:
            return None
        
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                best_match = data[0]
                return LrcParser.parse(
                    plain_lyrics=best_match.get("plainLyrics", ""),
                    synced_lyrics=best_match.get("syncedLyrics", "")
                )
        return None
        
    def _fetch_ovh(self) -> Optional[LyricsResult]:
        url = f"https://api.lyrics.ovh/v1/{self.request.artist}/{self.request.title}"
        try:
            resp = requests.get(url, timeout=7)
            if resp.status_code == 200:
                data = resp.json()
                return LrcParser.parse(plain_lyrics=data.get("lyrics", ""))
        except requests.exceptions.RequestException:
            pass
        return None

    def _fetch_netease(self) -> Optional[LyricsResult]:
        """Backup provider using NetEase Music API."""
        try:
            search_url = "https://music.cyrvoid.com/search" # Public NetEase proxy
            params = {"keywords": f"{self.request.artist} {self.request.title}", "limit": 1}
            search_resp = requests.get(search_url, params=params, timeout=10)
            if search_resp.status_code == 200:
                data = search_resp.json()
                songs = data.get("result", {}).get("songs", [])
                if songs:
                    song_id = songs[0]["id"]
                    lyric_url = f"https://music.cyrvoid.com/lyric?id={song_id}"
                    lyric_resp = requests.get(lyric_url, timeout=10)
                    if lyric_resp.status_code == 200:
                        ld = lyric_resp.json()
                        return LrcParser.parse(
                            plain_lyrics=ld.get("lrc", {}).get("lyric", ""),
                            synced_lyrics=ld.get("lrc", {}).get("lyric", "")
                        )
        except Exception:
            pass
        return None

    def _romanize_if_needed(self, result: LyricsResult):
        if not self.request.romanize:
            return
        if result and result.synced_lines:
            for line in result.synced_lines:
                rom = Romanizer.romanize(line.text)
                if rom and rom.lower() != line.text.lower():
                    line.romanized_text = rom
