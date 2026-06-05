#!/usr/bin/env python3
"""
MameSys Extractor - Herramienta para gestionar ROMs de MAME.

Extrae ROMs por sistema de arcade (NeoGeo, CPS1, CPS2, etc.)
usando catver.ini, y permite limpiar el romset con listas
personalizadas de nombres de ROMs.

Ejecutar:
    python main.py
    python3 main.py
"""

import sys
import os

# Asegurar que el directorio del proyecto está en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.app import main

if __name__ == "__main__":
    main()
