import sys

from PyQt6.QtWidgets import QApplication

from iracing_window import IracingWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = IracingWindow()
    win.show()
    sys.exit(app.exec())
