"""Pestaña universal para copiar ficheros por una lista TXT."""

import os
from typing import List

from PySide6.QtCore import Qt, QSettings, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.general_file_operations import (
    copy_general_items,
    normalize_base_name,
    parse_general_txt_list,
    scan_general_items,
)
from src.ui.widgets import FileSelector, FolderSelector


class UniversalCopyWorker(QThread):
    """Copia ficheros/carpetas de cualquier sistema sin bloquear la UI."""

    progress = Signal(int, int)
    status = Signal(str)
    finished_copy = Signal(int, int, int, list)
    error = Signal(str)

    def __init__(self, source_dir: str, requested_names: List[str], dest_dir: str,
                 recursive: bool, parent=None):
        super().__init__(parent)
        self.source_dir = source_dir
        self.requested_names = requested_names
        self.dest_dir = dest_dir
        self.recursive = recursive
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            self.status.emit(f"Copiando {len(self.requested_names)} entradas de la lista...")
            found, copied, missing_count, missing = copy_general_items(
                self.source_dir,
                self.requested_names,
                self.dest_dir,
                recursive=self.recursive,
                progress_callback=lambda cur, total: (
                    self.progress.emit(cur, total)
                    if not self._cancelled else None
                ),
                should_cancel=lambda: self._cancelled,
            )

            if self._cancelled:
                self.status.emit("Copia universal cancelada por el usuario.")
            else:
                self.status.emit(
                    f"Completado: {found} entradas encontradas, "
                    f"{copied} elementos copiados, {missing_count} no encontradas."
                )

            self.finished_copy.emit(found, copied, missing_count, missing)
        except Exception as exc:
            self.error.emit(f"Error en copia universal: {exc}")
            self.finished_copy.emit(0, 0, 0, [])


