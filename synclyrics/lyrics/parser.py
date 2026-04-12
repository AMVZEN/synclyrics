import re
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class LyricWord:
    text: str
    start_time: float
    end_time: float

@dataclass
class LyricLine:
    text: str
    start_time: float
    end_time: Optional[float] = None
    words: List[LyricWord] = field(default_factory=list)
    romanized_text: Optional[str] = None

@dataclass
class LyricsResult:
    synced_lines: List[LyricLine] = field(default_factory=list)
    plain_text: str = ""
    has_line_sync: bool = False
    has_word_sync: bool = False

class LrcParser:
    """Parses standard and enhanced LRC formats."""
    
    # Matches [mm:ss.xx]
    LINE_TIME_REGEX = re.compile(r'\[(\d{2}):(\d{2}\.\d{2,3})\]')
    # Matches <mm:ss.xx>
    WORD_TIME_REGEX = re.compile(r'<(\d{2}):(\d{2}\.\d{2,3})>')
    
    @staticmethod
    def _parse_time(m: str) -> float:
        """Converts mm:ss.xx string match to seconds."""
        # This matches the groups from regex
        minutes = int(m[0])
        seconds = float(m[1])
        return minutes * 60 + seconds
        
    @classmethod
    def parse(cls, plain_lyrics: str, synced_lyrics: Optional[str] = None) -> LyricsResult:
        result = LyricsResult(plain_text=plain_lyrics or "")
        
        if not synced_lyrics:
            return result
            
        lines = synced_lyrics.splitlines()
        parsed_lines = []
        has_word_sync = False
        
        for line in lines:
            line_time_match = cls.LINE_TIME_REGEX.match(line)
            if not line_time_match:
                continue
                
            start_time = cls._parse_time(line_time_match.groups())
            content = line[line_time_match.end():].strip()
            
            # Check for word-level sync
            words = []
            if '<' in content and '>' in content:
                has_word_sync = True
                # Enhanced LRC parsing
                # Format: [line_time] <word_time>word <word_time>word ...
                # or [line_time] word <word_time>word ...
                
                # Split content by word time tags, keeping the tags
                parts = re.split(r'(<\d{2}:\d{2}\.\d{2,3}>)', content)
                
                current_word_start = start_time
                for part in parts:
                    if not part: continue
                    
                    time_match = cls.WORD_TIME_REGEX.match(part)
                    if time_match:
                        # This part is a time tag <mm:ss.xx>
                        new_time = cls._parse_time(time_match.groups())
                        # If we already have words, the end_time of the last word is this tag's time
                        if words:
                            words[-1].end_time = new_time
                        current_word_start = new_time
                    else:
                        # This part is text
                        text_part = part.strip()
                        if text_part:
                            # Split by spaces if multiple words are together? 
                            # Usually enhanced LRC has tags between EVERY word.
                            words.append(LyricWord(
                                text=text_part,
                                start_time=current_word_start,
                                end_time=current_word_start + 0.5 # Default duration if not capped by next tag
                            ))
                
                # Cap the last word's end time to the next line's start if possible, 
                # but we'll do that after the loop.
                        
            # Clean plain text for this line
            clean_text = cls.WORD_TIME_REGEX.sub('', content).strip()
            
            parsed_lines.append(LyricLine(
                text=clean_text,
                start_time=start_time,
                words=words
            ))
            
        # Calculate ending times for lines
        for i in range(len(parsed_lines) - 1):
            parsed_lines[i].end_time = parsed_lines[i+1].start_time
            
        if parsed_lines:
            # Fake end time for last line
            parsed_lines[-1].end_time = parsed_lines[-1].start_time + 10.0
            
        result.synced_lines = parsed_lines
        result.has_line_sync = True
        result.has_word_sync = has_word_sync
        
        return result
