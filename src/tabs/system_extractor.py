"""
Pestaña 1: Extractor de ROMs por Sistema.

Soporta dos fuentes de datos:
- catver.ini: Filtra ROMs por sistema de arcade (NeoGeo, CPS1, CPS2, etc.)
- Archivos .DAT de clrmamepro: Cada .dat define un sistema con sus ROMs
"""

import os
from typing import Dict, List, Set

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QListWidget, QListWidgetItem, QPushButton,
    QTextEdit, QProgressBar, QComboBox, QLabel,
    QMessageBox, QSplitter, QStackedWidget, QFileDialog,
)
from PySide6.QtCore import Qt, QThread, Signal, QSettings

from src.core.catver_parser import (
    parse_catver, get_available_systems,
    get_system_roms, SYSTEM_PROFILES, SUBCATEGORY_PREFIX,
)
from src.core.dat_parser import parse_dat_folder
from src.core.rom_operations import scan_roms, copy_roms
from src.ui.widgets import FolderSelector, FileSelector


class ExtractWorker(QThread):
    """Worker thread para no bloquear la UI durante la extracción."""
    
    progress = Signal(int, int)         # actual, total
    status = Signal(str)                # mensaje de estado
    finished_extract = Signal(int, int, list)  # copiados, no_encontrados, lista_no_encontrados
    error = Signal(str)
    
    def __init__(self, source_dir: str, systems_selected: Dict[str, Set[str]],
                 dest_base: str, parent=None):
        super().__init__(parent)
        self.source_dir = source_dir
        self.systems_selected = systems_selected  # {system_name: {rom1, rom2, ...}}
        self.dest_base = dest_base
        self._cancelled = False
    
    def cancel(self):
        """Cancela la extracción en curso."""
        self._cancelled = True
    
    def run(self):
        try:
            total_roms = sum(len(roms) for roms in self.systems_selected.values())
            total_copied = 0
            total_missing = 0
            all_missing: List[str] = []
            processed = 0
            
            # Crear todos los directorios de destino de una vez
            for system_name in self.systems_selected.keys():
                dest_dir = os.path.join(self.dest_base, system_name.replace(" ", "_"))
                os.makedirs(dest_dir, exist_ok=True)
            
            for system_name, rom_names in self.systems_selected.items():
                if self._cancelled:
                    self.status.emit("Extracción cancelada por el usuario.")
                    break
                
                self.status.emit(f"Procesando {system_name} ({len(rom_names)} ROMs)...")
                
                dest_dir = os.path.join(self.dest_base, system_name.replace(" ", "_"))
                copied, missing, not_found = copy_roms(
                    self.source_dir, rom_names, dest_dir,
                    progress_callback=lambda cur, tot: (
                        self.progress.emit(processed + cur, total_roms)
                        if not self._cancelled else None
                    ),
                    should_cancel=lambda: self._cancelled,
                )
                total_copied += copied
                total_missing += missing
                all_missing.extend(not_found)
                processed += len(rom_names)
                self.progress.emit(processed, total_roms)
            
            if not self._cancelled:
                self.status.emit(
                    f"¡Completado! {total_copied} ROMs copiadas, "
                    f"{total_missing} no encontradas en el origen."
                )
            self.finished_extract.emit(total_copied, total_missing, all_missing)
        
        except Exception as e:
            self.error.emit(f"Error en extracción: {e}")
            self.finished_extract.emit(0, 0, [])


