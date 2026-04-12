import sys
import signal
from PyQt6.QtWidgets import QApplication
from synclyrics.ui.main_window import MainWindow

def main():
    # Allow python to handle Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    app = QApplication(sys.argv)
    
    # Optional styling trick to force font rendering quality
    font = app.font()
    font.setFamily("Inter")
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
