"""
Operaciones de archivo para gestionar ROMs de MAME.

Incluye:
- Escanear directorio de ROMs (.zip)
- Copiar ROMs a carpetas de destino
- Procesar listas de nombres de ROMs desde archivos
"""

import os
import shutil
import re
from typing import Dict, List, Set, Tuple, Optional
from xml.etree import ElementTree


def scan_roms(source_dir: str) -> Set[str]:
    """
    Escanea un directorio y devuelve un conjunto con los nombres
    de los archivos .zip/.7z y carpetas que contienen CHD.
    
    Ejemplo: 'sf2.zip' -> 'sf2', 'mslug.7z' -> 'mslug'
    """
    roms: Set[str] = set()
    if not os.path.isdir(source_dir):
        return roms
    
    with os.scandir(source_dir) as entries:
        for entry in entries:
            lower = entry.name.lower()
            if entry.is_file() and lower.endswith(".zip"):
                roms.add(lower[:-4])
            elif entry.is_file() and lower.endswith(".7z"):
                roms.add(lower[:-3])
            elif entry.is_dir() and _directory_contains_chd(entry.path):
                roms.add(lower)
    
    return roms


def copy_roms(
    source_dir: str,
    rom_names: Set[str],
    dest_dir: str,
    progress_callback=None,
    should_cancel=None,
) -> Tuple[int, int, List[str]]:
    """
    Copia archivos .zip/.7z y carpetas CHD desde source_dir a dest_dir
    cuyos nombres estén en rom_names.
    
    Args:
        source_dir: Directorio con los .zip
        rom_names: Nombres de ROMs a copiar (sin extensión)
        dest_dir: Directorio de destino
        progress_callback: Función opcional (actual, total) para progreso
    
    Returns:
        (copiados, no_encontrados, lista_de_no_encontrados)
    """
    os.makedirs(dest_dir, exist_ok=True)
    
    copied = 0
    not_found: List[str] = []
    total = len(rom_names)
    
    for i, rom_name in enumerate(sorted(rom_names)):
        if should_cancel and should_cancel():
            break

        source_file = os.path.join(source_dir, f"{rom_name}.zip")
        copied_set = False

        if os.path.isfile(source_file):
            dest_file = os.path.join(dest_dir, f"{rom_name}.zip")
            shutil.copy2(source_file, dest_file)
            copied_set = True
        else:
            source_file_7z = os.path.join(source_dir, f"{rom_name}.7z")
            if os.path.isfile(source_file_7z):
                dest_file = os.path.join(dest_dir, f"{rom_name}.7z")
                shutil.copy2(source_file_7z, dest_file)
                copied_set = True

        # Los juegos basados en disco suelen tener ZIP de metadatos y una
        # carpeta homónima con uno o varios CHD. Hay que conservar ambos.
        source_chd_dir = os.path.join(source_dir, rom_name)
        if os.path.isdir(source_chd_dir) and _directory_contains_chd(source_chd_dir):
            dest_chd_dir = os.path.join(dest_dir, rom_name)
            shutil.copytree(source_chd_dir, dest_chd_dir, dirs_exist_ok=True)
            copied_set = True

        if copied_set:
            copied += 1
        else:
            not_found.append(rom_name)
        
        if progress_callback:
            progress_callback(i + 1, total)
    
    return copied, len(not_found), not_found


def _directory_contains_chd(directory: str) -> bool:
    """Indica si una carpeta de set contiene al menos un archivo CHD."""
    try:
        with os.scandir(directory) as entries:
            return any(entry.is_file() and entry.name.lower().endswith(".chd") for entry in entries)
    except OSError:
        return False


