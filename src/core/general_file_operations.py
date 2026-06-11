"""Operaciones genéricas para extraer ficheros por nombre base.

Esta lógica está pensada para sistemas no-MAME: consolas retro, microordenadores
o cualquier colección donde el TXT contiene nombres sin extensión.
"""

import os
import shutil
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple


KNOWN_EXTENSIONS = {
    ".zip", ".7z", ".rar",
    ".iso", ".bin", ".cue", ".chd", ".gdi", ".cdi", ".ccd", ".img", ".sub", ".m3u",
    ".nes", ".fds", ".sfc", ".smc", ".gba", ".gb", ".gbc", ".n64", ".z64", ".v64",
    ".md", ".gen", ".smd", ".sms", ".gg", ".pce", ".a26", ".a52", ".a78", ".lnx",
    ".tap", ".tzx", ".dsk", ".adf", ".hdf", ".lha", ".rom",
    ".pbp", ".cso", ".exe", ".com", ".bat",
}


@dataclass(frozen=True)
class MatchCandidate:
    """Archivo o carpeta encontrada para una entrada del TXT."""

    source_path: str
    relative_path: str
    is_dir: bool


def normalize_base_name(name: str) -> str:
    """Normaliza un nombre para comparaciones tolerantes a mayúsculas/espacios."""
    return " ".join(name.strip().casefold().split())


def parse_general_txt_list(filepath: str) -> List[str]:
    """Lee un TXT con un nombre base por línea, preservando el orden.

    Ejemplo:
        sonic 2 (usa)
        Another World (Europe)

    Si por accidente se incluye una extensión simple, se elimina.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"No se encontró el archivo: {filepath}")

    entries: List[str] = []
    seen = set()
    with open(filepath, "r", encoding="utf-8", errors="replace") as file:
        for line in file:
            name = line.strip()
            if not name or name.startswith(("#", ";", "//")):
                continue

            name = _strip_simple_extension(name)
            key = normalize_base_name(name)
            if key and key not in seen:
                seen.add(key)
                entries.append(name)

    return entries


def scan_general_items(source_dir: str, recursive: bool = False) -> Dict[str, List[MatchCandidate]]:
    """Escanea archivos y carpetas usando su nombre sin extensión como clave."""
    index: Dict[str, List[MatchCandidate]] = {}
    if not os.path.isdir(source_dir):
        return index

    if recursive:
        walker = os.walk(source_dir)
        for current_dir, dirnames, filenames in walker:
            for dirname in dirnames:
                _add_candidate(index, source_dir, os.path.join(current_dir, dirname), is_dir=True)
            for filename in filenames:
                _add_candidate(index, source_dir, os.path.join(current_dir, filename), is_dir=False)
    else:
        with os.scandir(source_dir) as entries:
            for entry in entries:
                if entry.is_file() or entry.is_dir():
                    _add_candidate(index, source_dir, entry.path, is_dir=entry.is_dir())

    return index


def copy_general_items(
    source_dir: str,
    requested_names: List[str],
    dest_dir: str,
    recursive: bool = False,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> Tuple[int, int, int, List[str]]:
    """Copia todos los archivos/carpetas cuyo nombre base está en requested_names.

    Returns:
        (entradas_encontradas, elementos_copiados, entradas_no_encontradas, lista_no_encontradas)
    """
    os.makedirs(dest_dir, exist_ok=True)

    index = scan_general_items(source_dir, recursive=recursive)
    found_entries = 0
    copied_items = 0
    missing: List[str] = []
    total = len(requested_names)

    for current, requested_name in enumerate(requested_names, start=1):
        if should_cancel and should_cancel():
            break

        key = normalize_base_name(requested_name)
        candidates = index.get(key, [])

        if not candidates:
            missing.append(requested_name)
        else:
            found_entries += 1
            for candidate in candidates:
                _copy_candidate(candidate, dest_dir)
                copied_items += 1

        if progress_callback:
            progress_callback(current, total)

    return found_entries, copied_items, len(missing), missing


def _add_candidate(index: Dict[str, List[MatchCandidate]], root: str, path: str, is_dir: bool):
    basename = os.path.basename(path)
    base_name = basename if is_dir else os.path.splitext(basename)[0]
    key = normalize_base_name(base_name)
    if not key:
        return

    relative_path = os.path.relpath(path, root)
    index.setdefault(key, []).append(
        MatchCandidate(source_path=path, relative_path=relative_path, is_dir=is_dir)
    )


def _copy_candidate(candidate: MatchCandidate, dest_dir: str):
    dest_path = os.path.join(dest_dir, candidate.relative_path)
    parent_dir = os.path.dirname(dest_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    if candidate.is_dir:
        shutil.copytree(candidate.source_path, dest_path, dirs_exist_ok=True)
    else:
        shutil.copy2(candidate.source_path, dest_path)


def _strip_simple_extension(name: str) -> str:
    """Quita una extensión accidental si el texto parece un nombre de fichero."""
    base = os.path.basename(name)
    stem, ext = os.path.splitext(base)
    if ext.lower() in KNOWN_EXTENSIONS and stem and os.path.dirname(name) == "":
        return stem
    return name
