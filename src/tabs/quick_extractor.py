"""Pestaña de extracción rápida con listas de sistemas integradas."""

import os
from typing import Dict, List, Set

from PySide6.QtCore import Qt, QSettings, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.rom_operations import copy_roms, scan_roms
from src.data.quick_systems import MAME_LIST_VERSION, QUICK_SYSTEMS
from src.ui.widgets import FolderSelector


class QuickExtractWorker(QThread):
    """Copia un sistema integrado sin bloquear la interfaz."""

    progress = Signal(int, int)
    status = Signal(str)
    finished_extract = Signal(int, int, list)
    error = Signal(str)

    def __init__(self, source_dir: str, rom_names: Set[str], dest_dir: str, parent=None):
        super().__init__(parent)
        self.source_dir = source_dir
        self.rom_names = rom_names
        self.dest_dir = dest_dir
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            copied, missing, not_found = copy_roms(
                self.source_dir,
                self.rom_names,
                self.dest_dir,
                progress_callback=self.progress.emit,
                should_cancel=lambda: self._cancelled,
            )
            self.finished_extract.emit(copied, missing, not_found)
        except Exception as exc:
            self.error.emit(f"Error durante la extracción: {exc}")
            self.finished_extract.emit(0, 0, [])


class QuickSystemCard(QFrame):
    """Tarjeta compacta para un sistema integrado."""

    extract_requested = Signal(str)

    def __init__(self, system_key: str, system_data: dict, parent=None):
        super().__init__(parent)
        self.system_key = system_key
        self.setObjectName("systemCard")
        self.setMinimumWidth(255)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(7)

        title_row = QHBoxLayout()
        title = QLabel(system_data["label"])
        title.setObjectName("cardTitle")
        title_row.addWidget(title)
        title_row.addStretch()

        self.total_label = QLabel(f'{len(system_data["roms"])} sets')
        self.total_label.setObjectName("countBadge")
        title_row.addWidget(self.total_label)
        layout.addLayout(title_row)

        description = QLabel(system_data["description"])
        description.setWordWrap(True)
        description.setObjectName("mutedLabel")
        layout.addWidget(description)

        self.available_label = QLabel("Disponibilidad sin analizar")
        self.available_label.setObjectName("availabilityLabel")
        layout.addWidget(self.available_label)

        self.extract_btn = QPushButton("Extraer ahora")
        self.extract_btn.setObjectName("primaryButton")
        self.extract_btn.setMinimumHeight(34)
        self.extract_btn.clicked.connect(
            lambda: self.extract_requested.emit(self.system_key)
        )
        layout.addWidget(self.extract_btn)

    def set_available(self, available: int, total: int):
        self.available_label.setText(f"{available} de {total} sets presentes en origen")

    def reset_available(self):
        self.available_label.setText("Disponibilidad sin analizar")

    def set_busy(self, busy: bool):
        self.extract_btn.setEnabled(not busy)


