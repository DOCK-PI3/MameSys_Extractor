#!/usr/bin/env python3
"""
Lee la versión desde src/app.py (constante VERSION) y auto-genera
version.txt para PyInstaller.

Ejecutar:
    python sync_version.py
"""

import re
import os
import sys
from datetime import date

APP_PY = os.path.join("src", "app.py")
BUILD_INFO_PY = os.path.join("src", "build_info.py")
VERSION_TXT = "version.txt"


def extract_version() -> str:
    """Extrae VERSION = 'X.Y.Z' de src/app.py."""
    if not os.path.isfile(APP_PY):
        print(f"[ERROR] No se encontro {APP_PY}")
        sys.exit(1)

    with open(APP_PY, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(r'\bVERSION\s*=\s*["\']([^"\']+)["\']', content)
    if not match:
        print(f"[ERROR] No se encontro 'VERSION = ...' en {APP_PY}")
        sys.exit(1)

    return match.group(1)


def parse_version(version_str: str) -> tuple:
    """
    Convierte '1.0.0.20250605' a (1, 0, 0, 20250605).
    Si solo tiene 3 partes (ej: '1.0.0'), añade 0 como 4ª.
    """
    parts = version_str.split(".")
    nums = [int(p) for p in parts[:4]]
    while len(nums) < 4:
        nums.append(0)
    return tuple(nums[:4])


def generate_version_txt(semver: str, build_version: str):
    """Genera version.txt con los datos de versión."""
    v = parse_version(build_version)

    content = f"""# UTF-8
#
# Auto-generado por sync_version.py desde src/app.py
# Versión semántica: {semver}
# Build:             {build_version}
#
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={v},
    prodvers={v},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'040904B0',
          [StringStruct(u'CompanyName', u'MameSys'),
           StringStruct(u'FileDescription', u'MameSys Extractor - Gestor de ROMs de MAME'),
           StringStruct(u'FileVersion', u'{semver}'),
           StringStruct(u'InternalName', u'MameSys_Extractor'),
           StringStruct(u'LegalCopyright', u'Open Source'),
           StringStruct(u'OriginalFilename', u'MameSys_Extractor.exe'),
           StringStruct(u'ProductName', u'MameSys Extractor'),
           StringStruct(u'ProductVersion', u'{build_version}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [0x409, 1200])])
  ]
)
"""

    with open(VERSION_TXT, "w", encoding="utf-8") as f:
        f.write(content.lstrip())

    print(f"  -> version.txt generado (v{semver} build {build_version})")


def generate_build_info(semver: str, build_date: str, build_version: str):
    """Genera src/build_info.py con los datos de build para la UI."""
    content = f'''"""Info de build auto-generada por sync_version.py. No editar manualmente."""

BUILD_DATE = "{build_date}"
BUILD_VERSION = "{build_version}"
'''
    with open(BUILD_INFO_PY, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"  -> {BUILD_INFO_PY} generado (v{semver} build {build_date})")


def main():
    version = extract_version()
    build_num = date.today().strftime("%Y%m%d")
    build_version = f"{version}.{build_num}"
    
    print(f"  Version semantica:  v{version}")
    print(f"  Build number:       {build_num}")
    print(f"  Version de build:   v{build_version}")
    generate_version_txt(version, build_version)
    generate_build_info(version, build_num, build_version)


if __name__ == "__main__":
    main()
