"""
Ventana principal de MameSys Extractor.

Aplicación con interfaz de pestañas para gestionar ROMs:
- Extracción rápida de sistemas MAME conocidos
- Exploración de sistemas MAME mediante catver.ini/.DAT
- Limpieza con listas XML/Texto
- Copia universal para sistemas retro y ficheros generales
"""

import sys
import os

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget,
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QMenuBar, QMenu, QMessageBox,
)
from PySide6.QtGui import QIcon, QFont, QAction
from PySide6.QtCore import Qt

from src.tabs.system_extractor import SystemExtractorTab
from src.tabs.xml_cleaner import XmlCleanerTab
from src.tabs.quick_extractor import QuickExtractorTab
from src.tabs.universal_extractor import UniversalExtractorTab

try:
    from src.build_info import BUILD_DATE, BUILD_VERSION
except ImportError:
    BUILD_DATE = "unknown"
    BUILD_VERSION = "unknown"


class MainWindow(QMainWindow):
    """Ventana principal con pestañas."""
    
    VERSION = "1.2.0"
    BUILD_DATE = BUILD_DATE
    WINDOW_TITLE = "MameSys Extractor"
    WINDOW_WIDTH = 1180
    WINDOW_HEIGHT = 760
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{self.WINDOW_TITLE} v{self.VERSION} build {MainWindow.BUILD_DATE}")
        self.resize(self.WINDOW_WIDTH, self.WINDOW_HEIGHT)
        self.setMinimumSize(900, 620)
        
        # Widget central
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 10, 12, 8)
        main_layout.setSpacing(8)
        
        # Cabecera
        header = QFrame()
        header.setObjectName("appHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 10)

        title_column = QVBoxLayout()
        title_column.setSpacing(2)
        title_label = QLabel("MameSys Extractor")
        title_label.setObjectName("appTitle")
        title_font = QFont()
        title_font.setPointSize(17)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_column.addWidget(title_label)
        
        subtitle_label = QLabel(
            "Organiza y extrae sistemas completos de MAME, consolas retro y ficheros generales."
        )
        subtitle_label.setWordWrap(True)
        subtitle_label.setObjectName("headerSubtitle")
        title_column.addWidget(subtitle_label)
        header_layout.addLayout(title_column, 1)

        version_label = QLabel(f"v{MainWindow.VERSION} · build {MainWindow.BUILD_DATE}")
        version_label.setObjectName("versionBadge")
        version_label.setToolTip(f"MameSys Extractor v{BUILD_VERSION}")
        header_layout.addWidget(version_label, 0, Qt.AlignVCenter)
        main_layout.addWidget(header)
        
        # Barra de menú
        self._create_menu_bar()
        
        # Pestañas
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        
        self.quick_tab = QuickExtractorTab()
        self.system_tab = SystemExtractorTab()
        self.xml_tab = XmlCleanerTab()
        self.universal_tab = UniversalExtractorTab()
        
        self.tabs.addTab(self.quick_tab, "Extracción rápida")
        self.tabs.addTab(self.system_tab, "Explorar sistemas")
        self.tabs.addTab(self.xml_tab, "Extraer con lista")
        self.tabs.addTab(self.universal_tab, "Universal TXT")
        
        main_layout.addWidget(self.tabs, 1)
        self._link_shared_paths()
        
        # Barra de estado
        self.statusBar().showMessage("Listo. Creado por mabedeep Emulos Team 2026")
    
    def _create_menu_bar(self):
        """Crea la barra de menú superior."""
        menu_bar = self.menuBar()

        # Menú Ayuda
        help_menu = menu_bar.addMenu("Ayuda")

        about_action = QAction("Acerca de", self)
        about_action.setShortcut("F1")
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _show_about(self):
        """Muestra el diálogo 'Acerca de'."""
        QMessageBox.about(
            self,
            "Acerca de MameSys Extractor",
            f"<h2 style='color:#f8fafc;margin-bottom:12px;'>MameSys Extractor</h2>"
            f"<p style='color:#cbd5e1;font-size:13px;'>"
            f"Gestor de ROMs y ficheros retro — organiza, extrae y limpia tus colecciones.<br><br>"
            f"<b>Versión:</b> {BUILD_VERSION}<br>"
            f"<b>Build:</b> {BUILD_DATE}<br>"
            f"<b>Autor:</b> mabedeep Emulos Team<br>"
            f"<b>Licencia:</b> Open Source<br>"
            f"</p>"
            f"<p style='color:#64748b;font-size:11px;margin-top:8px;'>"
            f"© 2026 MameSys Extractor"
            f"</p>"
        )

    def closeEvent(self, event):
        """Guardar configuración al cerrar."""
        self.system_tab.save_settings()
        self.xml_tab.save_settings()
        self.quick_tab.save_settings()
        self.universal_tab.save_settings()
        super().closeEvent(event)

    def _link_shared_paths(self):
        """Mantiene las carpetas origen/destino sincronizadas entre pestañas."""
        tabs = (self.quick_tab, self.system_tab, self.xml_tab, self.universal_tab)

        for source_tab in tabs:
            for target_tab in tabs:
                if source_tab is target_tab:
                    continue
                source_tab.source_folder.path_changed.connect(target_tab.source_folder.set_text)
                source_tab.dest_folder.path_changed.connect(target_tab.dest_folder.set_text)

        # Al iniciar, reutilizar la primera ruta guardada que exista.
        shared_source = next((tab.source_folder.text() for tab in tabs if tab.source_folder.text()), "")
        shared_dest = next((tab.dest_folder.text() for tab in tabs if tab.dest_folder.text()), "")
        for tab in tabs:
            if shared_source:
                tab.source_folder.set_text(shared_source)
            if shared_dest:
                tab.dest_folder.set_text(shared_dest)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MameSys Extractor")
    app.setOrganizationName("MameSysExtractor")
    
    # Estilo global
    app.setStyle("Fusion")
    _apply_stylesheet(app)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


def _apply_stylesheet(app: QApplication):
    """Aplica estilos modernos y oscuros a la aplicación."""
    stylesheet = """
    QMainWindow, QWidget {
        background-color: #111827;
        color: #e5e7eb;
    }
    QWidget {
        font-size: 13px;
    }
    QFrame#appHeader {
        background-color: #172033;
        border: 1px solid #26344d;
        border-radius: 10px;
    }
    QLabel#appTitle {
        color: #f8fafc;
    }
    QLabel#headerSubtitle, QLabel#mutedLabel {
        color: #94a3b8;
    }
    QLabel#versionBadge, QLabel#countBadge {
        background-color: #22304a;
        color: #93c5fd;
        border: 1px solid #334b70;
        border-radius: 9px;
        padding: 3px 9px;
        font-weight: bold;
    }
    QFrame#systemCard {
        background-color: #172033;
        border: 1px solid #2b3a55;
        border-radius: 8px;
    }
    QFrame#systemCard:hover {
        border-color: #3b82f6;
        background-color: #1a263b;
    }
    QLabel#cardTitle {
        color: #f8fafc;
        font-size: 14px;
        font-weight: bold;
    }
    QLabel#availabilityLabel {
        color: #67e8f9;
    }
    QGroupBox {
        background-color: #151e2f;
        border: 1px solid #2b3a55;
        border-radius: 8px;
        margin-top: 10px;
        padding-top: 12px;
        font-weight: bold;
        color: #cbd5e1;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        color: #93c5fd;
    }
    QLineEdit {
        background-color: #0f172a;
        border: 1px solid #334155;
        border-radius: 6px;
        padding: 6px 9px;
        color: #f8fafc;
        selection-background-color: #2563eb;
    }
    QLineEdit:focus {
        border: 1px solid #60a5fa;
    }
    QPushButton {
        background-color: #22304a;
        border: 1px solid #3a4b69;
        border-radius: 6px;
        padding: 6px 14px;
        color: #e5e7eb;
        font-weight: 500;
    }
    QPushButton:hover {
        background-color: #2b3d5d;
        border-color: #60a5fa;
    }
    QPushButton:pressed {
        background-color: #1d2b43;
    }
    QPushButton#primaryButton {
        background-color: #2563eb;
        border-color: #3b82f6;
        color: white;
        font-weight: bold;
    }
    QPushButton#primaryButton:hover {
        background-color: #1d4ed8;
    }
    QPushButton#primaryButton:disabled {
        background-color: #1e293b;
        color: #64748b;
        border-color: #334155;
    }
    QPushButton#dangerButton {
        background-color: #7f1d1d;
        border-color: #b91c1c;
    }
    QPushButton:disabled {
        background-color: #1e293b;
        color: #64748b;
        border-color: #334155;
    }
    QListWidget, QScrollArea {
        background-color: #0f172a;
        border: 1px solid #334155;
        border-radius: 6px;
        padding: 4px;
        outline: none;
    }
    QListWidget::item {
        padding: 4px 6px;
        border-radius: 3px;
    }
    QListWidget::item:hover {
        background-color: #1e293b;
    }
    QTextEdit {
        background-color: #0b1220;
        border: 1px solid #334155;
        border-radius: 6px;
        padding: 6px;
        font-family: "Consolas", "Courier New", monospace;
        font-size: 12px;
        color: #cbd5e1;
    }
    QProgressBar {
        background-color: #0f172a;
        border: 1px solid #334155;
        border-radius: 5px;
        text-align: center;
        color: #e5e7eb;
    }
    QProgressBar::chunk {
        background-color: #2563eb;
        border-radius: 4px;
    }
    QTabWidget::pane {
        border: 1px solid #2b3a55;
        border-radius: 7px;
        background-color: #111827;
    }
    QTabBar::tab {
        background-color: #172033;
        border: 1px solid #2b3a55;
        border-bottom: none;
        border-radius: 6px 6px 0 0;
        padding: 9px 22px;
        margin-right: 3px;
        color: #94a3b8;
    }
    QTabBar::tab:selected {
        background-color: #1e293b;
        color: #93c5fd;
        font-weight: bold;
    }
    QTabBar::tab:hover {
        background-color: #22304a;
    }
    QSplitter::handle {
        background-color: #26344d;
        width: 2px;
    }
    QStatusBar {
        background-color: #0b1220;
        color: #94a3b8;
    }
    QMenuBar {
        background-color: #0f172a;
        color: #cbd5e1;
        border-bottom: 1px solid #26344d;
        padding: 2px 6px;
    }
    QMenuBar::item {
        padding: 4px 12px;
        border-radius: 4px;
    }
    QMenuBar::item:selected {
        background-color: #1e293b;
    }
    QMenu {
        background-color: #151e2f;
        border: 1px solid #334155;
        border-radius: 6px;
        padding: 4px;
        color: #e5e7eb;
    }
    QMenu::item {
        padding: 6px 28px 6px 16px;
        border-radius: 4px;
    }
    QMenu::item:selected {
        background-color: #2563eb;
    }
    QLabel {
        background-color: transparent;
    }
    """
    app.setStyleSheet(stylesheet)


if __name__ == "__main__":
    main()
