@echo off
REM ============================================================
REM  AILT9019 Q&A — launch script (Windows)
REM  Starts the server and opens the browser automatically
REM ============================================================

echo.
echo  Starting AILT9019 Course Q&A...
echo  Server: http://127.0.0.1:8765
echo  Press Ctrl+C to stop.
echo.

REM Open browser after a short delay
start "" "http://127.0.0.1:8765"

REM Start server
python app.py

pause
