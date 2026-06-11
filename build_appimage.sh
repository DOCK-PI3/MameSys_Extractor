#!/usr/bin/env bash
# ==============================================================================
# build_appimage.sh — Compila MameSys Extractor como AppImage para Linux
#
# Requisitos:
#   - Ubuntu 20.04+ (o WSL2 con Ubuntu) en arquitectura x86_64
#   - Conexión a internet (descarga appimagetool)
#
# Uso:
#   chmod +x build_appimage.sh
#   ./build_appimage.sh
#
# El AppImage se generará en: dist/MameSys_Extractor-*.AppImage
# ==============================================================================

set -euo pipefail

# --- Configuración -----------------------------------------------------------
APP_NAME="MameSys_Extractor"
APP_TITLE="MameSys Extractor"
APP_GENERIC_NAME="ROM Manager"
APP_COMMENT="Organiza y extrae sistemas completos desde tu colección de MAME"
APP_CATEGORIES="Utility;Archiving;"
APP_VERSION=$(grep -Po 'VERSION\s*=\s*"\K[^"]*' src/app.py)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build_appimage"
APPDIR="${BUILD_DIR}/${APP_NAME}.AppDir"
DIST_DIR="${SCRIPT_DIR}/dist"

# Colores para terminal
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# --- Utilidades --------------------------------------------------------------
log()  { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $1"; }
warn() { echo -e "${YELLOW}[AVISO]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# --- Verificación de entorno -------------------------------------------------
check_requirements() {
    log "Verificando requisitos del sistema..."

    # Verificar que estamos en Linux x86_64
    local arch
    arch=$(uname -m)
    if [[ "$arch" != "x86_64" ]]; then
        err "Arquitectura no soportada: $arch. Se requiere x86_64."
    fi

    # Python 3
    if ! command -v python3 &>/dev/null; then
        log "Python 3 no encontrado. Instalando..."
        sudo apt-get update -qq
        sudo apt-get install -y -qq python3 python3-pip python3-venv
    fi
    log "  ✓ Python $(python3 --version)"

    # pip
    if ! python3 -m pip --version &>/dev/null; then
        log "Instalando pip..."
        sudo apt-get install -y -qq python3-pip
    fi
    log "  ✓ pip $(python3 -m pip --version | awk '{print $2}')"

    # Dependencias del sistema para PySide6 / Qt
    log "Instalando dependencias de sistema para PySide6/Qt..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq \
        libxcb-cursor0 \
        libxcb-icccm4 \
        libxcb-image0 \
        libxcb-keysyms1 \
        libxcb-randr0 \
        libxcb-render-util0 \
        libxcb-shape0 \
        libxcb-sync1 \
        libxcb-util1 \
        libxcb-xfixes0 \
        libxcb-xinerama0 \
        libxcb-xkb1 \
        libxkbcommon-x11-0 \
        libgl1-mesa-glx \
        libegl1-mesa \
        libfontconfig1 \
        libfreetype6 \
        libdbus-1-3 \
        file \
        wget \
        2>/dev/null

    log "  ✓ Dependencias de sistema instaladas"
}

# --- Icono -------------------------------------------------------------------
generate_icon_png() {
    log "Generando icono PNG para AppImage..."

    # Instalar Pillow para poder leer/generar imágenes
    python3 -m pip install -q Pillow 2>/dev/null || true

    # Generar el .ico usando el script existente del proyecto
    if [[ -f "mame.ico" ]]; then
        log "  Usando mame.ico existente..."
    else
        python3 generate_icon.py
        if [[ ! -f "mame.ico" ]]; then
            warn "generate_icon.py no creó mame.ico, generando PNG minimalista..."
            python3 -c "
from PIL import Image
import os
os.makedirs('build_appimage', exist_ok=True)
img = Image.new('RGBA', (256, 256), (43, 43, 58, 255))
img.save('build_appimage/${APP_NAME}.png', 'PNG')
img.resize((64, 64), Image.Resampling.LANCZOS).save('build_appimage/${APP_NAME}_64.png', 'PNG')
"
            return
        fi
    fi

    # Convertir el .ico a .png (necesario para AppImage en Linux)
    python3 -c "
from PIL import Image
import os

os.makedirs('build_appimage', exist_ok=True)
img = Image.open('mame.ico')

# Guardar en los tamaños necesarios (Pillow abre el frame más grande por defecto)
img.save('build_appimage/${APP_NAME}.png', 'PNG')
img.resize((64, 64), Image.Resampling.LANCZOS).save('build_appimage/${APP_NAME}_64.png', 'PNG')
print('Icono PNG generado correctamente')
"

    log "  ✓ Icono PNG generado desde mame.ico"
}

# --- PyInstaller build -------------------------------------------------------
run_pyinstaller() {
    log "Instalando dependencias Python..."
    python3 -m pip install -q --upgrade pip
    python3 -m pip install -q pyinstaller PySide6 Pillow

    log "  ✓ PyInstaller $(pyinstaller --version)"
    log "  ✓ PySide6 $(python3 -c 'import PySide6; print(PySide6.__version__)')"

    log "Sincronizando versión desde src/app.py..."
    python3 sync_version.py

    log "Ejecutando PyInstaller (modo --onedir)..."
    pyinstaller \
        --onedir \
        --windowed \
        --name "${APP_NAME}" \
        --icon="build_appimage/${APP_NAME}.png" \
        --add-data "src:src" \
        --clean \
        --noconfirm \
        main.py

    if [[ ! -d "${DIST_DIR}/${APP_NAME}" ]]; then
        err "PyInstaller no generó el directorio esperado: ${DIST_DIR}/${APP_NAME}"
    fi

    log "  ✓ Build de PyInstaller completado"
}

# --- AppDir ------------------------------------------------------------------
create_appdir() {
    log "Creando estructura AppDir..."

    # Limpiar build anterior
    rm -rf "${APPDIR}"
    mkdir -p "${APPDIR}"

    # Copiar el output de PyInstaller al AppDir
    cp -a "${DIST_DIR}/${APP_NAME}/"* "${APPDIR}/"

    # Crear AppRun
    cat > "${APPDIR}/AppRun" << 'APPRUNEOF'
#!/usr/bin/env bash
# AppRun para MameSys Extractor
# PyInstaller --onedir ya gestiona sus propias rutas de librerías.

SELF="$(dirname "$(readlink -f "$0")")"

# Asegurar que los plugins Qt de PySide6 son localizables
if [[ -d "${SELF}/_internal/PySide6/Qt/plugins" ]]; then
    export QT_PLUGIN_PATH="${SELF}/_internal/PySide6/Qt/plugins"
fi

exec "${SELF}/${APP_NAME}" "$@"
APPRUNEOF

    chmod +x "${APPDIR}/AppRun"
    log "  ✓ AppRun creado"

    # Crear archivo .desktop
    cat > "${APPDIR}/${APP_NAME}.desktop" << DESKEOF
[Desktop Entry]
Type=Application
Name=${APP_TITLE}
GenericName=${APP_GENERIC_NAME}
Comment=${APP_COMMENT}
Exec=AppRun
Icon=${APP_NAME}
Categories=${APP_CATEGORIES}
Terminal=false
X-AppImage-Version=${APP_VERSION}
DESKEOF

    log "  ✓ Archivo .desktop creado"

    # Copiar icono al AppDir
    cp "${BUILD_DIR}/${APP_NAME}.png" "${APPDIR}/${APP_NAME}.png"
    log "  ✓ Icono copiado al AppDir"

    # Copiar iconos a estructura hicolor (buena práctica)
    mkdir -p "${APPDIR}/usr/share/icons/hicolor/64x64/apps"
    mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"
    cp "${BUILD_DIR}/${APP_NAME}_64.png" \
       "${APPDIR}/usr/share/icons/hicolor/64x64/apps/${APP_NAME}.png"
    cp "${BUILD_DIR}/${APP_NAME}.png" \
       "${APPDIR}/usr/share/icons/hicolor/256x256/apps/${APP_NAME}.png"

    # Mover el .desktop a su ubicación estándar
    mkdir -p "${APPDIR}/usr/share/applications"
    cp "${APPDIR}/${APP_NAME}.desktop" \
       "${APPDIR}/usr/share/applications/${APP_NAME}.desktop"

    log "  ✓ Estructura AppDir completa"
}

# --- AppImage packaging ------------------------------------------------------
package_appimage() {
    log "Descargando appimagetool..."

    local APPIMAGETOOL_URL
    APPIMAGETOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"

    local APPIMAGETOOL="${BUILD_DIR}/appimagetool.AppImage"

    if [[ ! -f "${APPIMAGETOOL}" ]]; then
        wget -q --show-progress -O "${APPIMAGETOOL}" "${APPIMAGETOOL_URL}" || \
            err "No se pudo descargar appimagetool. Comprueba tu conexión a internet."
        chmod +x "${APPIMAGETOOL}"
    fi
    log "  ✓ appimagetool listo"

    # Generar nombre de archivo con versión
    local BUILD_DATE
    BUILD_DATE=$(date +%Y%m%d)
    local OUTPUT_NAME="${APP_NAME}-v${APP_VERSION}-${BUILD_DATE}-x86_64.AppImage"

    log "Empaquetando AppImage: ${OUTPUT_NAME}..."

    # appimagetool necesita ciertas variables de entorno en algunos entornos
    export ARCH=x86_64

    "${APPIMAGETOOL}" \
        "${APPDIR}" \
        "${DIST_DIR}/${OUTPUT_NAME}" \
        2>&1 | while IFS= read -r line; do
            # Silenciar warnings de librerías del sistema que no deben bundlearze
            if [[ ! "$line" =~ "glibc" ]] && [[ ! "$line" =~ "WARNING" ]]; then
                echo "  $line"
            fi
        done

    if [[ ! -f "${DIST_DIR}/${OUTPUT_NAME}" ]]; then
        err "No se generó el AppImage. Revisa los mensajes anteriores."
    fi

    chmod +x "${DIST_DIR}/${OUTPUT_NAME}"

    local size
    size=$(du -h "${DIST_DIR}/${OUTPUT_NAME}" | cut -f1)

    echo ""
    echo -e "${CYAN}================================================================${NC}"
    echo -e "${CYAN}  AppImage generado exitosamente${NC}"
    echo -e "${CYAN}================================================================${NC}"
    echo -e "  Archivo : ${GREEN}${DIST_DIR}/${OUTPUT_NAME}${NC}"
    echo -e "  Tamaño  : ${size}"
    echo -e "  Versión : v${APP_VERSION} (build ${BUILD_DATE})"
    echo -e "  Arquitectura : x86_64"
    echo -e "${CYAN}================================================================${NC}"
    echo ""
    echo "Para ejecutar:"
    echo "  chmod +x dist/${OUTPUT_NAME}"
    echo "  ./dist/${OUTPUT_NAME}"
    echo ""
    echo -e "${YELLOW}Nota:${NC} Si el AppImage no ejecuta, instala FUSE:"
    echo "  sudo apt-get install -y fuse libfuse2"
    echo ""
}

# --- Limpieza ----------------------------------------------------------------
cleanup() {
    log "Limpiando archivos temporales de build..."
    rm -rf "${BUILD_DIR}"
    rm -rf "${SCRIPT_DIR}/build"
    rm -f "${SCRIPT_DIR}/${APP_NAME}.spec"
    log "  ✓ Limpieza completada"
}

# --- Main --------------------------------------------------------------------
main() {
    echo ""
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}  ${APP_TITLE} — AppImage Builder${NC}"
    echo -e "${CYAN}  v${APP_VERSION} · Linux x86_64${NC}"
    echo -e "${CYAN}============================================${NC}"
    echo ""

    cd "${SCRIPT_DIR}"

    check_requirements
    generate_icon_png
    run_pyinstaller
    create_appdir
    package_appimage
    cleanup

    log "¡Listo!"
}

main "$@"
