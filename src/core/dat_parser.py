"""
Parser para archivos .dat de clrmamepro (formato LogiqX XML).

Formato:
    <?xml version="1.0"?>
    <datafile>
        <header>
            <name>Sistema</name>
            <description>Descripción</description>
        </header>
        <game name="rom1">
            <description>Nombre del juego</description>
            <rom name="archivo.bin" size="1234" crc="abcdef12"/>
        </game>
        ...
    </datafile>

Cada archivo .dat representa un sistema de arcade. Los nombres de ROM
se extraen del atributo 'name' de los elementos <game> y <machine>.
"""

import os
from typing import Dict, Tuple, Callable, Optional
from xml.etree import ElementTree


def parse_dat_file(
    filepath: str,
    log_callback: Optional[Callable[[str], None]] = None,
) -> Tuple[str, Dict[str, str]]:
    """
    Parsea un archivo .dat de clrmamepro.

    Args:
        filepath: Ruta al archivo .dat.
        log_callback: Función opcional para recibir mensajes de advertencia.

    Returns:
        (nombre_sistema, {nombre_rom: descripcion})

        El nombre del sistema se obtiene del <header><name>,
        <header><description> o del nombre del archivo (en ese orden).

        La clave del diccionario es el nombre del juego/ROM
        (atributo 'name' de <game> o <machine>).

    Raises:
        FileNotFoundError: Si el archivo no existe.
        ElementTree.ParseError: Si el XML está mal formado.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"No se encontró el archivo: {filepath}")

    tree = ElementTree.parse(filepath)
    root = tree.getroot()

    # Extraer nombre del sistema del header (una sola lectura del XML)
    system_name = _extract_system_name_from_root(root)

    # Si no se pudo extraer, usar el nombre del archivo
    if not system_name:
        system_name = os.path.splitext(os.path.basename(filepath))[0]
        if log_callback:
            log_callback(
                f"  ⚠ {os.path.basename(filepath)}: sin <name> en header, "
                f"usando nombre de archivo '{system_name}'"
            )

    # Extraer juegos/ROMs
    games: Dict[str, str] = {}
    for element in root.iter():
        tag = element.tag.lower() if hasattr(element, 'tag') else ""

        if tag in ("game", "machine"):
            game_name = element.attrib.get("name", "").strip()
            if not game_name:
                continue

            # Intentar obtener la descripción
            description = element.attrib.get("description", "")
            if not description:
                desc_elem = element.find("description")
                if desc_elem is not None and desc_elem.text:
                    description = desc_elem.text.strip()

            games[game_name] = description or game_name

    if not games and log_callback:
        log_callback(
            f"  ⚠ {os.path.basename(filepath)}: no tiene elementos <game> o <machine>"
        )

    return system_name, games


def parse_dat_folder(
    folder_path: str,
    log_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Dict[str, str]]:
    """
    Escanea una carpeta en busca de archivos .dat y los parsea todos.

    Args:
        folder_path: Carpeta que contiene archivos .dat.
        log_callback: Función opcional para recibir mensajes de advertencia/error.

    Returns:
        {nombre_sistema: {nombre_rom: descripcion}}

    Raises:
        NotADirectoryError: Si la carpeta no existe.
    """
    if not os.path.isdir(folder_path):
        raise NotADirectoryError(f"No es un directorio: {folder_path}")

    systems: Dict[str, Dict[str, str]] = {}
    dat_files = sorted(
        f for f in os.listdir(folder_path) if f.lower().endswith(".dat")
    )

    for filename in dat_files:
        filepath = os.path.join(folder_path, filename)

        try:
            system_name, games = parse_dat_file(filepath, log_callback)

            if not games:
                if log_callback:
                    log_callback(f"  ⚠ {filename}: sin ROMs, omitido.")
                continue

            # Manejar nombres de sistema duplicados
            if system_name in systems:
                base_name = system_name
                suffix = 2
                while system_name in systems:
                    system_name = f"{base_name} ({suffix})"
                    suffix += 1
                if log_callback:
                    log_callback(
                        f"  ⚠ {filename}: nombre duplicado '{base_name}', "
                        f"renombrado a '{system_name}'"
                    )

            systems[system_name] = games

        except ElementTree.ParseError as e:
            if log_callback:
                log_callback(f"  ❌ {filename}: XML mal formado ({e})")
        except FileNotFoundError as e:
            if log_callback:
                log_callback(f"  ❌ {filename}: {e}")
        except Exception as e:
            if log_callback:
                log_callback(f"  ❌ {filename}: error inesperado ({e})")

    return systems


def _extract_system_name_from_root(root) -> str:
    """
    Extrae el nombre del sistema del <header> de un XML ya parseado.
    Busca en orden: <name>, <description>.
    """
    header = root.find("header")
    if header is not None:
        for tag_name in ("name", "description"):
            elem = header.find(tag_name)
            if elem is not None and elem.text:
                name = elem.text.strip()
                if name and len(name) < 100:
                    return name
    return ""