def parse_rom_list_file(filepath: str) -> Set[str]:
    """
    Parsea un archivo que contiene nombres de ROMs.
    
    Soporta:
    - Archivos de texto plano (un nombre por línea)
    - Archivos XML estilo MAME -listxml (busca atributos 'name' en
      elementos <machine>, <game> y <rom>).
    
    Devuelve un conjunto de nombres de ROMs (sin extensión).
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"No se encontró el archivo: {filepath}")
    
    rom_names: Set[str] = set()
    
    # Intentar parsear como XML de MAME primero
    try:
        tree = ElementTree.parse(filepath)
        root = tree.getroot()
        _extract_mame_xml_names(root, rom_names)
        if rom_names:
            return _clean_rom_names(rom_names)
    except ElementTree.ParseError:
        pass  # No es XML, procesar como texto
    
    # Procesar como texto plano (un nombre de ROM por línea)
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # Ignorar comentarios y líneas que parecen cabeceras
            if line.startswith(";") or line.startswith("#") or line.startswith("//"):
                continue
            # Ignorar líneas con demasiadas palabras (probablemente no son nombres de ROM)
            if len(line.split()) > 3:
                continue
            # Quitar extensión .zip / .7z
            if line.lower().endswith(".zip"):
                line = line[:-4]
            elif line.lower().endswith(".7z"):
                line = line[:-3]
            rom_names.add(line)
    
    return _clean_rom_names(rom_names)


def _extract_mame_xml_names(element, rom_names: Set[str]):
    """
    Extrae nombres de ROMs de un XML estilo MAME -listxml.
    Busca el atributo 'name' en elementos <machine>, <game> y <rom>.
    """
    tag = element.tag.lower() if hasattr(element, 'tag') else ""
    
    # Máquinas / juegos (formato MAME -listxml)
    if tag in ("machine", "game"):
        name = element.attrib.get("name", "").strip()
        if name:
            rom_names.add(name)
    
    # ROMs individuales (formato DAT / clrmamepro)
    if tag == "rom":
        name = element.attrib.get("name", "").strip()
        if name:
            rom_names.add(name)
    
    # Recursión en hijos
    for child in element:
        _extract_mame_xml_names(child, rom_names)


# Secciones de configuración conocidas que NO son categorías
_INI_CONFIG_SECTIONS = {'FOLDER_SETTINGS', 'ROOT_FOLDER'}


def parse_ini_categories(filepath: str) -> Dict[str, List[str]]:
    """
    Parsea un archivo .ini con estructura de categorías.
    
    Formato esperado:
      - Primeras líneas de cabecera (ignoradas hasta encontrar [(...)])
      - [(Nombre de Categoría)]
        rom1
        rom2
        ...
      - Separación entre categorías (línea en blanco)
    
    Returns:
        dict: {nombre_categoria: [lista_de_roms], ...}
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"No se encontró el archivo: {filepath}")
    
    categories: dict = {}
    current_category: Optional[str] = None
    
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            stripped = line.strip()
            
            # Ignorar líneas vacías
            if not stripped:
                continue
            
            # Detectar categoría: [(Nombre de la categoría)]
            cat_match = re.match(r'^\(\[(.+?)\]\)\s*$', stripped)
            if cat_match:
                current_category = cat_match.group(1).strip()
                if current_category not in categories:
                    categories[current_category] = []
                continue
            
            # También aceptar [Nombre Categoría] sin paréntesis,
            # siempre que no sea una sección de configuración conocida
            bracket_match = re.match(r'^\[(.+?)\]\s*$', stripped)
            if bracket_match:
                section_name = bracket_match.group(1).strip()
                if section_name not in _INI_CONFIG_SECTIONS:
                    current_category = section_name
                    if current_category not in categories:
                        categories[current_category] = []
                    continue
                else:
                    # Es una sección de configuración → ignorar
                    continue
            
            # Ignorar líneas de comentario
            if stripped.startswith(";") or stripped.startswith("#") or stripped.startswith("//"):
                continue
            
            # Ignorar líneas de configuración (clave=valor o clave valor)
            if re.match(r'^[A-Za-z_]\w*\s+', stripped) and len(stripped.split()) == 2:
                continue
            
            # Si estamos dentro de una categoría, añadir ROM
            if current_category is not None:
                # Limpiar nombre de ROM (quitar extensión si la tiene)
                rom_name = stripped.lower()
                for ext in ('.zip', '.7z', '.rom', '.bin'):
                    if rom_name.endswith(ext):
                        rom_name = rom_name[:-len(ext)]
                        break
                categories[current_category].append(rom_name)
    
    return categories


def _clean_rom_names(rom_names: Set[str]) -> Set[str]:
    """Limpia nombres de ROMs: quita extensiones, filtra entradas no válidas."""
    cleaned: Set[str] = set()
    for name in rom_names:
        name = name.strip()
        if not name:
            continue
        # Quitar extensión
        name = re.sub(r'\.(zip|7z|rom|bin)$', '', name, flags=re.IGNORECASE)
        # Filtrar strings que claramente no son nombres de ROM
        if len(name) > 50 or name.startswith("<?xml") or name.startswith("<!"):
            continue
        # Filtrar strings con espacios o barras (MAME ROMs son palabras simples)
        if " " in name or "/" in name or "\\" in name:
            continue
        cleaned.add(name)
    return cleaned
