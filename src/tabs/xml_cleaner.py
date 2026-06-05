"""
Pestaña 2: Limpiador de ROMs con XML/lista.

Permite seleccionar un archivo con nombres de ROMs (XML o texto plano)
y copiar las ROMs que coincidan a una carpeta de destino configurable.
"""

import os
from typing import List, Set, Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QTextEdit, QProgressBar,
    QLabel, QMessageBox, QSplitter, QFileDialog,
    QCheckBox, QScrollArea, QSizePolicy,
)
from PySide6.QtCore import Qt, QThread, Signal, QSettings

from src.core.rom_operations import (
    scan_roms, copy_roms, parse_rom_list_file, parse_ini_categories
)
from src.ui.widgets import FolderSelector, FileSelector


class CleanWorker(QThread):
    """Worker thread para no bloquear la UI durante la limpieza."""
    
    progress = Signal(int, int)
    status = Signal(str)
    finished_clean = Signal(int, int, list)  # copiados, no_encontrados, lista_no_encontrados
    error = Signal(str)
    
    def __init__(self, source_dir: str, rom_names: Set[str],
                 dest_dir: str, parent=None):
        super().__init__(parent)
        self.source_dir = source_dir
        self.rom_names = rom_names
        self.dest_dir = dest_dir
        self._cancelled = False
    
    def cancel(self):
        """Cancela la limpieza en curso."""
        self._cancelled = True
    
    def run(self):
        try:
            self.status.emit(f"Copiando {len(self.rom_names)} ROMs seleccionadas...")
            
            # Crear directorio destino
            os.makedirs(self.dest_dir, exist_ok=True)
            
            copied, missing, not_found = copy_roms(
                self.source_dir,
                self.rom_names,
                self.dest_dir,
                progress_callback=lambda cur, tot: (
                    self.progress.emit(cur, tot)
                    if not self._cancelled else None
                ),
                should_cancel=lambda: self._cancelled,
            )
            
            if self._cancelled:
                self.status.emit("Limpieza cancelada por el usuario.")
            else:
                msg = f"Completado: {copied} ROMs copiadas"
                if missing:
                    msg += f", {missing} no encontradas en el origen."
                else:
                    msg += "."
                self.status.emit(msg)
            self.finished_clean.emit(copied, missing, not_found)
        
        except Exception as e:
            self.error.emit(f"Error en limpieza: {e}")
            self.finished_clean.emit(0, 0, [])


