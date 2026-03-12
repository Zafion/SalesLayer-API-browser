import json
from pathlib import Path
from urllib.parse import quote

import requests

from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QTextEdit, QSizePolicy, QMessageBox, QFileDialog, QLineEdit,
    QScrollArea, QFormLayout, QSplitter
)
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import Qt

from api_client import SalesLayerApiClient
from metadata_parser import extract_properties_from_metadata


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

ASSET_CUSTOM_TYPES = {"image_pack", "file"}
BASE_URL = "https://api2.saleslayer.com/rest/Catalog"


class PostTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        self.client = None
        self.current_properties = []
        self.current_postable_properties = []
        self.custom_entities_tables = []
        self.last_payload = None
        self.last_result_data = None

        self.is_loading_metadata = False
        self.is_populating_custom_entities = False
        self.form_widgets = {}

        self.build_ui()
        self.on_entity_changed()

    def build_ui(self):
        root_layout = QVBoxLayout()

        main_splitter = QSplitter(Qt.Vertical)

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

        controls_layout.addWidget(QLabel("Idioma:"))
        self.language_selector = QComboBox()
        self.language_selector.addItems(["es", "en", "fr", "de", "it", "pt", "pl", "es-mx", "zh", "en-gi"])
        self.language_selector.setCurrentText("es")
        controls_layout.addWidget(self.language_selector)

        self.load_metadata_button = QPushButton("Load Metadata")
        self.load_metadata_button.clicked.connect(self.load_metadata)
        controls_layout.addWidget(self.load_metadata_button)

        self.generate_payload_button = QPushButton("Generate Payload")
        self.generate_payload_button.clicked.connect(self.generate_payload)
        controls_layout.addWidget(self.generate_payload_button)

        self.run_post_button = QPushButton("Run POST")
        self.run_post_button.clicked.connect(self.run_post)
        controls_layout.addWidget(self.run_post_button)

        top_layout.addLayout(controls_layout)

        self.form_info = QTextEdit()
        self.form_info.setReadOnly(True)
        self.form_info.setMaximumHeight(140)
        self.form_info.setPlainText(
            "Carga metadata para generar el formulario POST.\n"
            "Products usa overlay específico.\n"
            "Categories y Variants soportan campos simples, multiidioma JSON e imágenes/archivos."
        )
        top_layout.addWidget(self.form_info)

        top_layout.addWidget(QLabel("Formulario POST"))

        self.form_container = QWidget()
        self.form_layout = QFormLayout()
        self.form_container.setLayout(self.form_layout)

        self.form_scroll = QScrollArea()
        self.form_scroll.setWidgetResizable(True)
        self.form_scroll.setWidget(self.form_container)
        self.form_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        top_layout.addWidget(self.form_scroll, 1)

        top_widget.setLayout(top_layout)

        bottom_splitter = QSplitter(Qt.Horizontal)

        result_widget = QWidget()
        result_layout = QVBoxLayout()
        result_layout.setContentsMargins(0, 0, 0, 0)

        results_header = QHBoxLayout()
        results_header.addWidget(QLabel("Resultado POST"))

        self.copy_json_button = QPushButton("Copy JSON")
        self.copy_json_button.clicked.connect(self.copy_json)
        results_header.addWidget(self.copy_json_button)

        self.export_json_button = QPushButton("Export JSON")
        self.export_json_button.clicked.connect(self.export_json)
        results_header.addWidget(self.export_json_button)

        results_header.addStretch()
        result_layout.addLayout(results_header)

        self.results_output = QTextEdit()
        self.results_output.setReadOnly(True)
        result_layout.addWidget(self.results_output)

        result_widget.setLayout(result_layout)

        payload_widget = QWidget()
        payload_layout = QVBoxLayout()
        payload_layout.setContentsMargins(0, 0, 0, 0)

        payload_layout.addWidget(QLabel("Payload preview"))
        self.payload_preview = QTextEdit()
        self.payload_preview.setReadOnly(True)
        payload_layout.addWidget(self.payload_preview)

        payload_widget.setLayout(payload_layout)

        bottom_splitter.addWidget(result_widget)
        bottom_splitter.addWidget(payload_widget)
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

    def _request_headers(self, accept_language: str | None = None) -> dict:
        api_key = self.main_window.get_api_key()
        headers = {
            "X-API-KEY": api_key,
            "Accept": "*/*",
            "Content-Type": "application/json",
            "User-Agent": "SalesLayerApiBrowser/0.1",
        }
        if accept_language:
            headers["Accept-Language"] = accept_language
        return headers

    def _post_request(self, entity: str, payload: dict, denominator: str | None = None) -> dict:
        if entity == "CustomEntities":
            if not denominator:
                raise ValueError("Debes seleccionar una tabla de Custom Entity.")
            encoded = quote(denominator, safe="")
            url = f"{BASE_URL}/CustomEntities('{encoded}')"
        else:
            url = f"{BASE_URL}/{entity}"

        response = requests.post(
            url,
            headers=self._request_headers(self.language_selector.currentText().strip()),
            json=payload,
            timeout=30
        )

        if not response.ok:
            detail = response.text.strip()
            if detail:
                raise ValueError(
                    f"{response.status_code} Client Error for url: {url}\n\nRespuesta API:\n{detail}"
                )
            response.raise_for_status()

        if not response.text.strip():
            return {"status_code": response.status_code, "message": "Empty response body"}

        try:
            return response.json()
        except ValueError:
            return {
                "status_code": response.status_code,
                "raw_response": response.text
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

    def get_selected_custom_entity_metadata_denominator(self):
        data = self.custom_entity_selector.currentData()
        if isinstance(data, dict):
            return data.get("display_denominator")
        return data

    def get_selected_custom_entity_post_denominator(self):
        # En este tenant, Swagger confirma que create usa el visible
        return self.get_selected_custom_entity_metadata_denominator()

    def get_selected_custom_entity_denominator(self):
        return self.get_selected_custom_entity_metadata_denominator()

    def load_custom_entities_tables(self, force_refresh: bool = False):
        previous_selection = self.get_selected_custom_entity_metadata_denominator()

        if self.custom_entity_selector.count() > 0 and not force_refresh:
            return

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

        self.is_populating_custom_entities = True
        try:
            self.custom_entity_selector.clear()

            for table in self.custom_entities_tables:
                label = f"CustomEntities('{table['display_denominator']}')"
                self.custom_entity_selector.addItem(label, table)

            if previous_selection:
                for index in range(self.custom_entity_selector.count()):
                    data = self.custom_entity_selector.itemData(index)
                    if isinstance(data, dict) and data.get("display_denominator") == previous_selection:
                        self.custom_entity_selector.setCurrentIndex(index)
                        break
        finally:
            self.is_populating_custom_entities = False

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

    def clear_form(self):
        while self.form_layout.rowCount():
            self.form_layout.removeRow(0)
        self.form_widgets = {}

    def _create_input_widget_for_property(self, prop: dict):
        special_kind = prop.get("special_kind")
        field_type = prop.get("type", "")

        if special_kind == "status":
            widget = QComboBox()
            widget.addItem("", None)
            enum_values = prop.get("enum_values") or ["V", "I", "D", "R", "v", "i", "d", "r"]
            seen = set()
            for value in enum_values:
                if value in seen:
                    continue
                seen.add(value)
                widget.addItem(str(value), value)
            return {
                "widget_type": "status",
                "widget": widget,
            }

        if special_kind == "multilang_json":
            widget = QTextEdit()
            widget.setMaximumHeight(90)
            widget.setPlaceholderText('Ejemplo: {"es":"Texto","en":"Text"}')
            return {
                "widget_type": "multilang_json",
                "widget": widget,
            }

        if special_kind == "asset_ref":
            widget = QLineEdit()
            widget.setPlaceholderText("Nombre del fichero ya existente en el PIM")
            return {
                "widget_type": "asset_ref",
                "widget": widget,
            }

        if field_type in {"boolean", "boolean | null"}:
            widget = QComboBox()
            widget.addItem("", None)
            widget.addItem("true", True)
            widget.addItem("false", False)
            return {
                "widget_type": "boolean",
                "widget": widget,
            }

        widget = QLineEdit()
        if field_type in {"integer", "integer | null"}:
            widget.setPlaceholderText("Introduce un número entero")
        elif field_type in {"number", "number | null"}:
            widget.setPlaceholderText("Introduce un número decimal")
        else:
            widget.setPlaceholderText("Introduce un valor")

        return {
            "widget_type": "simple",
            "widget": widget,
        }

    def _get_products_post_overlay_fields(self):
        return [
            {
                "name": "prod_title",
                "title": "Name",
                "type": "string",
                "required": True,
                "custom_type": "short_text",
                "postable": True,
            },
            {
                "name": "prod_description",
                "title": "Description",
                "type": "string | null",
                "required": False,
                "custom_type": "long_text",
                "postable": True,
            },
            {
                "name": "prod_image",
                "title": "Image",
                "type": "string | null",
                "required": False,
                "custom_type": "image",
                "postable": True,
                "special_kind": "asset_ref",
            },
            {
                "name": "prod_stat",
                "title": "Status",
                "type": "string | null",
                "required": False,
                "custom_type": "status",
                "postable": True,
                "special_kind": "status",
                "enum_values": ["V", "I", "D", "R", "v", "i", "d", "r"],
            },
            {
                "name": "cat_id",
                "title": "Category ID",
                "type": "integer | null",
                "required": False,
                "custom_type": "",
                "postable": True,
            },
            {
                "name": "typ_id",
                "title": "Attribute Set ID",
                "type": "integer | null",
                "required": False,
                "custom_type": "",
                "postable": True,
            },
        ]

    def _get_product_post_fields(self, properties: list[dict]) -> list[dict]:
        excluded = {
            "prod_id",
            "prod_clone_id",
            "prod_modify",
            "prod_creation",
            "cat_ref",
        }

        post_fields = [
            prop for prop in properties
            if prop["type"] in SIMPLE_TYPES
            and prop["name"] not in excluded
            and prop["name"] not in {"prod_title", "prod_description", "prod_image", "prod_stat", "cat_id", "typ_id"}
        ]

        existing_names = {prop["name"] for prop in post_fields}

        for overlay in self._get_products_post_overlay_fields():
            if overlay["name"] not in existing_names:
                post_fields.append(overlay)

        order_priority = {
            "prod_ref": 1,
            "prod_title": 2,
            "prod_description": 3,
            "prod_image": 4,
            "prod_stat": 5,
            "cat_id": 6,
            "typ_id": 7,
        }

        post_fields.sort(key=lambda x: (order_priority.get(x["name"], 999), x["name"]))
        return post_fields

    def _get_category_post_fields(self, properties: list[dict]) -> list[dict]:
        fields = []
        names = set()

        def add_field(prop):
            if prop["name"] in names:
                return
            names.add(prop["name"])
            fields.append(prop)

        excluded = {
            "cat_id",
            "cat_parent_ref",
            "cat_parent_path",
            "cat_creation",
            "cat_modify",
        }

        for prop in properties:
            if prop["name"] in excluded:
                continue

            if prop["name"] == "cat_ref":
                add_field({**prop, "required": True})
                continue

            if prop["type"] in SIMPLE_TYPES:
                if prop.get("custom_type") == "status":
                    prop = {**prop, "special_kind": "status"}
                add_field(prop)

            if str(prop.get("x_cultures", "")).lower() == "true":
                add_field({**prop, "special_kind": "multilang_json"})

            if prop.get("custom_type") in ASSET_CUSTOM_TYPES:
                add_field({
                    **prop,
                    "type": "string | null",
                    "special_kind": "asset_ref",
                })

        if "cat_parent_id" not in names:
            add_field({
                "name": "cat_parent_id",
                "title": "Parent Category ID",
                "type": "integer | null",
                "required": False,
                "custom_type": "",
                "postable": True,
            })

        order_priority = {
            "cat_ref": 1,
            "cat_title": 2,
            "cat_description": 3,
            "cat_image": 4,
            "cat_stat": 5,
            "cat_parent_id": 6,
            "cat_tags": 7,
        }

        fields.sort(key=lambda x: (order_priority.get(x["name"], 999), x["name"]))
        return fields

    def _get_variant_post_fields(self, properties: list[dict]) -> list[dict]:
        fields = []
        names = set()

        def add_field(prop):
            if prop["name"] in names:
                return
            names.add(prop["name"])
            fields.append(prop)

        add_field({
            "name": "prod_id",
            "title": "Product ID / Reference",
            "type": "string | null",
            "required": True,
            "custom_type": "",
            "postable": True,
        })

        excluded = {
            "prod_ref",
            "frmt_id",
            "frmt_modify",
            "frmt_creation",
            "frmt_stat",
        }

        for prop in properties:
            if prop["name"] in excluded:
                continue

            if prop["type"] in SIMPLE_TYPES:
                add_field(prop)

            if str(prop.get("x_cultures", "")).lower() == "true":
                add_field({**prop, "special_kind": "multilang_json"})

            if prop.get("custom_type") in ASSET_CUSTOM_TYPES:
                add_field({
                    **prop,
                    "type": "string | null",
                    "special_kind": "asset_ref",
                })

        order_priority = {
            "prod_id": 1,
            "frmt_ref": 2,
        }

        fields.sort(key=lambda x: (order_priority.get(x["name"], 999), x["name"]))
        return fields

    def _get_custom_entity_post_fields(self, properties: list[dict]) -> list[dict]:
        fields = []
        names = set()

        def add_field(prop):
            if prop["name"] in names:
                return
            names.add(prop["name"])
            fields.append(prop)

        for prop in properties:
            name_lower = prop["name"].lower()

            if name_lower.endswith("_creation"):
                continue
            if name_lower.endswith("_modify"):
                continue
            if name_lower.endswith("_id"):
                continue

            if prop["type"] in SIMPLE_TYPES:
                if prop.get("custom_type") == "status":
                    prop = {**prop, "special_kind": "status"}
                add_field(prop)

            if str(prop.get("x_cultures", "")).lower() == "true":
                add_field({**prop, "special_kind": "multilang_json"})

            if prop.get("custom_type") in ASSET_CUSTOM_TYPES:
                add_field({
                    **prop,
                    "type": "string | null",
                    "special_kind": "asset_ref",
                })

        fields.sort(key=lambda x: x["name"])
        return fields

    def _get_post_fields_for_entity(self, entity: str, properties: list[dict]) -> list[dict]:
        if entity == "Products":
            return self._get_product_post_fields(properties)

        if entity == "Categories":
            return self._get_category_post_fields(properties)

        if entity == "Variants":
            return self._get_variant_post_fields(properties)

        if entity == "CustomEntities":
            return self._get_custom_entity_post_fields(properties)

        return [prop for prop in properties if prop["type"] in SIMPLE_TYPES]

    def build_form(self):
        self.clear_form()

        for prop in self.current_postable_properties:
            label_text = f'{prop["name"]} | {prop["title"]} | {prop["type"]}'
            if prop.get("required"):
                label_text += " | required"

            special_kind = prop.get("special_kind")
            if special_kind == "multilang_json":
                label_text += " | multi-language JSON"
            elif special_kind == "asset_ref":
                label_text += " | existing file/image"
            elif special_kind == "status":
                label_text += " | status"

            widget_info = self._create_input_widget_for_property(prop)
            self.form_layout.addRow(QLabel(label_text), widget_info["widget"])
            self.form_widgets[prop["name"]] = {
                **widget_info,
                "property": prop,
            }

        if not self.current_postable_properties:
            self.form_layout.addRow(QLabel("No hay campos disponibles para POST en esta entidad."))

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
            self.current_postable_properties = self._get_post_fields_for_entity(entity, properties)

            self.build_form()
            self.payload_preview.clear()
            self.results_output.clear()
            self.last_payload = None
            self.last_result_data = None

            info_lines = [
                f"Campos disponibles para POST: {len(self.current_postable_properties)}"
            ]

            if entity == "Products":
                info_lines.append("Products usa overlay específico con strings simples y Accept-Language.")
                info_lines.append("prod_image debe apuntar a un fichero ya existente en el PIM.")
            elif entity == "Categories":
                info_lines.append("Categories admite multiidioma JSON y campos de imagen/archivo.")
                info_lines.append('Ejemplo multiidioma: {"es":"Título","en":"Title"}')
                info_lines.append("cat_image debe apuntar a un fichero ya existente en el PIM.")
            elif entity == "Variants":
                info_lines.append("Variants fuerza prod_id y admite campos de imagen/archivo y multiidioma detectados por metadata.")
                info_lines.append('Para campos multiidioma usa JSON como {"es":"Texto","en":"Text"}')
            elif entity == "CustomEntities":
                info_lines.append(f"Tabla metadata/read: {self.get_selected_custom_entity_metadata_denominator()}")
                info_lines.append(f"Tabla create/post: {self.get_selected_custom_entity_post_denominator()}")

            self.form_info.setPlainText("\n".join(info_lines))

            QMessageBox.information(
                self,
                "Metadata cargada",
                f"Se han preparado {len(self.current_postable_properties)} campos para POST."
            )

        except Exception as e:
            QMessageBox.critical(self, "Error cargando metadata", str(e))
        finally:
            self.is_loading_metadata = False

    def _read_widget_value(self, widget_info: dict):
        prop = widget_info["property"]
        field_type = prop.get("type", "")
        widget_type = widget_info["widget_type"]

        if widget_type in {"boolean", "status"}:
            return widget_info["widget"].currentData()

        raw = widget_info["widget"].toPlainText().strip() if widget_type == "multilang_json" else widget_info["widget"].text().strip()

        if raw == "":
            return None

        if widget_type == "multilang_json":
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"El campo {prop['name']} debe contener un JSON válido. "
                    'Ejemplo: {"es":"Texto","en":"Text"}'
                ) from e

            if not isinstance(value, dict):
                raise ValueError(f"El campo {prop['name']} debe ser un objeto JSON por idioma.")

            cleaned = {}
            for lang, text in value.items():
                if text is None:
                    continue
                text_str = str(text).strip()
                if text_str != "":
                    cleaned[str(lang).strip()] = text_str

            if not cleaned:
                return None

            return cleaned

        if field_type in {"integer", "integer | null"}:
            try:
                return int(raw)
            except ValueError as e:
                raise ValueError(f"El campo {prop['name']} requiere un entero.") from e

        if field_type in {"number", "number | null"}:
            try:
                return float(raw.replace(",", "."))
            except ValueError as e:
                raise ValueError(f"El campo {prop['name']} requiere un número.") from e

        return raw

    def collect_payload(self) -> dict:
        payload = {}

        for field_name, widget_info in self.form_widgets.items():
            prop = widget_info["property"]
            value = self._read_widget_value(widget_info)

            if value is None:
                if prop.get("required"):
                    raise ValueError(f"El campo obligatorio {field_name} no puede estar vacío.")
                continue

            payload[field_name] = value

        return payload

    def generate_payload(self):
        try:
            payload = self.collect_payload()
            self.last_payload = payload
            self.payload_preview.setPlainText(
                json.dumps(payload, indent=2, ensure_ascii=False)
            )
        except Exception as e:
            QMessageBox.critical(self, "Error generando payload", str(e))

    def run_post(self):
        try:
            entity = self.entity_selector.currentText()

            payload = self.collect_payload()
            if not payload:
                raise ValueError("El payload está vacío. Introduce al menos un valor.")

            self.last_payload = payload
            self.payload_preview.setPlainText(
                json.dumps(payload, indent=2, ensure_ascii=False)
            )

            denominator = None
            if entity == "CustomEntities":
                denominator = self.get_selected_custom_entity_post_denominator()
                if not denominator:
                    raise ValueError("Debes seleccionar una tabla de Custom Entity.")

            data = self._post_request(entity, payload, denominator)
            self.last_result_data = data

            self.results_output.setPlainText(
                json.dumps(data, indent=2, ensure_ascii=False)
            )

        except Exception as e:
            QMessageBox.critical(self, "Error ejecutando POST", str(e))

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
        denominator = self.get_selected_custom_entity_post_denominator()

        if entity == "customentities" and denominator:
            safe_denominator = (
                denominator.replace("/", "_")
                .replace("\\", "_")
                .replace(" ", "_")
            )
            default_name = f"{entity}_{safe_denominator}_post_result.json"
        else:
            default_name = f"{entity}_post_result.json"

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