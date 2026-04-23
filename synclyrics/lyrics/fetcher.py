import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt6.QtCore import QThread, pyqtSignal
from dataclasses import dataclass
from typing import Optional, List
from .parser import LrcParser, LyricsResult
from .romanizer import Romanizer

# Persistent session with connection pooling for faster repeated requests
_session = requests.Session()
_session.headers.update({"User-Agent": "SyncLyrics v1.2.0"})
# Pre-warm connection pool
adapter = requests.adapters.HTTPAdapter(
    pool_connections=4, pool_maxsize=8, max_retries=1
)
_session.mount("https://", adapter)
_session.mount("http://", adapter)


@dataclass
class FetchRequest:
    artist: str
    title: str
    album: str = ""
    duration: float = 0.0
    romanize: bool = True


class LyricsFetcher(QThread):
    """Fetches lyrics from multiple providers concurrently.
    
    Emits ALL results found so the UI can let the user cycle through them.
    """
    lyrics_ready = pyqtSignal(object, object, object)  # (List[LyricsResult], int, FetchRequest)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, request: FetchRequest):
        super().__init__()
        self.request = request
        
    def run(self):
        try:
            all_results: List[LyricsResult] = []
            
            # Fire all providers concurrently for speed
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = {
                    pool.submit(self._fetch_lrclib_get): "lrclib_get",
                    pool.submit(self._fetch_lrclib_search_all): "lrclib_search",
                    pool.submit(self._fetch_netease): "netease",
                    pool.submit(self._fetch_ovh): "ovh",
                }
                
                # Collect results as they complete (fastest first)
                for future in as_completed(futures, timeout=12):
                    try:
                        result = future.result()
                        if result is None:
                            continue
                        if isinstance(result, list):
                            all_results.extend(result)
                        elif result:
                            all_results.append(result)
                    except Exception:
                        pass

            # Deduplicate: prefer synced over plain, remove exact text dupes
            all_results = self._deduplicate(all_results)
            
            # Romanize all results
            if self.request.romanize:
                for r in all_results:
                    self._romanize_if_needed(r)
            
            if all_results:
                self.lyrics_ready.emit(all_results, 0, self.request)
            else:
                fallback = [LyricsResult(plain_text="No lyrics found")]
                self.lyrics_ready.emit(fallback, 0, self.request)
            
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def _deduplicate(self, results: List[LyricsResult]) -> List[LyricsResult]:
        """Remove duplicates, preferring synced lyrics over plain-only."""
        seen_texts = set()
        unique = []
        for r in results:
            # Build a fingerprint from the first few synced lines or plain text
            if r.synced_lines:
                key = tuple(l.text.strip().lower() for l in r.synced_lines[:5])
            elif r.plain_text:
                key = tuple(r.plain_text.strip().lower()[:200].split('\n')[:5])
            else:
                continue
            if key not in seen_texts:
                seen_texts.add(key)
                unique.append(r)
        
        # Sort: synced first, then by number of lines (more = better)
        unique.sort(key=lambda r: (
            not r.has_line_sync,  # synced first
            -len(r.synced_lines) if r.synced_lines else 0
        ))
        return unique

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
            
        try:
            resp = _session.get(url, params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return LrcParser.parse(
                    plain_lyrics=data.get("plainLyrics", ""),
                    synced_lyrics=data.get("syncedLyrics", "")
                )
        except requests.exceptions.RequestException:
            pass
        return None
        
    def _fetch_lrclib_search_all(self) -> Optional[List[LyricsResult]]:
        """Fetch ALL search results from LRCLIB so user can cycle through them."""
        url = "https://lrclib.net/api/search"
        params = {
            "track_name": self.request.title,
            "artist_name": self.request.artist
        }
        
        try:
            resp = _session.get(url, params=params, timeout=5)
        except requests.exceptions.RequestException:
            return None
        
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                results = []
                for entry in data[:10]:  # Cap at 10 alternatives
                    r = LrcParser.parse(
                        plain_lyrics=entry.get("plainLyrics", ""),
                        synced_lyrics=entry.get("syncedLyrics", "")
                    )
                    if r and (r.synced_lines or r.plain_text):
                        results.append(r)
                return results if results else None
        return None
        
    def _fetch_ovh(self) -> Optional[LyricsResult]:
        url = f"https://api.lyrics.ovh/v1/{self.request.artist}/{self.request.title}"
        try:
            resp = _session.get(url, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                return LrcParser.parse(plain_lyrics=data.get("lyrics", ""))
        except requests.exceptions.RequestException:
            pass
        return None

    def _fetch_netease(self) -> Optional[List[LyricsResult]]:
        """Backup provider using NetEase Music API. Returns multiple results."""
        try:
            search_url = "https://music.cyrvoid.com/search"
            # Get top 5 matches
            params = {"keywords": f"{self.request.artist} {self.request.title}", "limit": 5}
            search_resp = _session.get(search_url, params=params, timeout=5)
            if search_resp.status_code == 200:
                data = search_resp.json()
                songs = data.get("result", {}).get("songs", [])
                results = []
                # Fetch lyrics for up to 3 best matches to avoid flooding
                for s in songs[:3]:
                    song_id = s["id"]
                    lyric_url = f"https://music.cyrvoid.com/lyric?id={song_id}"
                    lyric_resp = _session.get(lyric_url, timeout=5)
                    if lyric_resp.status_code == 200:
                        ld = lyric_resp.json()
                        lrc_text = ld.get("lrc", {}).get("lyric", "")
                        tlyric = ld.get("tlyric", {}).get("lyric", "") # Translation
                        
                        r = LrcParser.parse(
                            plain_lyrics=lrc_text,
                            synced_lyrics=lrc_text
                        )
                        if r and (r.synced_lines or r.plain_text):
                            results.append(r)
                            
                        # If there's a translation, treat it as another version?
                        if tlyric:
                            tr = LrcParser.parse(plain_lyrics=tlyric, synced_lyrics=tlyric)
                            if tr and (tr.synced_lines or tr.plain_text):
                                results.append(tr)
                return results if results else None
        except Exception:
            pass
        return None

    def _romanize_if_needed(self, result: LyricsResult):
        if not self.request.romanize:
            return
        if not result:
            return
            
        # Detect if the whole song is likely Japanese
        is_jp = Romanizer.contains_japanese(self.request.artist) or \
                Romanizer.contains_japanese(self.request.title)
        
        if not is_jp:
            if result.synced_lines:
                for line in result.synced_lines:
                    if Romanizer.contains_japanese(line.text):
                        is_jp = True
                        break
            elif result.plain_text:
                if Romanizer.contains_japanese(result.plain_text):
                    is_jp = True

        if result.synced_lines:
            for line in result.synced_lines:
                rom = Romanizer.romanize(line.text, is_japanese_hint=is_jp)
                if rom and rom.lower() != line.text.lower():
                    line.romanized_text = rom
