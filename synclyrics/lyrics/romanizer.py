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
            try:
                name = unicodedata.name(char, "")
                if any(x in name for x in ["CJK UNIFIED IDEOGRAPH", "HIRAGANA", "KATAKANA", "HANGUL", "BOPOMOFO"]):
                    return True
            except: continue
        return False
        
    @staticmethod
    def contains_japanese(text: str) -> bool:
        for char in text:
            try:
                name = unicodedata.name(char, "")
                # Hiragana, Katakana, and Japanese-specific punctuation
                if "HIRAGANA" in name or "KATAKANA" in name or "IDEOGRAPHIC ITERATION MARK" in name:
                    return True
            except: continue
        return False

    @staticmethod
    def romanize(text: str, is_japanese_hint: bool = False) -> Optional[str]:
        if not text or not text.strip():
            return None
            
        # Optimization: skip if it's already plain ASCII
        if all(ord(c) < 128 for c in text):
            return None

        # Detect script
        has_jp = Romanizer.contains_japanese(text) or is_japanese_hint
        has_cjk = Romanizer.contains_cjk(text)

        # Prioritize PyKakasi for Japanese (Hiragana/Katakana + Kanji)
        if HAS_KAKASI and (has_jp or (has_cjk and not HAS_PYPINYIN)):
            result = kakasi.convert(text)
            return " ".join([item['hepburn'] for item in result])
            
        # Pypinyin for Chinese (only if we didn't suspect Japanese)
        if HAS_PYPINYIN and has_cjk:
             return " ".join(lazy_pinyin(text))
             
        # Fallback to unidecode for Korean, Cyrillic, Arabic, etc.
        if HAS_UNIDECODE:
            return unidecode(text)
            
        return None
