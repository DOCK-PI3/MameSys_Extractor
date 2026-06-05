"""
Parser para archivos catver.ini de MAME.

Formato:
    ; comentarios
    nombre_rom=Categoría / Subcategoría

Ejemplo:
    sf2=Fighter / Versus
    mslug=Shooter / Walking
    neogeo=NeoGeo
"""

import os
import re
from typing import Dict, List


def parse_catver(filepath: str) -> Dict[str, str]:
    """
    Parsea un archivo catver.ini y devuelve un diccionario
    {nombre_rom: categoria}.
    
    El catver.ini de MAME tiene múltiples secciones:
    - [Category]: categorías reales (géneros)
    - Otras secciones: números de versión, etc.
    
    Solo se procesa la sección [Category] para evitar que
    entradas de versión sobreescriban las categorías.
    Si no se encuentra [Category], se procesa todo el archivo.
    """
    categories: Dict[str, str] = {}
    
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"No se encontró el archivo: {filepath}")
    
    in_category_section = False
    found_category_header = False
    
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            stripped = line.strip()
            
            # Detectar secciones
            if stripped.startswith("[") and stripped.endswith("]"):
                if stripped.lower() == "[category]":
                    found_category_header = True
                    in_category_section = True
                else:
                    in_category_section = False
                continue
            
            # Si no se ha encontrado [Category] aún, procesar todo
            # (modo compatibilidad para archivos sin secciones)
            if not found_category_header and not in_category_section:
                in_category_section = True
            
            # Solo procesar si estamos en la sección correcta
            if not in_category_section:
                continue
            
            # Ignorar líneas vacías y comentarios
            if not stripped or stripped.startswith(";") or stripped.startswith("#"):
                continue
            
            # Separar por el primer '='
            if "=" in stripped:
                rom, category = stripped.split("=", 1)
                rom = rom.strip()
                category = category.strip()
                if rom and category:
                    categories[rom] = category
    
    return categories


def filter_by_keywords(
    catver_data: Dict[str, str],
    keywords: List[str],
    case_sensitive: bool = False,
) -> Dict[str, str]:
    """
    Filtra el diccionario catver por palabras clave.
    Devuelve {rom: categoria} de las ROMs cuya categoría
    contiene AL MENOS UNA de las keywords.
    """
    if not keywords:
        return {}
    
    result: Dict[str, str] = {}
    
    for rom, category in catver_data.items():
        cat_check = category if case_sensitive else category.lower()
        for kw in keywords:
            kw_check = kw if case_sensitive else kw.lower()
            if kw_check in cat_check:
                result[rom] = category
                break
    
    return result


# ------------------------------------------------------------------
# Extracción de categorías reales del catver.ini
# ------------------------------------------------------------------

# Las categorías de catver.ini son géneros (Fighter, Shooter, etc.),
# pero también contiene strings de versión (0.146u5) que NO son categorías.
_VERSION_PATTERN = re.compile(r'^\d+\.\d+[a-z]?.*$')


def _get_top_category(cat_val: str) -> str:
    """Extrae la categoría principal de un valor tipo 'Fighter / Versus'."""
    if ' / ' in cat_val:
        return cat_val.split(' / ', 1)[0].strip()
    return cat_val.strip()


def extract_categories_from_catver(
    catver_data: Dict[str, str]
) -> Dict[str, int]:
    """
    Extrae las categorías reales (top-level) del catver.ini.
    
    El formato del catver.ini es:
        rom=TopCategory / SubCategory
        rom=TopCategory
    
    Esta función extrae la parte antes de ' / ' como categoría
    principal y cuenta cuántas ROMs hay en cada una.
    
    Filtra strings que parecen números de versión (0.146u5, 0.162, etc.).
    """
    categories: Dict[str, int] = {}
    
    for cat_val in catver_data.values():
        top_cat = _get_top_category(cat_val)
        
        # Saltar strings que son versiones (0.146u5, 0.162, etc.)
        if _VERSION_PATTERN.match(top_cat):
            continue
        
        if top_cat:
            categories[top_cat] = categories.get(top_cat, 0) + 1
    
    return categories


def filter_by_top_category(
    catver_data: Dict[str, str],
    category_name: str,
) -> Dict[str, str]:
    """
    Filtra las ROMs cuya categoría principal (top-level) coincida
    exactamente con `category_name` (case-insensitive).
    
    Ejemplo: category_name='Fighter' encuentra ROMs con
    categoría 'Fighter / Versus', 'Fighter / Scrolling', 'Fighter', etc.
    """
    result: Dict[str, str] = {}
    cat_lower = category_name.lower()
    
    for rom, cat_val in catver_data.items():
        if _get_top_category(cat_val).lower() == cat_lower:
            result[rom] = cat_val
    
    return result


