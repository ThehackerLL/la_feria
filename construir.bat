@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo   Construyendo Sistema POS (64 bits)
echo ============================================

rem Usa el Python del entorno virtual si existe
set PY=python
if exist "venv\Scripts\python.exe" set PY=venv\Scripts\python.exe
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe

echo Usando: %PY%
%PY% -m pip install -r requirements.txt
if errorlevel 1 goto error

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

%PY% -m PyInstaller --noconfirm --clean --windowed ^
  --name SistemaPOS ^
  --icon recursos\icono.ico ^
  --add-data "recursos;recursos" ^
  --collect-all customtkinter ^
  --collect-submodules app ^
  main.py
if errorlevel 1 goto error

echo.
echo ============================================
echo   LISTO. El programa quedo en: dist\SistemaPOS
echo   Prueba dist\SistemaPOS\SistemaPOS.exe
echo ============================================
pause
exit /b 0

:error
echo.
echo *** ALGO FALLO. Copia el mensaje de arriba y mandamelo. ***
pause
exit /b 1