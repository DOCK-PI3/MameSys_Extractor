@echo off
chcp 65001 >nul
echo ============================================
echo   MameSys Extractor - Build Script
echo ============================================
echo.

:: Verificar / generar el icono
if not exist "mame.ico" (
    echo [!] No se encontro mame.ico. Generando automaticamente...
    python generate_icon.py
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] No se pudo generar el icono.
        pause
        exit /b 1
    )
    echo [OK] Icono generado correctamente.
    echo.
) else (
    echo [OK] Icono mame.ico encontrado.
    echo.
)

:: Preguntar si quiere regenerar el icono
set /p regen="[?] Regenerar el icono? (s/N): "
if /i "%regen%"=="s" (
    echo     Regenerando icono...
    python generate_icon.py
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] No se pudo regenerar el icono.
        pause
        exit /b 1
    )
    echo     Icono regenerado.
)

echo.
echo ============================================
echo   Iniciando build...
echo ============================================
echo.

:: Sincronizar version.txt desde src/app.py
echo [0/4] Sincronizando version desde src/app.py...
python sync_version.py
if %ERRORLEVEL% neq 0 (
    echo [ERROR] No se pudo sincronizar la version.
    pause
    exit /b 1
)
echo.

:: Limpiar builds anteriores
echo [1/4] Limpiando builds anteriores...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "*.spec" del /q "*.spec"

:: Construir el .exe
echo [2/4] Construyendo MameSys_Extractor.exe...
python -m PyInstaller --onefile --windowed --name "MameSys_Extractor" --icon="mame.ico" --version-file="version.txt" --clean main.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] La build fallo con codigo %ERRORLEVEL%.
    pause
    exit /b %ERRORLEVEL%
)

:: Verificar que el .exe se genero
if not exist "dist\MameSys_Extractor.exe" (
    echo [ERROR] No se genero el .exe correctamente.
    pause
    exit /b 1
)

echo [3/4] Verificando ejecutable...
for %%A in ("dist\MameSys_Extractor.exe") do set size=%%~zA
set /a size_mb=%size% / 1048576
echo.

echo ============================================
echo   Build completada con exito!
echo ============================================
echo   Ejecutable: dist\MameSys_Extractor.exe
echo   Tamaño:     %size_mb% MB
echo   Icono:      mame.ico
echo   Version:    auto-sincronizada desde src\app.py
echo ============================================
echo.

pause
