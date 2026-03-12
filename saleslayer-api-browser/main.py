import sys

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit, QTabWidget
)

from ui_get_tab import GetTab
from ui_post_tab import PostTab
from ui_patch_tab import PatchTab


class SalesLayerBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sales Layer API Browser")
        self.resize(1280, 850)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()

        api_layout = QHBoxLayout()
        api_layout.addWidget(QLabel("API Key:"))

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Introduce aquí el API key del cliente")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        api_layout.addWidget(self.api_key_input)

        main_layout.addLayout(api_layout)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.get_tab = GetTab(self)
        self.post_tab = PostTab(self)
        self.patch_tab = PatchTab(self)

        self.tabs.addTab(self.get_tab, "GET / Read")
        self.tabs.addTab(self.post_tab, "POST / Create")
        self.tabs.addTab(self.patch_tab, "PATCH / Update")

        central_widget.setLayout(main_layout)

    def get_api_key(self) -> str:
        return self.api_key_input.text().strip()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SalesLayerBrowser()
    window.show()
    sys.exit(app.exec())