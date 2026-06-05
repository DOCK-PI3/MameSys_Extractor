"""
Widgets de UI compartidos entre las pestañas.
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton,
    QFileDialog, QLabel,
)
from PySide6.QtCore import Signal, Qt


class FolderSelector(QWidget):
    """Widget compuesto: etiqueta + línea de texto + botón Examinar."""
    
    path_changed = Signal(str)
    
    def __init__(self, label_text: str = "Carpeta:", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        self.label = QLabel(label_text)
        self.label.setFixedWidth(110)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.path_input = QLineEdit()
        self.path_input.setMinimumHeight(32)
        self.path_input.setPlaceholderText("Selecciona una carpeta...")
        self.path_input.textChanged.connect(self.path_changed.emit)
        
        self.browse_btn = QPushButton("Examinar...")
        self.browse_btn.setObjectName("secondaryButton")
        self.browse_btn.setMinimumWidth(90)
        self.browse_btn.setMinimumHeight(32)
        self.browse_btn.clicked.connect(self._browse)
        
        layout.addWidget(self.label)
        layout.addWidget(self.path_input, 1)
        layout.addWidget(self.browse_btn)
    
    def _browse(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Seleccionar Carpeta", self.path_input.text() or ""
        )
        if folder:
            self.path_input.setText(folder)
    
    def text(self) -> str:
        return self.path_input.text()
    
    def set_text(self, text: str):
        self.path_input.setText(text)


class FileSelector(QWidget):
    """Widget compuesto: etiqueta + línea de texto + botón Examinar (archivo)."""
    
    path_changed = Signal(str)
    
    def __init__(self, label_text: str = "Archivo:", filter_str: str = "Todos (*.*)", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        self.label = QLabel(label_text)
        self.label.setFixedWidth(110)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.path_input = QLineEdit()
        self.path_input.setMinimumHeight(32)
        self.path_input.setPlaceholderText("Selecciona un archivo...")
        self.path_input.textChanged.connect(self.path_changed.emit)
        
        self.browse_btn = QPushButton("Examinar...")
        self.browse_btn.setObjectName("secondaryButton")
        self.browse_btn.setMinimumWidth(90)
        self.browse_btn.setMinimumHeight(32)
        self.browse_btn.clicked.connect(lambda: self._browse(filter_str))
        
        layout.addWidget(self.label)
        layout.addWidget(self.path_input, 1)
        layout.addWidget(self.browse_btn)
    
    def _browse(self, filter_str: str):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Archivo", self.path_input.text() or "", filter_str
        )
        if filepath:
            self.path_input.setText(filepath)
    
    def text(self) -> str:
        return self.path_input.text()
    
    def set_text(self, text: str):
        self.path_input.setText(text)