class XmlCleanerTab(QWidget):
    """Pestaña de limpieza de ROMs usando lista de nombres."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parsed_rom_names: Set[str] = set()
        self._last_missing_roms: List[str] = []
        self._stored_categories: Dict[str, List[str]] = {}
        self._category_checkboxes: List[QCheckBox] = []
        
        self.settings = QSettings("MameSysExtractor", "XmlCleaner")
        self._init_ui()
        self.load_settings()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # === Configuración ===
        config_group = QGroupBox("Configuración")
        config_layout = QVBoxLayout(config_group)
        
        self.source_folder = FolderSelector("ROMs origen:")
        config_layout.addWidget(self.source_folder)
        
        self.rom_list_file = FileSelector(
            "Lista ROMs (.xml/.txt/.ini):",
            "Archivos de lista (*.xml *.txt *.dat *.ini *.cfg);;XML (*.xml);;Texto (*.txt);;INI (*.ini *.cfg);;Todos (*.*)"
        )
        config_layout.addWidget(self.rom_list_file)
        
        # Carpeta destino
        self.dest_folder = FolderSelector("Carpeta destino:")
        self.dest_folder.path_changed.connect(self.save_settings)
        config_layout.addWidget(self.dest_folder)
        
        # Botón para cargar la lista
        load_row = QHBoxLayout()
        self.load_list_btn = QPushButton("📋 Cargar lista de ROMs")
        self.load_list_btn.clicked.connect(self._load_rom_list)
        self.load_list_btn.setMinimumHeight(32)
        load_row.addWidget(self.load_list_btn)
        load_row.addStretch()
        config_layout.addLayout(load_row)
        
        layout.addWidget(config_group)
        
        # === Selección de categorías (visible solo para .ini con categorías) ===
        self.categories_group = QGroupBox("📂 Categorías detectadas")
        self.categories_group.setVisible(False)
        cat_main_layout = QVBoxLayout(self.categories_group)
        
        # Scroll area para los checkboxes de categorías
        self.cat_scroll = QScrollArea()
        self.cat_scroll.setWidgetResizable(True)
        self.cat_scroll.setMaximumHeight(180)
        self.cat_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        self.cat_container = QWidget()
        self.cat_container_layout = QVBoxLayout(self.cat_container)
        self.cat_container_layout.setContentsMargins(4, 4, 4, 4)
        self.cat_container_layout.setSpacing(2)
        self.cat_container_layout.addStretch()
        self.cat_scroll.setWidget(self.cat_container)
        cat_main_layout.addWidget(self.cat_scroll)
        
        # Botones de selección
        cat_btn_row = QHBoxLayout()
        self.select_all_btn = QPushButton("✅ Seleccionar todo")
        self.select_all_btn.clicked.connect(self._select_all_categories)
        self.select_all_btn.setMinimumHeight(28)
        cat_btn_row.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton("⬜ Deseleccionar todo")
        self.deselect_all_btn.clicked.connect(self._deselect_all_categories)
        self.deselect_all_btn.setMinimumHeight(28)
        cat_btn_row.addWidget(self.deselect_all_btn)
        
        cat_btn_row.addStretch()
        
        self.apply_categories_btn = QPushButton("🔄 Actualizar selección")
        self.apply_categories_btn.clicked.connect(self._apply_category_selection)
        self.apply_categories_btn.setMinimumHeight(32)
        self.apply_categories_btn.setStyleSheet(
            "QPushButton { background-color: #3a6b3a; border-color: #5a9b5a; }"
            "QPushButton:hover { background-color: #4a7b4a; }"
        )
        cat_btn_row.addWidget(self.apply_categories_btn)
        
        cat_main_layout.addLayout(cat_btn_row)
        
        # === Resumen ===
        summary_group = QGroupBox("Resumen")
        summary_layout = QVBoxLayout(summary_group)
        self.summary_label = QLabel(
            "Carga un archivo de lista (.xml o .txt) con los nombres de las ROMs que quieres extraer."
        )
        self.summary_label.setWordWrap(True)
        summary_layout.addWidget(self.summary_label)
        # === Área adaptable: selección a la izquierda, actividad a la derecha ===
        splitter = QSplitter(Qt.Horizontal)

        overview_widget = QWidget()
        overview_layout = QVBoxLayout(overview_widget)
        overview_layout.setContentsMargins(0, 0, 0, 0)
        overview_layout.setSpacing(8)
        overview_layout.addWidget(self.categories_group, 1)
        overview_layout.addWidget(summary_group)
        overview_layout.addStretch()
        splitter.addWidget(overview_widget)
        
        # Ejecución
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(8)
        
        exec_group = QGroupBox("Ejecución")
        exec_layout = QVBoxLayout(exec_group)
        exec_layout.setSpacing(6)
        
        btn_row = QHBoxLayout()
        self.clean_btn = QPushButton("🧹 Copiar ROMs a destino")
        self.clean_btn.setObjectName("primaryButton")
        self.clean_btn.clicked.connect(self._start_cleaning)
        self.clean_btn.setMinimumHeight(36)
        self.clean_btn.setEnabled(False)
        btn_row.addWidget(self.clean_btn)
        
        self.cancel_btn = QPushButton("⏹ Cancelar")
        self.cancel_btn.setObjectName("dangerButton")
        self.cancel_btn.clicked.connect(self._cancel_cleaning)
        self.cancel_btn.setMinimumHeight(36)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setVisible(False)
        btn_row.addWidget(self.cancel_btn)
        
        btn_row.addStretch()
        exec_layout.addLayout(btn_row)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        exec_layout.addWidget(self.progress_bar)
        
        # Botón para guardar ROMs no encontradas
        self.export_missing_btn = QPushButton("💾 Guardar lista de ROMs no encontradas")
        self.export_missing_btn.clicked.connect(self._export_missing_roms)
        self.export_missing_btn.setMinimumHeight(32)
        self.export_missing_btn.setVisible(False)
        exec_layout.addWidget(self.export_missing_btn)
        
        bottom_layout.addWidget(exec_group)
        
        # Log
        log_group = QGroupBox("Registro")
        log_layout = QVBoxLayout(log_group)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Aquí aparecerá el registro de la lista y la copia.")
        log_layout.addWidget(self.log_output)
        bottom_layout.addWidget(log_group, 1)
        
        splitter.addWidget(bottom_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([760, 430])
        
        layout.addWidget(splitter, 1)
    
    def load_settings(self):
        self.source_folder.set_text(
            self.settings.value("source_folder", "")
        )
        self.rom_list_file.set_text(
            self.settings.value("rom_list_file", "")
        )
        self.dest_folder.set_text(
            self.settings.value("dest_folder", "")
        )
    
    def save_settings(self):
        self.settings.setValue("source_folder", self.source_folder.text())
        self.settings.setValue("rom_list_file", self.rom_list_file.text())
        self.settings.setValue("dest_folder", self.dest_folder.text())
    
    def _log(self, message: str):
        self.log_output.append(message)
    
    def _load_rom_list(self):
        filepath = self.rom_list_file.text()
        if not filepath:
            QMessageBox.warning(self, "Error", "Selecciona un archivo de lista primero.")
            return
        
        if not os.path.isfile(filepath):
            QMessageBox.warning(self, "Error", f"No se encontró el archivo:\n{filepath}")
            return
        
        try:
            self._log(f"Cargando lista: {filepath}")
            
            # Intentar detectar categorías en el archivo (funciona con .ini, .txt, etc.)
            categories: Dict[str, List[str]] = parse_ini_categories(filepath)
            
            if categories:
                # Archivo con categorías → mostrar selector de categorías
                self._stored_categories = categories
                self._show_category_checkboxes(categories)
                
                # Por defecto cargar TODAS las ROMs (todas las categorías seleccionadas)
                self.parsed_rom_names = set()
                for rom_list in categories.values():
                    self.parsed_rom_names.update(rom_list)
                
                self._log(f"  -> {len(categories)} categorías encontradas con {len(self.parsed_rom_names)} ROMs en total.")
                for cat_name, roms in categories.items():
                    self._log(f"       • {cat_name}: {len(roms)} ROMs")
            else:
                # Archivo normal (XML, txt, o .ini sin categorías)
                self._stored_categories = {}
                self._hide_category_checkboxes()
                self.parsed_rom_names = parse_rom_list_file(filepath)
                self._log(f"  -> {len(self.parsed_rom_names)} nombres de ROMs encontrados.")
            
            # Verificar cuántas existen en el origen
            source_dir = self.source_folder.text()
            if source_dir and os.path.isdir(source_dir):
                roms_in_source = scan_roms(source_dir)
                available = self.parsed_rom_names & roms_in_source
                missing_count = len(self.parsed_rom_names) - len(available)
                self._log(f"  -> {len(available)} ROMs disponibles en origen.")
                if missing_count:
                    self._log(f"  -> {missing_count} ROMs de la lista NO están en el origen.")
                
                self.summary_label.setText(
                    f"Lista: {len(self.parsed_rom_names)} ROMs | "
                    f"En origen: {len(available)} | "
                    f"No encontradas: {missing_count}"
                )
            else:
                self.summary_label.setText(
                    f"Lista cargada: {len(self.parsed_rom_names)} ROMs."
                )
            
            self.clean_btn.setEnabled(len(self.parsed_rom_names) > 0)
            self.save_settings()
            
        except Exception as e:
            self._log(f"ERROR: {e}")
            QMessageBox.critical(self, "Error", f"Error al cargar la lista:\n{e}")
    
    def _start_cleaning(self):
        source_dir = self.source_folder.text()
        dest_dir = self.dest_folder.text()
        
        if not source_dir or not os.path.isdir(source_dir):
            QMessageBox.warning(self, "Error", "Selecciona una carpeta de ROMs origen válida.")
            return
        if not dest_dir:
            QMessageBox.warning(self, "Error", "Selecciona una carpeta de destino.")
            return
        if not self.parsed_rom_names:
            QMessageBox.warning(self, "Error", "Carga una lista de ROMs primero.")
            return
        
        self._log(f"\n--- Iniciando copia de {len(self.parsed_rom_names)} ROMs ---")
        self._log(f"  Origen: {source_dir}")
        self._log(f"  Destino: {dest_dir}")
        
        self.clean_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.parsed_rom_names))
        self.progress_bar.setValue(0)
        
        # Ocultar botón de exportar al iniciar
        self.export_missing_btn.setVisible(False)
        self._last_missing_roms = []
        
        self.worker = CleanWorker(source_dir, self.parsed_rom_names, dest_dir)
        self.worker.progress.connect(self._on_progress)
        self.worker.status.connect(self._log)
        self.worker.finished_clean.connect(self._on_finished)
        self.worker.error.connect(lambda e: (
            self._log(f"ERROR: {e}"),
            QMessageBox.critical(self, "Error", e)
        ))
        self.worker.start()
        
        self.save_settings()
    
    def _cancel_cleaning(self):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)
            self._log("Cancelando limpieza...")
    
    def _on_progress(self, current: int, total: int):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
    
    def _on_finished(self, copied: int, missing: int, not_found: list):
        self.clean_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        msg = f"Limpieza completada: {copied} ROMs copiadas"
        if missing:
            msg += f", {missing} no encontradas"
        self._log(msg)
        
        # Guardar lista de no encontradas y mostrar botón si hay
        self._last_missing_roms = not_found
        if not_found:
            self.export_missing_btn.setVisible(True)
            self._log(f"  ({len(not_found)} ROMs listadas para exportar)")
        
        if copied > 0:
            QMessageBox.information(self, "Completado", msg)
    
    def _show_category_checkboxes(self, categories: Dict[str, List[str]]):
        """Muestra los checkboxes de categorías en el widget."""
        # Limpiar todo el layout (widgets + spacer)
        while self.cat_container_layout.count():
            item = self.cat_container_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._category_checkboxes.clear()
        
        # Crear checkboxes para cada categoría (ordenados alfabéticamente)
        for cat_name in sorted(categories.keys()):
            rom_count = len(categories[cat_name])
            if rom_count == 0:
                continue  # Omitir categorías vacías
            cb = QCheckBox(f"{cat_name}  ({rom_count} ROMs)")
            cb.setChecked(True)
            cb.setProperty("category", cat_name)  # Guardar nombre real para lookup
            cb.setStyleSheet("QCheckBox { padding: 2px 4px; }")
            self._category_checkboxes.append(cb)
            self.cat_container_layout.addWidget(cb)
        
        # Stretch al final
        self.cat_container_layout.addStretch()
        
        self.categories_group.setVisible(True)
    
    def _hide_category_checkboxes(self):
        """Oculta el widget de categorías y limpia los checkboxes."""
        self.categories_group.setVisible(False)
        while self.cat_container_layout.count():
            item = self.cat_container_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._category_checkboxes.clear()
        self._stored_categories = {}
    
    def _select_all_categories(self):
        """Marca todos los checkboxes de categorías."""
        for cb in self._category_checkboxes:
            cb.setChecked(True)
    
    def _deselect_all_categories(self):
        """Desmarca todos los checkboxes de categorías."""
        for cb in self._category_checkboxes:
            cb.setChecked(False)
    
    def _apply_category_selection(self):
        """Aplica la selección de categorías: actualiza parsed_rom_names
        con las ROMs de las categorías marcadas."""
        if not self._stored_categories:
            return
        
        self.parsed_rom_names = set()
        for cb in self._category_checkboxes:
            if cb.isChecked():
                cat_name = cb.property("category")
                if cat_name and cat_name in self._stored_categories:
                    self.parsed_rom_names.update(self._stored_categories[cat_name])
        
        total_selected = len(self.parsed_rom_names)
        cats_checked = sum(1 for cb in self._category_checkboxes if cb.isChecked())
        self._log(f"  -> Selección actualizada: {cats_checked} categorías, {total_selected} ROMs.")
        
        # Actualizar resumen
        source_dir = self.source_folder.text()
        if source_dir and os.path.isdir(source_dir):
            roms_in_source = scan_roms(source_dir)
            available = self.parsed_rom_names & roms_in_source
            missing_count = len(self.parsed_rom_names) - len(available)
            self.summary_label.setText(
                f"Lista: {total_selected} ROMs | "
                f"En origen: {len(available)} | "
                f"No encontradas: {missing_count}"
            )
        else:
            self.summary_label.setText(
                f"Lista cargada: {total_selected} ROMs."
            )
        
        self.clean_btn.setEnabled(total_selected > 0)

    def _export_missing_roms(self):
        """Guarda la lista de ROMs no encontradas a un archivo .txt."""
        if not self._last_missing_roms:
            QMessageBox.information(self, "Sin datos", "No hay ROMs no encontradas para exportar.")
            return
        
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar lista de ROMs no encontradas",
            "roms_no_encontradas.txt",
            "Archivos de texto (*.txt);;Todos (*.*)"
        )
        if not filepath:
            return  # Usuario canceló
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# ROMs no encontradas en el origen\n")
                f.write(f"# Total: {len(self._last_missing_roms)}\n")
                f.write(f"#\n")
                for rom in sorted(self._last_missing_roms):
                    f.write(f"{rom}\n")
            self._log(f"  -> Lista guardada en: {filepath}")
            QMessageBox.information(
                self, "Guardado",
                f"Lista de {len(self._last_missing_roms)} ROMs guardada en:\n{filepath}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al guardar:\n{e}")
