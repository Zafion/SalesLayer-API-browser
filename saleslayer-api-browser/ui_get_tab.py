import json
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QComboBox, QListWidget, QListWidgetItem,
    QTextEdit, QMessageBox, QSpinBox, QFileDialog, QSizePolicy,
    QSplitter
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from api_client import SalesLayerApiClient
from metadata_parser import extract_properties_from_metadata
from query_builder import build_params


SIMPLE_TYPES = {
    "string",
    "string | null",
    "integer",
    "integer | null",
    "number",
    "number | null",
    "boolean",
    "boolean | null",
}

OPERATOR_LABELS = {
    "eq": "igual a",
    "ne": "distinto de",
    "gt": "mayor que",
    "ge": "mayor o igual que",
    "lt": "menor que",
    "le": "menor o igual que",
    "contains": "contiene",
    "startswith": "empieza por",
    "endswith": "termina en",
}

STRING_OPERATORS = ["eq", "ne", "contains", "startswith", "endswith"]
NUMBER_OPERATORS = ["eq", "ne", "gt", "ge", "lt", "le"]
BOOLEAN_OPERATORS = ["eq", "ne"]


class GetTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        self.client = None
        self.current_properties = []
        self.current_simple_properties = []
        self.filters = []
        self.last_result_data = None
        self.custom_entities_tables = []

        self.is_loading_metadata = False
        self.is_populating_custom_entities = False

        self.build_ui()
        self.on_entity_changed()

    def build_ui(self):
        root_layout = QVBoxLayout()

        main_splitter = QSplitter(Qt.Vertical)

        # TOP AREA
        top_widget = QWidget()
        top_layout = QVBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)

        controls_layout = QHBoxLayout()

        controls_layout.addWidget(QLabel("Entidad:"))
        self.entity_selector = QComboBox()
        self.entity_selector.addItems(["Products", "Variants", "Categories", "CustomEntities"])
        self.entity_selector.currentIndexChanged.connect(self.on_entity_changed)
        controls_layout.addWidget(self.entity_selector)

        self.custom_entity_label = QLabel("Custom Entity:")
        controls_layout.addWidget(self.custom_entity_label)

        self.custom_entity_selector = QComboBox()
        self.custom_entity_selector.setMinimumWidth(320)
        self.custom_entity_selector.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.custom_entity_selector.currentIndexChanged.connect(self.on_custom_entity_changed)
        controls_layout.addWidget(self.custom_entity_selector)

        controls_layout.addWidget(QLabel("Top:"))
        self.top_input = QSpinBox()
        self.top_input.setRange(1, 100)
        self.top_input.setValue(10)
        controls_layout.addWidget(self.top_input)

        self.load_metadata_button = QPushButton("Load Metadata")
        self.load_metadata_button.clicked.connect(self.load_metadata)
        controls_layout.addWidget(self.load_metadata_button)

        self.run_query_button = QPushButton("Run Query")
        self.run_query_button.clicked.connect(self.run_query)
        controls_layout.addWidget(self.run_query_button)

        top_layout.addLayout(controls_layout)

        top_layout.addWidget(QLabel("Campos disponibles:"))
        self.fields_list = QListWidget()
        self.fields_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        top_layout.addWidget(self.fields_list, 1)

        top_layout.addWidget(QLabel("Filtros:"))

        filter_controls = QHBoxLayout()

        self.filter_joiner_selector = QComboBox()
        self.filter_joiner_selector.addItem("AND | y", "and")
        self.filter_joiner_selector.addItem("OR | o", "or")
        self.filter_joiner_selector.setMinimumWidth(120)
        filter_controls.addWidget(self.filter_joiner_selector, 1)

        self.filter_field_selector = QComboBox()
        self.filter_field_selector.setMinimumWidth(340)
        self.filter_field_selector.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.filter_field_selector.currentIndexChanged.connect(self.on_filter_field_changed)
        filter_controls.addWidget(self.filter_field_selector, 3)

        self.filter_operator_selector = QComboBox()
        self.filter_operator_selector.setMinimumWidth(210)
        filter_controls.addWidget(self.filter_operator_selector, 2)

        self.filter_value_input = QLineEdit()
        self.filter_value_input.setPlaceholderText("Valor del filtro")
        self.filter_value_input.setMinimumWidth(260)
        filter_controls.addWidget(self.filter_value_input, 3)

        self.add_filter_button = QPushButton("Add Filter")
        self.add_filter_button.clicked.connect(self.add_filter)
        filter_controls.addWidget(self.add_filter_button)

        self.remove_filter_button = QPushButton("Remove Selected Filter")
        self.remove_filter_button.clicked.connect(self.remove_selected_filter)
        filter_controls.addWidget(self.remove_filter_button)

        top_layout.addLayout(filter_controls)

        self.filters_list = QListWidget()
        self.filters_list.setMaximumHeight(130)
        top_layout.addWidget(self.filters_list)

        top_widget.setLayout(top_layout)

        # BOTTOM AREA
        bottom_splitter = QSplitter(Qt.Horizontal)

        results_widget = QWidget()
        results_layout = QVBoxLayout()
        results_layout.setContentsMargins(0, 0, 0, 0)

        results_header = QHBoxLayout()
        results_header.addWidget(QLabel("Resultados JSON:"))

        self.copy_json_button = QPushButton("Copy JSON")
        self.copy_json_button.clicked.connect(self.copy_json)
        results_header.addWidget(self.copy_json_button)

        self.export_json_button = QPushButton("Export JSON")
        self.export_json_button.clicked.connect(self.export_json)
        results_header.addWidget(self.export_json_button)

        results_header.addStretch()
        results_layout.addLayout(results_header)

        self.results_output = QTextEdit()
        self.results_output.setReadOnly(True)
        results_layout.addWidget(self.results_output)

        results_widget.setLayout(results_layout)

        params_widget = QWidget()
        params_layout = QVBoxLayout()
        params_layout.setContentsMargins(0, 0, 0, 0)

        params_layout.addWidget(QLabel("Query params:"))
        self.query_preview = QTextEdit()
        self.query_preview.setReadOnly(True)
        params_layout.addWidget(self.query_preview)

        params_widget.setLayout(params_layout)

        bottom_splitter.addWidget(results_widget)
        bottom_splitter.addWidget(params_widget)
        bottom_splitter.setStretchFactor(0, 3)
        bottom_splitter.setStretchFactor(1, 2)

        main_splitter.addWidget(top_widget)
        main_splitter.addWidget(bottom_splitter)
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 2)

        root_layout.addWidget(main_splitter)
        self.setLayout(root_layout)

    def on_entity_changed(self):
        is_custom_entities = self.entity_selector.currentText() == "CustomEntities"
        self.custom_entity_label.setVisible(is_custom_entities)
        self.custom_entity_selector.setVisible(is_custom_entities)

    def get_client(self):
        api_key = self.main_window.get_api_key()
        if not api_key:
            raise ValueError("Debes introducir un API key.")
        return SalesLayerApiClient(api_key)

    def _extract_custom_entity_display_denominator(self, schema: dict) -> str | None:
        for candidate in [schema.get("$id", ""), schema.get("title", ""), schema.get("description", "")]:
            if not candidate:
                continue
            import re
            for pattern in [r"CustomEntities\('(.+?)'\)", r"CustomEntity\('(.+?)'\)"]:
                match = re.search(pattern, candidate)
                if match:
                    return match.group(1).strip()

        title = schema.get("title")
        return str(title).strip() if title else None

    def _extract_custom_entity_post_denominator(self, schema: dict) -> str | None:
        storage_name = schema.get("x-storage-object-name")
        if storage_name:
            return str(storage_name).strip()
        return self._extract_custom_entity_display_denominator(schema)

    def get_selected_custom_entity_metadata_denominator(self):
        data = self.custom_entity_selector.currentData()
        if isinstance(data, dict):
            return data.get("display_denominator")
        return data

    def get_selected_custom_entity_post_denominator(self):
        data = self.custom_entity_selector.currentData()
        if isinstance(data, dict):
            return data.get("post_denominator")
        return data

    def get_selected_custom_entity_denominator(self):
        return self.get_selected_custom_entity_metadata_denominator()

    def get_allowed_operators_for_type(self, field_type: str):
        normalized_type = (field_type or "").strip().lower()

        if normalized_type in {"integer", "integer | null", "number", "number | null"}:
            return NUMBER_OPERATORS

        if normalized_type in {"boolean", "boolean | null"}:
            return BOOLEAN_OPERATORS

        return STRING_OPERATORS

    def populate_operator_selector(self, field_type: str):
        self.filter_operator_selector.clear()

        for op in self.get_allowed_operators_for_type(field_type):
            self.filter_operator_selector.addItem(
                f"{op} | {OPERATOR_LABELS[op]}",
                op
            )

    def on_filter_field_changed(self):
        field_data = self.filter_field_selector.currentData()
        if not field_data:
            self.filter_operator_selector.clear()
            return

        field_type = field_data.get("type", "string")
        self.populate_operator_selector(field_type)

    def load_custom_entities_tables(self, force_refresh: bool = False):
        previous_selection = self.get_selected_custom_entity_metadata_denominator()

        if self.custom_entity_selector.count() > 0 and not force_refresh:
            return

        metadata_text = self.client.get_metadata("CustomEntities")
        data = json.loads(metadata_text)
        schemas = data.get("value", [])

        tables = []
        for schema in schemas:
            display_denominator = self._extract_custom_entity_display_denominator(schema)
            if not display_denominator:
                continue

            post_denominator = self._extract_custom_entity_post_denominator(schema)
            title = schema.get("title", display_denominator)

            tables.append({
                "title": title,
                "display_denominator": display_denominator,
                "post_denominator": post_denominator or display_denominator,
            })

        unique = {}
        for table in tables:
            unique[table["display_denominator"]] = table

        self.custom_entities_tables = sorted(unique.values(), key=lambda x: x["title"].lower())

        if not self.custom_entities_tables:
            raise ValueError("No se encontraron tablas de Custom Entities en la metadata.")

        self.is_populating_custom_entities = True
        try:
            self.custom_entity_selector.clear()

            for table in self.custom_entities_tables:
                self.custom_entity_selector.addItem(table["title"], table)

            if previous_selection:
                for index in range(self.custom_entity_selector.count()):
                    data = self.custom_entity_selector.itemData(index)
                    if isinstance(data, dict) and data.get("display_denominator") == previous_selection:
                        self.custom_entity_selector.setCurrentIndex(index)
                        break
        finally:
            self.is_populating_custom_entities = False

    def load_metadata(self):
        if self.is_loading_metadata:
            return

        try:
            self.is_loading_metadata = True
            self.client = self.get_client()
            entity = self.entity_selector.currentText()

            if entity == "CustomEntities":
                self.load_custom_entities_tables(force_refresh=False)

                denominator = self.get_selected_custom_entity_metadata_denominator()
                if not denominator:
                    raise ValueError("No se ha podido determinar la tabla de Custom Entity.")

                metadata_text = self.client.get_metadata("CustomEntities", denominator)
                properties = extract_properties_from_metadata(
                    metadata_text,
                    selected_entity="CustomEntities",
                    custom_entity_denominator=denominator
                )
            else:
                metadata_text = self.client.get_metadata(entity)
                properties = extract_properties_from_metadata(metadata_text, entity)

            self.current_properties = properties
            self.current_simple_properties = [
                prop for prop in properties if prop["type"] in SIMPLE_TYPES
            ]

            self.filters = []
            self.fields_list.clear()
            self.filters_list.clear()
            self.filter_field_selector.clear()
            self.filter_operator_selector.clear()

            for prop in properties:
                label = f'{prop["name"]} | {prop["title"]} | {prop["type"]}'
                if prop["required"]:
                    label += " | required"
                if prop["custom_type"]:
                    label += f' | {prop["custom_type"]}'

                item = QListWidgetItem(label)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                item.setData(Qt.UserRole, prop["name"])
                self.fields_list.addItem(item)

            for prop in self.current_simple_properties:
                combo_label = f'{prop["name"]} | {prop["title"]} | {prop["type"]}'
                self.filter_field_selector.addItem(
                    combo_label,
                    {
                        "name": prop["name"],
                        "type": prop["type"],
                        "title": prop["title"],
                    }
                )

            if self.filter_field_selector.count() > 0:
                self.on_filter_field_changed()

            extra = ""
            if entity == "CustomEntities":
                extra = (
                    f" Tabla metadata/read: {self.get_selected_custom_entity_metadata_denominator()}."
                    f" Tabla create/post: {self.get_selected_custom_entity_post_denominator()}."
                )

            QMessageBox.information(
                self,
                "Metadata cargada",
                f"Se han cargado {len(properties)} campos. "
                f"{len(self.current_simple_properties)} disponibles para filtros simples."
                f"{extra}"
            )

        except Exception as e:
            QMessageBox.critical(self, "Error cargando metadata", str(e))
        finally:
            self.is_loading_metadata = False

    def on_custom_entity_changed(self):
        if self.entity_selector.currentText() != "CustomEntities":
            return

        if self.is_populating_custom_entities or self.is_loading_metadata:
            return

        if not self.main_window.get_api_key():
            return

        if self.custom_entity_selector.count() == 0:
            return

        self.load_metadata()

    def get_selected_fields(self):
        selected_fields = []

        for i in range(self.fields_list.count()):
            item = self.fields_list.item(i)
            if item.checkState() == Qt.Checked:
                selected_fields.append(item.data(Qt.UserRole))

        return selected_fields

    def add_filter(self):
        field_data = self.filter_field_selector.currentData()
        field_label = self.filter_field_selector.currentText()
        operator = self.filter_operator_selector.currentData()
        operator_label = self.filter_operator_selector.currentText()
        value = self.filter_value_input.text().strip()
        joiner = self.filter_joiner_selector.currentData()

        if not field_data:
            QMessageBox.warning(self, "Filtro inválido", "Primero carga metadata.")
            return

        field = field_data["name"]
        field_type = field_data["type"]

        if not value:
            QMessageBox.warning(self, "Filtro inválido", "Introduce un valor para el filtro.")
            return

        filter_item = {
            "field": field,
            "field_type": field_type,
            "field_label": field_label,
            "operator": operator,
            "operator_label": operator_label,
            "value": value,
            "joiner": joiner,
        }
        self.filters.append(filter_item)

        self.refresh_filters_list()
        self.filter_value_input.clear()

    def remove_selected_filter(self):
        current_row = self.filters_list.currentRow()
        if current_row < 0:
            return

        del self.filters[current_row]
        self.refresh_filters_list()

    def refresh_filters_list(self):
        self.filters_list.clear()

        for index, item in enumerate(self.filters):
            prefix = ""
            if index > 0:
                prefix = ("OR" if item.get("joiner") == "or" else "AND") + " | "
            text = f'{prefix}{item["field"]} [{item["field_type"]}] | {item["operator_label"]} | {item["value"]}'
            self.filters_list.addItem(text)

    def run_query(self):
        try:
            self.client = self.get_client()
            entity = self.entity_selector.currentText()
            selected_fields = self.get_selected_fields()
            top = self.top_input.value()

            if not selected_fields:
                raise ValueError("Selecciona al menos un campo antes de ejecutar la consulta.")

            params = build_params(
                selected_fields=selected_fields,
                filters=self.filters,
                top=top
            )

            self.query_preview.setPlainText(
                json.dumps(params, indent=2, ensure_ascii=False)
            )

            denominator = None
            if entity == "CustomEntities":
                denominator = self.get_selected_custom_entity_metadata_denominator()
                if not denominator:
                    raise ValueError("Debes seleccionar una tabla de Custom Entity.")

            data = self.client.get_data(entity, params, denominator)
            self.last_result_data = data

            self.results_output.setPlainText(
                json.dumps(data, indent=2, ensure_ascii=False)
            )

        except Exception as e:
            QMessageBox.critical(self, "Error ejecutando consulta", str(e))

    def copy_json(self):
        text = self.results_output.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Sin contenido", "No hay JSON para copiar.")
            return

        QGuiApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copiado", "El JSON se ha copiado al portapapeles.")

    def export_json(self):
        if self.last_result_data is None:
            QMessageBox.information(self, "Sin contenido", "No hay JSON para exportar.")
            return

        entity = self.entity_selector.currentText().lower()
        denominator = self.get_selected_custom_entity_metadata_denominator()

        if entity == "customentities" and denominator:
            safe_denominator = (
                denominator.replace("/", "_")
                .replace("\\", "_")
                .replace(" ", "_")
            )
            default_name = f"{entity}_{safe_denominator}_result.json"
        else:
            default_name = f"{entity}_result.json"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar JSON",
            str(Path.home() / default_name),
            "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.last_result_data, f, indent=2, ensure_ascii=False)

            QMessageBox.information(self, "Exportado", f"JSON guardado en:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error exportando JSON", str(e))