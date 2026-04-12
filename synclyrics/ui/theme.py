from dataclasses import dataclass

@dataclass
class ThemePalette:
    name: str
    background: str
    surface: str
    surface_alt: str
    primary: str
    secondary: str
    text_main: str
    text_muted: str
    error: str

PRESETS = {
    "tokyo-night": ThemePalette(
        name="Tokyo Night", background="#1a1b26", surface="#24283b", surface_alt="#292e42",
        primary="#7aa2f7", secondary="#bb9af7", text_main="#c0caf5", text_muted="#565f89", error="#f7768e"
    ),
    "nord": ThemePalette(
        name="Nord", background="#2e3440", surface="#3b4252", surface_alt="#434c5e",
        primary="#88c0d0", secondary="#81a1c1", text_main="#eceff4", text_muted="#4c566a", error="#bf616a"
    ),
    "gruvbox": ThemePalette(
        name="Gruvbox", background="#282828", surface="#3c3836", surface_alt="#504945",
        primary="#b8bb26", secondary="#fabd2f", text_main="#ebdbb2", text_muted="#a89984", error="#fb4934"
    ),
    "rose-pine": ThemePalette(
        name="Rosé Pine", background="#191724", surface="#1f1d2e", surface_alt="#26233a",
        primary="#ebbcba", secondary="#c4a7e7", text_main="#e0def4", text_muted="#6e6a86", error="#eb6f92"
    ),
    "catppuccin-mocha": ThemePalette(
        name="Catppuccin Mocha", background="#1e1e2e", surface="#313244", surface_alt="#45475a",
        primary="#cba6f7", secondary="#89b4fa", text_main="#cdd6f4", text_muted="#a6adc8", error="#f38ba8"
    ),
    "everforest": ThemePalette(
        name="Everforest", background="#2b3339", surface="#323c41", surface_alt="#3a454a",
        primary="#a7c080", secondary="#83c092", text_main="#d3c6aa", text_muted="#859289", error="#e67e80"
    ),
    "oxocarbon": ThemePalette(
        name="Oxocarbon", background="#161616", surface="#262626", surface_alt="#393939",
        primary="#33b1ff", secondary="#ff7eb6", text_main="#f2f4f8", text_muted="#8dc605", error="#ff7eb6"
    ),
    "sweet": ThemePalette(
        name="Sweet", background="#0c0e14", surface="#11141c", surface_alt="#191d29",
        primary="#c50ed2", secondary="#00f3ff", text_main="#c3c7d1", text_muted="#4d5366", error="#e8134d"
    ),
    "synthwave": ThemePalette(
        name="Synthwave", background="#0d0221", surface="#1a0442", surface_alt="#260663",
        primary="#ff00e6", secondary="#00e5ff", text_main="#f5d6ff", text_muted="#7b5299", error="#ff2a2a"
    )
}

def generate_theme_from_color(base_hex: str, text_main=None, text_muted=None, primary=None, secondary=None, bg=None, surface=None) -> ThemePalette:
    base_hex = base_hex.lstrip('#')
    p = primary if primary else '#' + base_hex
    return ThemePalette(
        name=f"Custom ({base_hex})", 
        background=bg if bg else "#0b0b0b", 
        surface=surface if surface else "#141414", 
        surface_alt="#1e1e1e",
        primary=p, 
        secondary=secondary if secondary else p, 
        text_main=text_main if text_main else "#ffffff", 
        text_muted=text_muted if text_muted else "#666666", 
        error="#ff5555"
    )

class ThemeManager:
    _instance = None
    
    def __init__(self):
        self.current_theme = PRESETS["tokyo-night"]
        self.callbacks = []
        
    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = ThemeManager()
        return cls._instance
        
    def set_preset(self, preset_id: str):
        if preset_id in PRESETS:
            self.current_theme = PRESETS[preset_id]
            self._notify()
            
    def set_custom_color(self, hex_color: str, **kwargs):
        try:
            self.current_theme = generate_theme_from_color(hex_color, **kwargs)
            self._notify()
        except ValueError:
            pass
            
    def register_callback(self, callback):
        self.callbacks.append(callback)
        
    def _notify(self):
        for cb in self.callbacks:
            cb(self.current_theme)

    @property
    def theme(self) -> ThemePalette:
        return self.current_theme
