@echo off
echo Installing dependencies...
pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo.
    echo Install failed. Make sure Python is in your PATH.
    pause
    exit /b 1
)
echo.
echo Done! Starting jellyrpc...
start pythonw jellyrpc.py