class QuickExtractorTab(QWidget):
    """Extracción directa de sistemas conocidos con un solo botón."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("MameSysExtractor", "QuickExtractor")
        self.roms_in_source: Set[str] = set()
        self.cards: Dict[str, QuickSystemCard] = {}
        self._last_missing_roms: List[str] = []
        self._active_system_key = ""

        self._init_ui()
        self.load_settings()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        config_group = QGroupBox("Carpetas de trabajo")
        config_layout = QVBoxLayout(config_group)
        config_layout.setSpacing(7)

        self.source_folder = FolderSelector("ROMs origen:")
        self.source_folder.path_changed.connect(self._on_source_changed)
        config_layout.addWidget(self.source_folder)

        self.dest_folder = FolderSelector("Carpeta destino:")
        self.dest_folder.path_changed.connect(self.save_settings)
        config_layout.addWidget(self.dest_folder)

        scan_row = QHBoxLayout()
        self.scan_btn = QPushButton("Actualizar disponibilidad")
        self.scan_btn.setObjectName("secondaryButton")
        self.scan_btn.clicked.connect(self._scan_source)
        scan_row.addWidget(self.scan_btn)
        scan_row.addStretch()

        version_label = QLabel(f"Listas integradas basadas en MAME {MAME_LIST_VERSION}")
        version_label.setObjectName("mutedLabel")
        scan_row.addWidget(version_label)
        config_layout.addLayout(scan_row)
        layout.addWidget(config_group)

        splitter = QSplitter(Qt.Horizontal)

        systems_group = QGroupBox("Sistemas rápidos")
        systems_layout = QVBoxLayout(systems_group)
        systems_layout.setContentsMargins(10, 16, 10, 10)

        hint = QLabel(
            "Pulsa un sistema para copiar todos sus sets disponibles a una "
            "subcarpeta propia. Se incluyen ZIP, 7Z y carpetas CHD."
        )
        hint.setWordWrap(True)
        hint.setObjectName("mutedLabel")
        systems_layout.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        card_container = QWidget()
        card_grid = QGridLayout(card_container)
        card_grid.setContentsMargins(2, 4, 2, 2)
        card_grid.setHorizontalSpacing(10)
        card_grid.setVerticalSpacing(10)

        for index, (system_key, system_data) in enumerate(QUICK_SYSTEMS.items()):
            card = QuickSystemCard(system_key, system_data)
            card.extract_requested.connect(self._start_extraction)
            self.cards[system_key] = card
            card_grid.addWidget(card, index // 2, index % 2)

        card_grid.setRowStretch((len(QUICK_SYSTEMS) + 1) // 2, 1)
        scroll.setWidget(card_container)
        systems_layout.addWidget(scroll)
        splitter.addWidget(systems_group)

        activity_group = QGroupBox("Actividad")
        activity_layout = QVBoxLayout(activity_group)

        self.status_label = QLabel(
            "Selecciona las carpetas y pulsa un sistema para comenzar."
        )
        self.status_label.setWordWrap(True)
        activity_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        activity_layout.addWidget(self.progress_bar)

        action_row = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.setObjectName("dangerButton")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel_extraction)
        action_row.addWidget(self.cancel_btn)

        self.export_missing_btn = QPushButton("Guardar no encontradas")
        self.export_missing_btn.setVisible(False)
        self.export_missing_btn.clicked.connect(self._export_missing_roms)
        action_row.addWidget(self.export_missing_btn)
        action_row.addStretch()
        activity_layout.addLayout(action_row)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Aquí aparecerá el registro de extracción.")
        activity_layout.addWidget(self.log_output, 1)
        splitter.addWidget(activity_group)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([760, 430])
        layout.addWidget(splitter, 1)

    def load_settings(self):
        self.source_folder.set_text(self.settings.value("source_folder", ""))
        self.dest_folder.set_text(self.settings.value("dest_folder", ""))

    def save_settings(self):
        self.settings.setValue("source_folder", self.source_folder.text())
        self.settings.setValue("dest_folder", self.dest_folder.text())

    def _on_source_changed(self):
        self.roms_in_source = set()
        for card in self.cards.values():
            card.reset_available()
        self.save_settings()

    def _scan_source(self) -> bool:
        source_dir = self.source_folder.text()
        if not source_dir or not os.path.isdir(source_dir):
            QMessageBox.warning(self, "Carpeta no válida", "Selecciona una carpeta de ROMs origen válida.")
            return False

        self.status_label.setText("Analizando la carpeta de origen...")
        self.roms_in_source = scan_roms(source_dir)
        for system_key, card in self.cards.items():
            roms = QUICK_SYSTEMS[system_key]["roms"]
            card.set_available(len(roms & self.roms_in_source), len(roms))

        self.status_label.setText(
            f"Origen analizado: {len(self.roms_in_source)} sets disponibles."
        )
        self._log(f"Origen analizado: {source_dir} ({len(self.roms_in_source)} sets)")
        self.save_settings()
        return True

    def _start_extraction(self, system_key: str):
        source_dir = self.source_folder.text()
        dest_base = self.dest_folder.text()
        if not source_dir or not os.path.isdir(source_dir):
            QMessageBox.warning(self, "Carpeta no válida", "Selecciona una carpeta de ROMs origen válida.")
            return
        if not dest_base:
            QMessageBox.warning(self, "Destino pendiente", "Selecciona una carpeta de destino.")
            return
        if not self.roms_in_source and not self._scan_source():
            return

        system_data = QUICK_SYSTEMS[system_key]
        available = set(system_data["roms"]) & self.roms_in_source
        if not available:
            QMessageBox.information(
                self,
                "Sin coincidencias",
                f'No se encontraron sets de {system_data["label"]} en la carpeta origen.',
            )
            return

        self._active_system_key = system_key
        dest_dir = os.path.join(dest_base, system_data["folder"])
        self._last_missing_roms = []
        self.export_missing_btn.setVisible(False)
        self._set_busy(True)

        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(available))
        self.progress_bar.setValue(0)
        self.status_label.setText(
            f'Extrayendo {len(available)} sets de {system_data["label"]}...'
        )
        self._log(f'\n--- {system_data["label"]}: {len(available)} sets -> {dest_dir} ---')

        self.worker = QuickExtractWorker(source_dir, available, dest_dir, self)
        self.worker.progress.connect(self._on_progress)
        self.worker.error.connect(self._on_error)
        self.worker.finished_extract.connect(self._on_finished)
        self.worker.start()
        self.save_settings()

    def _set_busy(self, busy: bool):
        self.scan_btn.setEnabled(not busy)
        self.cancel_btn.setVisible(busy)
        for card in self.cards.values():
            card.set_busy(busy)

    def _cancel_extraction(self):
        if hasattr(self, "worker") and self.worker.isRunning():
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)
            self.status_label.setText("Cancelando extracción...")

    def _on_progress(self, current: int, total: int):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    def _on_error(self, message: str):
        self._log(message)
        QMessageBox.critical(self, "Error", message)

    def _on_finished(self, copied: int, missing: int, not_found: list):
        was_cancelled = hasattr(self, "worker") and self.worker._cancelled
        self._set_busy(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self._last_missing_roms = not_found
        self.export_missing_btn.setVisible(bool(not_found))

        label = QUICK_SYSTEMS[self._active_system_key]["label"]
        if was_cancelled:
            message = f"Extracción de {label} cancelada. {copied} sets copiados."
        else:
            message = f"{label}: {copied} sets copiados."
            if missing:
                message += f" {missing} no encontrados."
        self.status_label.setText(message)
        self._log(message)
        if copied and not was_cancelled:
            QMessageBox.information(self, "Extracción completada", message)

    def _export_missing_roms(self):
        if not self._last_missing_roms:
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar lista de ROMs no encontradas",
            "roms_no_encontradas.txt",
            "Archivos de texto (*.txt);;Todos (*.*)",
        )
        if filepath:
            with open(filepath, "w", encoding="utf-8") as file:
                file.write("\n".join(sorted(self._last_missing_roms)) + "\n")
            self._log(f"Lista de no encontradas guardada en: {filepath}")

    def _log(self, message: str):
        self.log_output.append(message)
