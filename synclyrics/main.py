import sys
import os
import signal
from PyQt6.QtWidgets import QApplication
from synclyrics.ui.main_window import MainWindow

def main():
    # Suppress harmless Qt OpenType font warnings (Nerd Font glyphs)
    os.environ.setdefault("QT_LOGGING_RULES", "qt.text.font.db=false")
    
    # Allow python to handle Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    app = QApplication(sys.argv)
    
    # Set a proper font fallback chain for the entire app
    font = app.font()
    font.setFamilies(["JetBrainsMono Nerd Font", "JetBrainsMono NF", "Inter", "Fira Code", "monospace"])
    font.setStyleHint(font.StyleHint.Monospace)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