def extract_subcategories_from_catver(
    catver_data: Dict[str, str]
) -> Dict[str, int]:
    """
    Extrae las subcategorías completas del catver.ini.
    
    Devuelve { 'Fighter / Versus': 1017, 'Shooter / Flying Vertical': 832, ... }
    Solo incluye entradas que tienen ' / ' (categoría + subcategoría).
    Filtra strings que son números de versión.
    """
    subcategories: Dict[str, int] = {}
    
    for cat_val in catver_data.values():
        # Solo entradas con subcategoría real (tienen ' / ')
        if ' / ' not in cat_val:
            continue
        # Saltar versiones
        top_cat = _get_top_category(cat_val)
        if _VERSION_PATTERN.match(top_cat):
            continue
        
        subcategories[cat_val] = subcategories.get(cat_val, 0) + 1
    
    return subcategories


def filter_by_full_category(
    catver_data: Dict[str, str],
    full_category: str,
) -> Dict[str, str]:
    """
    Filtra las ROMs cuya categoría COMPLETA coincida exactamente
    con `full_category` (case-insensitive).
    
    Ejemplo: full_category='Fighter / Versus' solo encuentra ROMs
    con esa categoría exacta, no 'Fighter / Scrolling'.
    """
    result: Dict[str, str] = {}
    cat_lower = full_category.lower()
    
    for rom, cat_val in catver_data.items():
        if cat_val.lower() == cat_lower:
            result[rom] = cat_val
    
    return result


# ------------------------------------------------------------------
# Perfiles predefinidos de sistemas de arcade (por fabricante/hardware)
# ------------------------------------------------------------------
# NOTA: catver.ini categoriza por género (Fighter, Shooter, etc.),
# no por hardware. Algunas versiones incluyen el sistema en la
# categoría (ej: "NeoGeo"). Si no encuentras un sistema, prueba
# con palabras clave más genéricas (ej: el fabricante).
SYSTEM_PROFILES: Dict[str, List[str]] = {
    # --- Capcom ---
    "CPS1": [
        "capcom play system 1",
        "cps-1",
        "cps1",
    ],
    "CPS2": [
        "capcom play system 2",
        "cps-2",
        "cps2",
    ],
    "CPS3": [
        "capcom play system 3",
        "cps-3",
        "cps3",
    ],
    "Capcom (otras)": [
        "capcom",
    ],

    # --- SNK / NeoGeo ---
    "NeoGeo": [
        "neogeo",
        "neo geo",
        "neo-geo",
    ],
    "SNK (pre-NeoGeo)": [
        "snk",
    ],

    # --- Sega ---
    "Sega System 1": [
        "sega system 1",
    ],
    "Sega System 16": [
        "sega system 16",
        "system 16",
    ],
    "Sega System 18": [
        "sega system 18",
        "system 18",
    ],
    "Sega System 24": [
        "sega system 24",
        "system 24",
    ],
    "Sega System 32": [
        "sega system 32",
        "system 32",
    ],
    "Sega Model 1": [
        "sega model 1",
        "model 1",
    ],
    "Sega Model 2": [
        "sega model 2",
        "model 2",
    ],
    "Sega Model 3": [
        "sega model 3",
        "model 3",
    ],
    "Sega NAOMI": [
        "naomi",
        "sega naomi",
    ],
    "Sega NAOMI 2": [
        "naomi 2",
        "sega naomi 2",
    ],
    "Sega ST-V": [
        "st-v",
        "stv",
        "sega st-v",
        "sega titan",
    ],
    "Sega (otras)": [
        "sega",
    ],

    # --- Namco ---
    "Namco System 1": [
        "namco system 1",
    ],
    "Namco System 2": [
        "namco system 2",
    ],
    "Namco System 21": [
        "namco system 21",
    ],
    "Namco System 22": [
        "namco system 22",
    ],
    "Namco ND-1": [
        "namco nd-1",
        "nd-1",
    ],
    "Namco (otras)": [
        "namco",
    ],

    # --- Konami ---
    "Konami GX": [
        "konami gx",
    ],
    "Konami System 573": [
        "system 573",
        "konami 573",
    ],
    "Konami GV": [
        "konami gv",
    ],
    "Konami (otras)": [
        "konami",
    ],

    # --- Taito ---
    "Taito F3": [
        "taito f3",
    ],
    "Taito FX-1A": [
        "taito fx",
        "fx-1a",
    ],
    "Taito G-NET": [
        "taito g-net",
        "g-net",
    ],
    "Taito (otras)": [
        "taito",
    ],

    # --- Irem ---
    "Irem M72": [
        "irem m72",
        "m72",
    ],
    "Irem M92": [
        "irem m92",
        "m92",
    ],
    "Irem (otras)": [
        "irem",
    ],

    # --- Kaneko ---
    "Kaneko Super Nova": [
        "kaneko super nova",
        "super nova",
        "kaneko",
    ],

    # --- Sammy ---
    "Sammy Atomiswave": [
        "atomiswave",
        "sammy atomiswave",
        "sammy",
    ],

    # --- Seta ---
    "Seta": [
        "seta",
    ],

    # --- Nintendo ---
    "Nintendo": [
        "nintendo",
    ],
    "Nintendo PlayChoice-10": [
        "playchoice",
        "playchoice-10",
    ],
    "Nintendo Vs.": [
        "nintendo vs",
        "vs. system",
        "vs system",
    ],

    # --- Midway / Williams / Atari ---
    "Midway": [
        "midway",
    ],
    "Williams": [
        "williams",
    ],
    "Atari": [
        "atari",
    ],
    "Atari System 1": [
        "atari system 1",
    ],
    "Atari System 2": [
        "atari system 2",
    ],

    # --- Psikyo ---
    "Psikyo": [
        "psikyo",
    ],
    "Psikyo SH2": [
        "psikyo sh2",
        "psikyo",
    ],

    # --- Seibu Kaihatsu ---
    "Seibu Kaihatsu": [
        "seibu",
        "seibu kaihatsu",
    ],

    # --- Raizing / Eighting ---
    "Raizing / Eighting": [
        "raizing",
        "eighting",
    ],

    # --- Tecmo ---
    "Tecmo": [
        "tecmo",
    ],

    # --- Mitchell ---
    "Mitchell": [
        "mitchell",
    ],

    # --- Gaelco ---
    "Gaelco": [
        "gaelco",
    ],
    "Gaelco 3D": [
        "gaelco 3d",
        "gaelco",
    ],

    # --- Jaleco ---
    "Jaleco": [
        "jaleco",
    ],
    "Jaleco Mega System 32": [
        "mega system 32",
        "jaleco",
    ],

    # --- Nichibutsu ---
    "Nichibutsu": [
        "nichibutsu",
    ],

    # --- Universal ---
    "Universal": [
        "universal",
    ],

    # --- Toaplan ---
    "Toaplan": [
        "toaplan",
    ],

    # --- Cave ---
    "Cave": [
        "cave",
    ],
    "Cave CV1000": [
        "cv1000",
        "cave",
    ],

    # --- Data East ---
    "Data East": [
        "data east",
    ],

    # --- Otros fabricantes ---
    "Banpresto": [
        "banpresto",
    ],
    "Bally": [
        "bally",
    ],
    "Cinematronics": [
        "cinematronics",
    ],
    "Exidy": [
        "exidy",
    ],
    "Gottlieb": [
        "gottlieb",
    ],
    "Stern": [
        "stern",
    ],
    "Century": [
        "century",
    ],
    "Technos": [
        "technos",
    ],
    "Visco": [
        "visco",
    ],
    "NMK": [
        "nmk",
    ],
    "UPL": [
        "upl",
    ],
    "IGS": [
        "igs",
        "igs pgm",
    ],
    "IGS PGM2": [
        "pgm2",
        "igs pgm2",
    ],
}


