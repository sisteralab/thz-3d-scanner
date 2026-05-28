@echo off
setlocal

cd /d "%~dp0"

set "APP_NAME=Scanner3D"
set "PYTHON_EXE=python"
set "PRESERVED_SETTINGS=%TEMP%\%APP_NAME%_settings_preserved.ini"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"

tasklist /FI "IMAGENAME eq %APP_NAME%.exe" 2>nul | find /I "%APP_NAME%.exe" >nul
if not errorlevel 1 (
    echo %APP_NAME%.exe is running. Close the application before building.
    exit /b 1
)

if exist "%PRESERVED_SETTINGS%" del /Q "%PRESERVED_SETTINGS%"
if exist "dist\%APP_NAME%\settings.ini" (
    echo Preserving settings from existing build.
    copy /Y "dist\%APP_NAME%\settings.ini" "%PRESERVED_SETTINGS%" >nul
) else if exist "settings.ini" (
    echo Using workspace settings.ini as initial build settings.
    copy /Y "settings.ini" "%PRESERVED_SETTINGS%" >nul
)

if not exist "assets\scanner3d.ico" (
    echo Missing assets\scanner3d.ico
    exit /b 1
)

if not exist "ximc" (
    echo Missing ximc directory
    exit /b 1
)

%PYTHON_EXE% -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo PyInstaller is not installed. Installing it into the selected Python environment...
    %PYTHON_EXE% -m pip install pyinstaller
    if errorlevel 1 exit /b 1
)

%PYTHON_EXE% -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --windowed ^
    --name "%APP_NAME%" ^
    --icon "assets\scanner3d.ico" ^
    --add-data "assets;assets" ^
    --add-data "ximc;ximc" ^
    --add-data "pyximc.py;." ^
    --hidden-import "pyximc" ^
    --hidden-import "OpenGL.platform.win32" ^
    "main.py"

if errorlevel 1 (
    echo Build failed. Preserved settings backup remains at: %PRESERVED_SETTINGS%
    if exist "%APP_NAME%.spec" del /Q "%APP_NAME%.spec"
    exit /b 1
)

if exist "%PRESERVED_SETTINGS%" (
    copy /Y "%PRESERVED_SETTINGS%" "dist\%APP_NAME%\settings.ini" >nul
    del /Q "%PRESERVED_SETTINGS%"
)

if exist "%APP_NAME%.spec" del /Q "%APP_NAME%.spec"

echo.
echo Build complete: dist\%APP_NAME%\%APP_NAME%.exe
endlocal
