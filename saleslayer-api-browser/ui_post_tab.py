from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QTextEdit, QSizePolicy
)


class PostTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.build_ui()

    def build_ui(self):
        main_layout = QVBoxLayout()

        controls_layout = QHBoxLayout()

        controls_layout.addWidget(QLabel("Entidad:"))
        self.entity_selector = QComboBox()
        self.entity_selector.addItems(["Products", "Variants", "Categories", "CustomEntities"])
        controls_layout.addWidget(self.entity_selector)

        controls_layout.addWidget(QLabel("Custom Entity:"))
        self.custom_entity_selector = QComboBox()
        self.custom_entity_selector.setMinimumWidth(320)
        self.custom_entity_selector.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        controls_layout.addWidget(self.custom_entity_selector)

        self.load_metadata_button = QPushButton("Load Metadata")
        controls_layout.addWidget(self.load_metadata_button)

        self.generate_payload_button = QPushButton("Generate Payload")
        controls_layout.addWidget(self.generate_payload_button)

        self.run_post_button = QPushButton("Run POST")
        controls_layout.addWidget(self.run_post_button)

        main_layout.addLayout(controls_layout)

        main_layout.addWidget(QLabel("Formulario POST"))
        self.form_info = QTextEdit()
        self.form_info.setReadOnly(True)
        self.form_info.setPlainText(
            "Esta pestaña queda preparada para la siguiente fase.\n\n"
            "Aquí construiremos:\n"
            "- carga de metadata\n"
            "- formulario dinámico con campos simples\n"
            "- preview del payload JSON\n"
            "- ejecución de POST\n"
        )
        main_layout.addWidget(self.form_info)

        main_layout.addWidget(QLabel("Payload preview"))
        self.payload_preview = QTextEdit()
        self.payload_preview.setReadOnly(True)
        main_layout.addWidget(self.payload_preview)

        self.setLayout(main_layout)