def get_available_systems(
    catver_data: Dict[str, str],
) -> Dict[str, int]:
    """
    Devuelve un diccionario {nombre: cantidad_de_roms} combinando:
    1. Sistemas predefinidos (SYSTEM_PROFILES) que tienen ROMs
    2. Categorías reales extraídas del catver.ini
    3. Subcategorías (con prefijo '  └ ') para filtrar por género exacto
    
    Las categorías reales son géneros como Fighter, Shooter, Sports...
    Las subcategorías son como 'Fighter / Versus', 'Shooter / Flying Vertical'.
    """
    available: Dict[str, int] = {}
    
    # 1. Sistemas predefinidos (fabricantes/hardware)
    for system_name, keywords in SYSTEM_PROFILES.items():
        matches = filter_by_keywords(catver_data, keywords, case_sensitive=False)
        if matches:
            available[system_name] = len(matches)
    
    # 2. Categorías reales del archivo (géneros)
    real_categories = extract_categories_from_catver(catver_data)
    for cat_name, count in sorted(real_categories.items()):
        if cat_name not in available:
            available[cat_name] = count
    
    # 3. Subcategorías (con prefijo visual para distinguirlas)
    # Se muestran después de las categorías principales
    subcategories = extract_subcategories_from_catver(catver_data)
    for subcat_name, count in sorted(subcategories.items()):
        display_name = f"  └ {subcat_name}"
        if display_name not in available:
            available[display_name] = count
    
    return available


# Prefijo usado para identificar subcategorías en la lista
SUBCATEGORY_PREFIX = "  └ "


def get_system_roms(
    catver_data: Dict[str, str],
    system_name: str,
) -> Dict[str, str]:
    """
    Devuelve las ROMs de un sistema, categoría o subcategoría.
    
    - Si el nombre es un sistema predefinido → filter_by_keywords
    - Si el nombre tiene prefijo de subcategoría → filter_by_full_category
    - Si no → filter_by_top_category (categoría principal)
    """
    # 1. Sistema predefinido (fabricante/hardware)
    if system_name in SYSTEM_PROFILES:
        return filter_by_keywords(
            catver_data, SYSTEM_PROFILES[system_name], case_sensitive=False
        )
    
    # 2. Subcategoría (tiene el prefijo '  └ ')
    if system_name.startswith(SUBCATEGORY_PREFIX):
        full_cat = system_name[len(SUBCATEGORY_PREFIX):]
        return filter_by_full_category(catver_data, full_cat)
    
    # 3. Categoría principal (top-level)
    return filter_by_top_category(catver_data, system_name)
