import json
from pathlib import Path
from urllib.parse import quote

import requests

from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QTextEdit, QSizePolicy, QMessageBox, QFileDialog, QLineEdit,
    QSplitter
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from api_client import SalesLayerApiClient


BASE_URL = "https://api2.saleslayer.com/rest/Catalog"


class DeleteTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        self.client = None
        self.custom_entities_tables = []
        self.last_result_data = None

        self.is_loading_tables = False
        self.is_populating_custom_entities = False

        self.build_ui()
        self.on_entity_changed()

    def build_ui(self):
        root_layout = QVBoxLayout()

        main_splitter = QSplitter(Qt.Vertical)

        # TOP
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
        self.custom_entity_selector.setMinimumWidth(260)
        self.custom_entity_selector.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.custom_entity_selector.currentIndexChanged.connect(self.on_custom_entity_changed)
        controls_layout.addWidget(self.custom_entity_selector)

        self.load_tables_button = QPushButton("Load Custom Entities")
        self.load_tables_button.clicked.connect(self.load_custom_entities_tables)
        controls_layout.addWidget(self.load_tables_button)

        top_layout.addLayout(controls_layout)

        route_layout = QHBoxLayout()

        self.item_id_label = QLabel("Product ID:")
        route_layout.addWidget(self.item_id_label)

        self.item_id_input = QLineEdit()
        self.item_id_input.setPlaceholderText("Introduce el ID numérico del item a eliminar")
        route_layout.addWidget(self.item_id_input)

        self.delete_button = QPushButton("Run DELETE")
        self.delete_button.clicked.connect(self.run_delete)
        route_layout.addWidget(self.delete_button)

        top_layout.addLayout(route_layout)

        confirm_layout = QHBoxLayout()
        confirm_layout.addWidget(QLabel("Confirmación:"))

        self.confirm_input = QLineEdit()
        self.confirm_input.setPlaceholderText('Escribe DELETE para confirmar')
        confirm_layout.addWidget(self.confirm_input)

        top_layout.addLayout(confirm_layout)

        self.info_box = QTextEdit()
        self.info_box.setReadOnly(True)
        self.info_box.setMaximumHeight(180)
        self.info_box.setPlainText(
            "DELETE elimina un solo item por llamada.\n"
            "Debes indicar el ID de ruta numérico.\n"
            "Para evitar errores, escribe DELETE antes de ejecutar."
        )
        top_layout.addWidget(self.info_box)

        top_widget.setLayout(top_layout)

        # BOTTOM
        bottom_splitter = QSplitter(Qt.Horizontal)

        result_widget = QWidget()
        result_layout = QVBoxLayout()
        result_layout.setContentsMargins(0, 0, 0, 0)

        result_header = QHBoxLayout()
        result_header.addWidget(QLabel("Resultado DELETE"))

        self.copy_json_button = QPushButton("Copy JSON")
        self.copy_json_button.clicked.connect(self.copy_json)
        result_header.addWidget(self.copy_json_button)

        self.export_json_button = QPushButton("Export JSON")
        self.export_json_button.clicked.connect(self.export_json)
        result_header.addWidget(self.export_json_button)

        result_header.addStretch()
        result_layout.addLayout(result_header)

        self.results_output = QTextEdit()
        self.results_output.setReadOnly(True)
        result_layout.addWidget(self.results_output)

        result_widget.setLayout(result_layout)

        request_widget = QWidget()
        request_layout = QVBoxLayout()
        request_layout.setContentsMargins(0, 0, 0, 0)

        request_layout.addWidget(QLabel("Request preview"))
        self.request_preview = QTextEdit()
        self.request_preview.setReadOnly(True)
        request_layout.addWidget(self.request_preview)

        request_widget.setLayout(request_layout)

        bottom_splitter.addWidget(result_widget)
        bottom_splitter.addWidget(request_widget)
        bottom_splitter.setStretchFactor(0, 3)
        bottom_splitter.setStretchFactor(1, 2)

        main_splitter.addWidget(top_widget)
        main_splitter.addWidget(bottom_splitter)
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 3)

        root_layout.addWidget(main_splitter)
        self.setLayout(root_layout)

    def on_entity_changed(self):
        entity = self.entity_selector.currentText()
        is_custom_entities = entity == "CustomEntities"

        self.custom_entity_label.setVisible(is_custom_entities)
        self.custom_entity_selector.setVisible(is_custom_entities)
        self.load_tables_button.setVisible(is_custom_entities)

        label_map = {
            "Products": "Product ID:",
            "Variants": "Variant ID:",
            "Categories": "Category ID:",
            "CustomEntities": "Item ID:",
        }
        self.item_id_label.setText(label_map.get(entity, "Item ID:"))

        info_lines = [
            "DELETE elimina un solo item por llamada.",
            "Debes indicar el ID de ruta numérico.",
            "Para evitar errores, escribe DELETE antes de ejecutar.",
        ]

        if entity == "Products":
            info_lines.append("Endpoint: /rest/Catalog/Products(productId)")
        elif entity == "Variants":
            info_lines.append("Endpoint: /rest/Catalog/Variants(variantId)")
        elif entity == "Categories":
            info_lines.append("Endpoint: /rest/Catalog/Categories(categoryId)")
        elif entity == "CustomEntities":
            info_lines.append("Endpoint documentado: /rest/Catalog/CustomEntity('{customEntityDenominator}')/Item(itemId)")
            info_lines.append("La pestaña probará singular y, si da 404, hará fallback a plural.")

        self.info_box.setPlainText("\n".join(info_lines))

    def get_client(self):
        api_key = self.main_window.get_api_key()
        if not api_key:
            raise ValueError("Debes introducir un API key.")
        return SalesLayerApiClient(api_key)

    def _request_headers(self) -> dict:
        api_key = self.main_window.get_api_key()
        return {
            "X-API-KEY": api_key,
            "Accept": "*/*",
            "User-Agent": "SalesLayerApiBrowser/0.1",
        }

    def _extract_custom_entity_display_denominator(self, schema: dict) -> str | None:
        import re

        for candidate in [schema.get("$id", ""), schema.get("title", ""), schema.get("description", "")]:
            if not candidate:
                continue
            for pattern in [r"CustomEntities\('(.+?)'\)", r"CustomEntity\('(.+?)'\)"]:
                match = re.search(pattern, candidate)
                if match:
                    return match.group(1).strip()

        title = schema.get("title")
        return str(title).strip() if title else None

    def get_selected_custom_entity_denominator(self):
        data = self.custom_entity_selector.currentData()
        if isinstance(data, dict):
            return data.get("display_denominator")
        return data

    def load_custom_entities_tables(self):
        if self.is_loading_tables:
            return

        try:
            self.is_loading_tables = True
            self.client = self.get_client()

            metadata_text = self.client.get_metadata("CustomEntities")
            data = json.loads(metadata_text)
            schemas = data.get("value", [])

            tables = []
            for schema in schemas:
                display_denominator = self._extract_custom_entity_display_denominator(schema)
                if not display_denominator:
                    continue

                title = schema.get("title", display_denominator)
                tables.append({
                    "title": title,
                    "display_denominator": display_denominator,
                })

            unique = {}
            for table in tables:
                unique[table["display_denominator"]] = table

            self.custom_entities_tables = sorted(unique.values(), key=lambda x: x["title"].lower())

            if not self.custom_entities_tables:
                raise ValueError("No se encontraron tablas de Custom Entities en la metadata.")

            previous_selection = self.get_selected_custom_entity_denominator()

            self.is_populating_custom_entities = True
            try:
                self.custom_entity_selector.clear()

                for table in self.custom_entities_tables:
                    label = f"CustomEntities('{table['display_denominator']}')"
                    self.custom_entity_selector.addItem(label, table)

                if previous_selection:
                    for index in range(self.custom_entity_selector.count()):
                        item_data = self.custom_entity_selector.itemData(index)
                        if isinstance(item_data, dict) and item_data.get("display_denominator") == previous_selection:
                            self.custom_entity_selector.setCurrentIndex(index)
                            break
            finally:
                self.is_populating_custom_entities = False

            QMessageBox.information(
                self,
                "Custom Entities cargadas",
                f"Se han cargado {len(self.custom_entities_tables)} tablas."
            )

        except Exception as e:
            QMessageBox.critical(self, "Error cargando Custom Entities", str(e))
        finally:
            self.is_loading_tables = False

    def on_custom_entity_changed(self):
        if self.entity_selector.currentText() != "CustomEntities":
            return
        if self.is_populating_custom_entities or self.is_loading_tables:
            return

    def _get_route_item_id(self) -> int:
        raw = self.item_id_input.text().strip()
        if not raw:
            raise ValueError("Debes indicar el ID numérico del item a eliminar.")
        try:
            return int(raw)
        except ValueError as e:
            raise ValueError("El ID de ruta debe ser numérico.") from e

    def _build_delete_candidate_urls(self, entity: str, item_id: int, custom_entity_denominator: str | None = None) -> list[str]:
        if entity == "Products":
            return [f"{BASE_URL}/Products({item_id})"]

        if entity == "Variants":
            return [f"{BASE_URL}/Variants({item_id})"]

        if entity == "Categories":
            return [f"{BASE_URL}/Categories({item_id})"]

        if entity == "CustomEntities":
            if not custom_entity_denominator:
                raise ValueError("Debes seleccionar una tabla de Custom Entity.")

            encoded = quote(custom_entity_denominator, safe="")
            return [
                f"{BASE_URL}/CustomEntity('{encoded}')/Item({item_id})",
                f"{BASE_URL}/CustomEntities('{encoded}')/Item({item_id})",
            ]

        raise ValueError(f"Entidad no soportada para DELETE: {entity}")

    def _delete_request(self, entity: str, item_id: int, custom_entity_denominator: str | None = None) -> dict:
        candidate_urls = self._build_delete_candidate_urls(entity, item_id, custom_entity_denominator)
        headers = self._request_headers()

        self.request_preview.setPlainText(
            json.dumps(
                {
                    "entity": entity,
                    "item_id": item_id,
                    "custom_entity_denominator": custom_entity_denominator,
                    "candidate_urls": candidate_urls,
                },
                indent=2,
                ensure_ascii=False
            )
        )

        last_404_response = None

        for url in candidate_urls:
            response = requests.delete(
                url,
                headers=headers,
                timeout=30
            )

            if response.status_code == 404 and len(candidate_urls) > 1:
                last_404_response = response
                continue

            if not response.ok:
                detail = response.text.strip()
                if detail:
                    raise ValueError(
                        f"{response.status_code} Client Error for url: {url}\n\nRespuesta API:\n{detail}"
                    )
                response.raise_for_status()

            if not response.text.strip():
                return {
                    "status_code": response.status_code,
                    "message": "No Content",
                    "request_url": url,
                }

            try:
                data = response.json()
                data["_request_url"] = url
                return data
            except ValueError:
                return {
                    "status_code": response.status_code,
                    "raw_response": response.text,
                    "request_url": url,
                }

        if last_404_response is not None:
            detail = last_404_response.text.strip()
            raise ValueError(
                f"{last_404_response.status_code} Client Error for url: {last_404_response.url}\n\nRespuesta API:\n{detail}"
            )

        raise ValueError("No se pudo ejecutar DELETE.")

    def run_delete(self):
        try:
            if self.confirm_input.text().strip() != "DELETE":
                raise ValueError("Escribe DELETE en el campo de confirmación antes de ejecutar.")

            entity = self.entity_selector.currentText()
            item_id = self._get_route_item_id()

            denominator = None
            if entity == "CustomEntities":
                denominator = self.get_selected_custom_entity_denominator()
                if not denominator:
                    raise ValueError("Debes seleccionar una tabla de Custom Entity.")

            confirm_message = f"Vas a eliminar este item:\n\nEntidad: {entity}\nID: {item_id}"
            if denominator:
                confirm_message += f"\nTabla: {denominator}"
            confirm_message += "\n\n¿Quieres continuar?"

            reply = QMessageBox.question(
                self,
                "Confirmar DELETE",
                confirm_message,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            data = self._delete_request(entity, item_id, denominator)
            self.last_result_data = data

            self.results_output.setPlainText(
                json.dumps(data, indent=2, ensure_ascii=False)
            )

            QMessageBox.information(self, "DELETE ejecutado", "La operación DELETE se ha ejecutado.")

        except Exception as e:
            QMessageBox.critical(self, "Error ejecutando DELETE", str(e))

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
        default_name = f"{entity}_delete_result.json"

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