class UniversalExtractorTab(QWidget):
    """Copia cualquier archivo/carpeta cuyo nombre base aparezca en un TXT."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.requested_names: List[str] = []
        self._last_missing_names: List[str] = []
        self.settings = QSettings("MameSysExtractor", "UniversalExtractor")

        self._init_ui()
        self.load_settings()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        config_group = QGroupBox("Configuración")
        config_layout = QVBoxLayout(config_group)

        self.source_folder = FolderSelector("Origen:")
        self.source_folder.path_changed.connect(self.save_settings)
        config_layout.addWidget(self.source_folder)

        self.txt_file = FileSelector(
            "Lista TXT:",
            "Listas de texto (*.txt);;Todos (*.*)",
        )
        self.txt_file.path_changed.connect(self.save_settings)
        config_layout.addWidget(self.txt_file)

        self.dest_folder = FolderSelector("Destino:")
        self.dest_folder.path_changed.connect(self.save_settings)
        config_layout.addWidget(self.dest_folder)

        options_row = QHBoxLayout()
        self.recursive_cb = QCheckBox("Buscar también en subcarpetas")
        self.recursive_cb.setToolTip(
            "Si se activa, se buscan coincidencias dentro de todas las subcarpetas "
            "y se conserva la estructura relativa al copiar."
        )
        self.recursive_cb.toggled.connect(self.save_settings)
        options_row.addWidget(self.recursive_cb)
        options_row.addStretch()

        self.load_btn = QPushButton("Analizar TXT")
        self.load_btn.clicked.connect(self._load_txt_list)
        self.load_btn.setMinimumHeight(32)
        options_row.addWidget(self.load_btn)
        config_layout.addLayout(options_row)

        layout.addWidget(config_group)

        splitter = QSplitter(Qt.Horizontal)

        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(8)

        guide_group = QGroupBox("Cómo funciona")
        guide_layout = QVBoxLayout(guide_group)
        guide_text = QLabel(
            "Usa esta pestaña para cualquier sistema retro o colección de ficheros. "
            "El TXT debe tener un nombre por línea y sin extensión. Por ejemplo, "
            "si el archivo es 'sonic 2 (usa).zip', en el TXT escribe: sonic 2 (usa)."
        )
        guide_text.setWordWrap(True)
        guide_layout.addWidget(guide_text)
        info_layout.addWidget(guide_group)

        summary_group = QGroupBox("Resumen")
        summary_layout = QVBoxLayout(summary_group)
        self.summary_label = QLabel("Carga un TXT para ver cuántos ficheros coinciden.")
        self.summary_label.setWordWrap(True)
        summary_layout.addWidget(self.summary_label)
        info_layout.addWidget(summary_group)

        sample_group = QGroupBox("Ejemplo de TXT")
        sample_layout = QVBoxLayout(sample_group)
        sample = QTextEdit()
        sample.setReadOnly(True)
        sample.setMaximumHeight(120)
        sample.setPlainText("sonic 2 (usa)\nAnother World (Europe)\nDoom Shareware v1.9")
        sample_layout.addWidget(sample)
        info_layout.addWidget(sample_group)
        info_layout.addStretch()
        splitter.addWidget(info_widget)

        activity_widget = QWidget()
        activity_layout = QVBoxLayout(activity_widget)
        activity_layout.setContentsMargins(0, 0, 0, 0)
        activity_layout.setSpacing(8)

        exec_group = QGroupBox("Ejecución")
        exec_layout = QVBoxLayout(exec_group)
        btn_row = QHBoxLayout()

        self.copy_btn = QPushButton("Copiar ficheros a destino")
        self.copy_btn.setObjectName("primaryButton")
        self.copy_btn.clicked.connect(self._start_copy)
        self.copy_btn.setMinimumHeight(36)
        self.copy_btn.setEnabled(False)
        btn_row.addWidget(self.copy_btn)

        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.setObjectName("dangerButton")
        self.cancel_btn.clicked.connect(self._cancel_copy)
        self.cancel_btn.setMinimumHeight(36)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setVisible(False)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addStretch()
        exec_layout.addLayout(btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        exec_layout.addWidget(self.progress_bar)

        self.export_missing_btn = QPushButton("Guardar lista de no encontrados")
        self.export_missing_btn.clicked.connect(self._export_missing_names)
        self.export_missing_btn.setVisible(False)
        exec_layout.addWidget(self.export_missing_btn)
        activity_layout.addWidget(exec_group)

        log_group = QGroupBox("Registro")
        log_layout = QVBoxLayout(log_group)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Aquí aparecerá el análisis y la copia universal.")
        log_layout.addWidget(self.log_output)
        activity_layout.addWidget(log_group, 1)
        splitter.addWidget(activity_widget)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([760, 430])
        layout.addWidget(splitter, 1)

    def load_settings(self):
        self.source_folder.set_text(self.settings.value("source_folder", ""))
        self.txt_file.set_text(self.settings.value("txt_file", ""))
        self.dest_folder.set_text(self.settings.value("dest_folder", ""))
        self.recursive_cb.setChecked(self.settings.value("recursive", False, type=bool))

    def save_settings(self):
        self.settings.setValue("source_folder", self.source_folder.text())
        self.settings.setValue("txt_file", self.txt_file.text())
        self.settings.setValue("dest_folder", self.dest_folder.text())
        self.settings.setValue("recursive", self.recursive_cb.isChecked())

    def _load_txt_list(self):
        filepath = self.txt_file.text()
        if not filepath:
            QMessageBox.warning(self, "Error", "Selecciona un archivo TXT primero.")
            return
        if not os.path.isfile(filepath):
            QMessageBox.warning(self, "Error", f"No se encontró el archivo:\n{filepath}")
            return

        try:
            self.requested_names = parse_general_txt_list(filepath)
            self._last_missing_names = []
            self.export_missing_btn.setVisible(False)
            self._log(f"Cargando TXT: {filepath}")
            self._log(f"  -> {len(self.requested_names)} nombres únicos encontrados.")

            if not self.requested_names:
                self.summary_label.setText("El TXT no contiene nombres válidos.")
                self.copy_btn.setEnabled(False)
                return

            self._update_match_summary()
            self.copy_btn.setEnabled(True)
            self.save_settings()
        except Exception as exc:
            self._log(f"ERROR: {exc}")
            QMessageBox.critical(self, "Error", f"Error al cargar el TXT:\n{exc}")

    def _update_match_summary(self):
        source_dir = self.source_folder.text()
        if not source_dir or not os.path.isdir(source_dir):
            self.summary_label.setText(
                f"Lista cargada: {len(self.requested_names)} nombres. "
                "Selecciona una carpeta origen válida para comprobar coincidencias."
            )
            return

        index = scan_general_items(source_dir, recursive=self.recursive_cb.isChecked())
        found = 0
        copyable = 0
        for name in self.requested_names:
            candidates = index.get(normalize_base_name(name), [])
            if candidates:
                found += 1
                copyable += len(candidates)

        missing = len(self.requested_names) - found
        self.summary_label.setText(
            f"Lista: {len(self.requested_names)} nombres | "
            f"Encontrados: {found} | "
            f"Elementos copiables: {copyable} | "
            f"No encontrados: {missing}"
        )
        self._log(
            f"  -> Encontrados: {found}; elementos copiables: {copyable}; "
            f"no encontrados: {missing}."
        )

    def _start_copy(self):
        source_dir = self.source_folder.text()
        dest_dir = self.dest_folder.text()

        if not source_dir or not os.path.isdir(source_dir):
            QMessageBox.warning(self, "Error", "Selecciona una carpeta origen válida.")
            return
        if not dest_dir:
            QMessageBox.warning(self, "Error", "Selecciona una carpeta de destino.")
            return
        if not self.requested_names:
            QMessageBox.warning(self, "Error", "Carga un TXT primero.")
            return

        self._log(f"\n--- Copia universal: {len(self.requested_names)} nombres ---")
        self._log(f"  Origen: {source_dir}")
        self._log(f"  Destino: {dest_dir}")
        self._log(f"  Subcarpetas: {'sí' if self.recursive_cb.isChecked() else 'no'}")

        self.copy_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.requested_names))
        self.progress_bar.setValue(0)
        self.export_missing_btn.setVisible(False)
        self._last_missing_names = []

        self.worker = UniversalCopyWorker(
            source_dir,
            self.requested_names,
            dest_dir,
            self.recursive_cb.isChecked(),
            self,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.status.connect(self._log)
        self.worker.finished_copy.connect(self._on_finished)
        self.worker.error.connect(lambda e: (
            self._log(f"ERROR: {e}"),
            QMessageBox.critical(self, "Error", e)
        ))
        self.worker.start()
        self.save_settings()

    def _cancel_copy(self):
        if hasattr(self, "worker") and self.worker.isRunning():
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)
            self._log("Cancelando copia universal...")

    def _on_progress(self, current: int, total: int):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    def _on_finished(self, found: int, copied: int, missing_count: int, missing: list):
        self.copy_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self._last_missing_names = missing

        msg = (
            f"Copia universal completada: {found} nombres encontrados, "
            f"{copied} elementos copiados"
        )
        if missing_count:
            msg += f", {missing_count} no encontrados"
            self.export_missing_btn.setVisible(True)
        self._log(msg)
        self.summary_label.setText(msg)

        if copied > 0:
            QMessageBox.information(self, "Completado", msg)

    def _export_missing_names(self):
        if not self._last_missing_names:
            QMessageBox.information(self, "Sin datos", "No hay nombres no encontrados para exportar.")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar nombres no encontrados",
            "nombres_no_encontrados.txt",
            "Archivos de texto (*.txt);;Todos (*.*)",
        )
        if not filepath:
            return

        try:
            with open(filepath, "w", encoding="utf-8") as file:
                file.write("# Nombres no encontrados\n")
                file.write(f"# Total: {len(self._last_missing_names)}\n\n")
                for name in self._last_missing_names:
                    file.write(f"{name}\n")
            self._log(f"  -> Lista guardada en: {filepath}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Error al guardar:\n{exc}")

    def _log(self, message: str):
        self.log_output.append(message)