class SystemExtractorTab(QWidget):
    """Pestaña de extracción de ROMs por sistemas de arcade."""
    
    MODE_CATVER = "catver"
    MODE_DAT = "dat"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.catver_data: Dict[str, str] = {}
        self.dat_systems: Dict[str, Dict[str, str]] = {}  # {system: {rom: desc}}
        self.roms_in_source: Set[str] = set()
        self.systems_available: Dict[str, int] = {}
        self._current_source_mode = self.MODE_CATVER
        self._last_missing_roms: List[str] = []
        
        self.settings = QSettings("MameSysExtractor", "SystemExtractor")
        self._init_ui()
        self.load_settings()
    
    # ==================================================================
    # UI Construction
    # ==================================================================
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # === Configuración ===
        config_group = QGroupBox("Configuración")
        config_layout = QVBoxLayout(config_group)
        
        # Origen de ROMs
        self.source_folder = FolderSelector("ROMs origen:")
        config_layout.addWidget(self.source_folder)
        
        # Selector de tipo de fuente
        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Fuente de datos:"))
        self.source_combo = QComboBox()
        self.source_combo.addItem("📋 catver.ini (categorías)", self.MODE_CATVER)
        self.source_combo.addItem("📦 Archivos .DAT (clrmamepro)", self.MODE_DAT)
        self.source_combo.currentIndexChanged.connect(self._on_source_mode_changed)
        source_row.addWidget(self.source_combo, 1)
        config_layout.addLayout(source_row)
        
        # Stacked widget: catver.ini vs .DAT folder
        self.source_stack = QStackedWidget()
        
        # Página 0: catver.ini
        self.catver_file = FileSelector(
            "catver.ini:",
            "Archivos INI (*.ini);;Todos (*.*)"
        )
        self.source_stack.addWidget(self.catver_file)
        
        # Página 1: carpeta de .dat
        self.dat_folder = FolderSelector("Carpeta .dat:")
        self.source_stack.addWidget(self.dat_folder)
        
        config_layout.addWidget(self.source_stack)
        
        # Carpeta destino
        self.dest_folder = FolderSelector("Carpeta destino:")
        config_layout.addWidget(self.dest_folder)
        
        # Botón para analizar
        load_row = QHBoxLayout()
        self.load_btn = QPushButton("🔍 Analizar")
        self.load_btn.clicked.connect(self._load_source)
        self.load_btn.setMinimumHeight(32)
        load_row.addWidget(self.load_btn)
        load_row.addStretch()
        config_layout.addLayout(load_row)
        
        layout.addWidget(config_group)
        
        # === Área adaptable: sistemas a la izquierda, actividad a la derecha ===
        splitter = QSplitter(Qt.Horizontal)
        
        # --- Lista de sistemas ---
        systems_group = QGroupBox("Sistemas detectados")
        systems_layout = QVBoxLayout(systems_group)
        
        # Etiqueta de resumen
        self.summary_label = QLabel(
            "Selecciona una fuente de datos (catver.ini o .dat) y pulsa 'Analizar'."
        )
        self.summary_label.setWordWrap(True)
        systems_layout.addWidget(self.summary_label)
        
        # Cabecera con botones de selección
        select_row = QHBoxLayout()
        self.select_all_btn = QPushButton("Seleccionar todos")
        self.select_all_btn.clicked.connect(lambda: self._toggle_all(True))
        self.deselect_all_btn = QPushButton("Deseleccionar todos")
        self.deselect_all_btn.clicked.connect(lambda: self._toggle_all(False))
        select_row.addWidget(self.select_all_btn)
        select_row.addWidget(self.deselect_all_btn)
        select_row.addStretch()
        systems_layout.addLayout(select_row)
        
        self.systems_list = QListWidget()
        self.systems_list.setSelectionMode(QListWidget.NoSelection)
        systems_layout.addWidget(self.systems_list)
        
        splitter.addWidget(systems_group)
        
        # --- Ejecución y log ---
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(8)
        
        exec_group = QGroupBox("Ejecución")
        exec_layout = QVBoxLayout(exec_group)
        exec_layout.setSpacing(6)
        
        btn_row = QHBoxLayout()
        self.extract_btn = QPushButton("🚀 Extraer ROMs")
        self.extract_btn.setObjectName("primaryButton")
        self.extract_btn.clicked.connect(self._start_extraction)
        self.extract_btn.setMinimumHeight(36)
        self.extract_btn.setEnabled(False)
        btn_row.addWidget(self.extract_btn)
        
        self.cancel_btn = QPushButton("⏹ Cancelar")
        self.cancel_btn.setObjectName("dangerButton")
        self.cancel_btn.clicked.connect(self._cancel_extraction)
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
        self.log_output.setPlaceholderText("Aquí aparecerá el registro del análisis y la extracción.")
        log_layout.addWidget(self.log_output)
        bottom_layout.addWidget(log_group, 1)
        
        splitter.addWidget(bottom_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([760, 430])
        
        layout.addWidget(splitter, 1)
    
    # ==================================================================
    # Settings
    # ==================================================================
    
    def load_settings(self):
        self.source_folder.set_text(
            self.settings.value("source_folder", "")
        )
        self.catver_file.set_text(
            self.settings.value("catver_file", "")
        )
        self.dat_folder.set_text(
            self.settings.value("dat_folder", "")
        )
        self.dest_folder.set_text(
            self.settings.value("dest_folder", "")
        )
        
        # Restaurar modo anterior
        saved_mode = self.settings.value("source_mode", self.MODE_CATVER)
        idx = self.source_combo.findData(saved_mode)
        if idx >= 0:
            self.source_combo.setCurrentIndex(idx)
        self._on_source_mode_changed()
    
    def save_settings(self):
        self.settings.setValue("source_folder", self.source_folder.text())
        self.settings.setValue("catver_file", self.catver_file.text())
        self.settings.setValue("dat_folder", self.dat_folder.text())
        self.settings.setValue("dest_folder", self.dest_folder.text())
        self.settings.setValue("source_mode", self._current_source_mode)
    
    # ==================================================================
    # Mode switching
    # ==================================================================
    
    def _on_source_mode_changed(self):
        mode = self.source_combo.currentData()
        self._current_source_mode = mode
        
        if mode == self.MODE_CATVER:
            self.source_stack.setCurrentIndex(0)
            self.load_btn.setText("🔍 Analizar catver.ini")
        else:
            self.source_stack.setCurrentIndex(1)
            self.load_btn.setText("🔍 Analizar archivos .DAT")
        
        self.save_settings()
    
    # ==================================================================
    # Data loading
    # ==================================================================
    
    def _load_source(self):
        mode = self._current_source_mode
        
        # Escanear ROMs en origen primero
        source_dir = self.source_folder.text()
        if source_dir and os.path.isdir(source_dir):
            self.roms_in_source = scan_roms(source_dir)
        else:
            self.roms_in_source = set()
        
        if mode == self.MODE_CATVER:
            self._load_catver()
        else:
            self._load_dat()
    
    def _load_catver(self):
        catver_path = self.catver_file.text()
        if not catver_path:
            QMessageBox.warning(self, "Error", "Selecciona el archivo catver.ini primero.")
            return
        
        if not os.path.isfile(catver_path):
            QMessageBox.warning(self, "Error", f"No se encontró el archivo:\n{catver_path}")
            return
        
        try:
            self._log(f"Cargando catver.ini: {catver_path}")
            self.catver_data = parse_catver(catver_path)
            self._log(f"  -> {len(self.catver_data)} ROMs categorizadas encontradas.")
            # ROMs en origen
            if self.roms_in_source:
                self._log(f"  -> {len(self.roms_in_source)} ROMs (.zip/.7z) en carpeta origen.")
            
            # Detectar sistemas disponibles
            self.systems_available = get_available_systems(self.catver_data)
            self._populate_systems_list()
            
            # Habilitar extracción si hay sistemas
            self.extract_btn.setEnabled(len(self.systems_available) > 0)
            
            # Actualizar resumen
            total = sum(self.systems_available.values())
            msg = f"[catver.ini] {len(self.systems_available)} sistemas con {total} ROMs."
            if self.roms_in_source:
                # Calcular cuántas ROMs de los sistemas detectados están en origen
                available_total = 0
                for sys_name in self.systems_available:
                    roms = get_system_roms(self.catver_data, sys_name)
                    available_total += len(roms.keys() & self.roms_in_source)
                if available_total != total:
                    msg += f" ({available_total} disponibles en origen)"
            self.summary_label.setText(msg)
            
            self.save_settings()
            
        except Exception as e:
            self._log(f"ERROR: {e}")
            QMessageBox.critical(self, "Error", f"Error al cargar catver.ini:\n{e}")
    
    def _load_dat(self):
        dat_folder_path = self.dat_folder.text()
        if not dat_folder_path:
            QMessageBox.warning(self, "Error", "Selecciona una carpeta con archivos .DAT primero.")
            return
        
        if not os.path.isdir(dat_folder_path):
            QMessageBox.warning(self, "Error", f"No se encontró la carpeta:\n{dat_folder_path}")
            return
        
        try:
            self._log(f"Analizando archivos .DAT en: {dat_folder_path}")
            self.dat_systems = parse_dat_folder(dat_folder_path, log_callback=self._log)
            # ROMs en origen
            if self.roms_in_source:
                self._log(f"  -> {len(self.roms_in_source)} ROMs (.zip/.7z) en carpeta origen.")
            
            if not self.dat_systems:
                QMessageBox.warning(
                    self, "Sin resultados",
                    f"No se encontraron archivos .dat válidos en:\n{dat_folder_path}"
                )
                return
            
            self._log(f"  -> {len(self.dat_systems)} sistemas encontrados en archivos .dat.")
            
            # Construir diccionario de sistemas disponibles
            # Mostrar total de ROMs en el .dat y cuántas hay en origen
            self.systems_available = {}
            for sys_name, roms in self.dat_systems.items():
                self.systems_available[sys_name] = len(roms)
            
            self._populate_systems_list()
            
            self.extract_btn.setEnabled(len(self.systems_available) > 0)
            
            total_dat = sum(len(r) for r in self.dat_systems.values())
            available = sum(
                len(r.keys() & self.roms_in_source) if self.roms_in_source else 0
                for r in self.dat_systems.values()
            )
            msg = f"[.DAT] {len(self.dat_systems)} sistemas, {total_dat} ROMs totales."
            if self.roms_in_source and available != total_dat:
                msg += f" ({available} disponibles en origen)"
            self.summary_label.setText(msg)
            
            self.save_settings()
            
        except Exception as e:
            self._log(f"ERROR: {e}")
            QMessageBox.critical(self, "Error", f"Error al analizar .DAT:\n{e}")
    
    # ==================================================================
    # Systems list
    # ==================================================================
    
    def _populate_systems_list(self):
        """Llena la lista de sistemas/categorías con orden agrupado:
        las subcategorías (prefijo '  └ ') aparecen debajo de su categoría padre."""
        self.systems_list.clear()
        
        # Ordenar agrupando subcategorías bajo su categoría padre
        def _sort_key(item):
            name = item[0]
            # Subcategoría: extraer categoría padre de "  └ Padre / Hijo"
            if name.startswith(SUBCATEGORY_PREFIX):
                clean = name[len(SUBCATEGORY_PREFIX):]
                if ' / ' in clean:
                    parent = clean.split(' / ', 1)[0]
                else:
                    parent = clean
                return (parent, 1, clean.lower())
            # Categoría principal o sistema
            return (name, 0, name.lower())
        
        for system_name, count in sorted(self.systems_available.items(), key=_sort_key):
            item = QListWidgetItem(f"{system_name}  ({count} ROMs)")
            item.setData(Qt.UserRole, system_name)
            item.setCheckState(Qt.Unchecked)
            self.systems_list.addItem(item)
    
    def _toggle_all(self, checked: bool):
        for i in range(self.systems_list.count()):
            item = self.systems_list.item(i)
            item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
    
    # ==================================================================
    # Extraction
    # ==================================================================
    
    def _get_system_roms(self, system_name: str) -> Set[str]:
        """
        Obtiene el conjunto de nombres de ROMs para un sistema,
        según la fuente de datos activa.
        """
        if self._current_source_mode == self.MODE_CATVER:
            roms = get_system_roms(self.catver_data, system_name)
            return set(roms.keys())
        else:
            # MODE_DAT
            if system_name in self.dat_systems:
                return set(self.dat_systems[system_name].keys())
            return set()
    
    def _start_extraction(self):
        source_dir = self.source_folder.text()
        dest_base = self.dest_folder.text()
        
        if not source_dir or not os.path.isdir(source_dir):
            QMessageBox.warning(self, "Error", "Selecciona una carpeta de ROMs origen válida.")
            return
        if not dest_base:
            QMessageBox.warning(self, "Error", "Selecciona una carpeta de destino.")
            return
        
        # Recoger sistemas seleccionados
        systems_selected: Dict[str, Set[str]] = {}
        for i in range(self.systems_list.count()):
            item = self.systems_list.item(i)
            if item.checkState() == Qt.Checked:
                system_name = item.data(Qt.UserRole)
                roms = self._get_system_roms(system_name)
                # Solo incluir ROMs que existen en el origen
                if self.roms_in_source and roms:
                    roms_in_both = roms & self.roms_in_source  # intersección
                else:
                    roms_in_both = roms
                if roms_in_both:
                    systems_selected[system_name] = roms_in_both
        
        if not systems_selected:
            QMessageBox.warning(
                self, "Sin selección",
                "Selecciona al menos un sistema con ROMs disponibles."
            )
            return
        
        # Resumen
        total = sum(len(r) for r in systems_selected.values())
        fuente = "catver.ini" if self._current_source_mode == self.MODE_CATVER else ".DAT"
        self._log(f"\n--- Extrayendo {total} ROMs (fuente: {fuente}) ---")
        for sys_name, roms in systems_selected.items():
            self._log(f"  {sys_name}: {len(roms)} ROMs")
        
        self.extract_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(0)
        
        # Ocultar botón de exportar al iniciar nueva extracción
        self.export_missing_btn.setVisible(False)
        self._last_missing_roms = []
        
        self.worker = ExtractWorker(source_dir, systems_selected, dest_base)
        self.worker.progress.connect(self._on_progress)
        self.worker.status.connect(self._log)
        self.worker.finished_extract.connect(self._on_finished)
        self.worker.error.connect(lambda e: (
            self._log(f"ERROR: {e}"),
            QMessageBox.critical(self, "Error", e)
        ))
        self.worker.start()
        
        self.save_settings()
    
    # ==================================================================
    # Logging & helpers
    # ==================================================================
    
    def _log(self, message: str):
        self.log_output.append(message)
    
    def _on_progress(self, current: int, total: int):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
    
    def _cancel_extraction(self):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)
            self._log("Cancelando extracción...")
    
    def _on_finished(self, copied: int, missing: int, not_found: list):
        self.extract_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        msg = f"Extracción completada: {copied} ROMs copiadas"
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
