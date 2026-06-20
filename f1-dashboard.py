import sys

from PyQt6.QtWidgets import QApplication

from dashboard import DashboardWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = DashboardWindow()
    win.show()
    sys.exit(app.exec())

