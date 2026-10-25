@echo off
REM ============================================================
REM  AILT9019 Q&A — one-time install script (Windows)
REM  Installs Python dependencies and indexes any PDFs in data/
REM ============================================================

echo.
echo  ============================================
echo   AILT9019 Course Q&A - Installation
echo  ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found. Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

echo  [1/2] Installing dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo  [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo  [2/2] Indexing PDFs in data/ (if any)...
python -c "import indexer; r = indexer.index_all(); print('Indexed:', r) if r else print('No PDFs found in data/. Copy course PDFs there.')"

echo.
echo  Installation complete!
echo  Run start.bat to launch the app.
echo.
pause
