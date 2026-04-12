import unicodedata
from typing import Optional

try:
    import pykakasi
    HAS_KAKASI = True
    kakasi = pykakasi.kakasi()
except ImportError:
    HAS_KAKASI = False

try:
    from pypinyin import lazy_pinyin
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False

try:
    from unidecode import unidecode
    HAS_UNIDECODE = True
except ImportError:
    HAS_UNIDECODE = False


class Romanizer:
    """Detects script and applies romanization."""
    
    @staticmethod
    def contains_cjk(text: str) -> bool:
        for char in text:
            name = unicodedata.name(char, "")
            if "CJK UNIFIED IDEOGRAPH" in name or "HIRAGANA" in name or "KATAKANA" in name or "HANGUL" in name:
                return True
        return False
        
    @staticmethod
    def contains_japanese(text: str) -> bool:
         for char in text:
            name = unicodedata.name(char, "")
            if "HIRAGANA" in name or "KATAKANA" in name:
                return True
         return False

    @staticmethod
    def romanize(text: str) -> Optional[str]:
        if not text or not text.strip():
            return None
            
        # Optimization: skip if it's already plain ASCII
        if all(ord(c) < 128 for c in text):
            return None

        # Prioritize PyKakasi for Japanese (Hiragana/Katakana + Kanji)
        if HAS_KAKASI and Romanizer.contains_japanese(text):
            result = kakasi.convert(text)
            return " ".join([item['hepburn'] for item in result])
            
        # Pypinyin for Chinese
        if HAS_PYPINYIN and Romanizer.contains_cjk(text): # Rough heuristic if not JP, try CN
             return " ".join(lazy_pinyin(text))
             
        # Fallback to unidecode for Korean, Cyrillic, Arabic, etc.
        if HAS_UNIDECODE:
            return unidecode(text)
            
        return None
