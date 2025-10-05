@echo off
echo ========================================
echo MX Fantasy League - Python Setup Script
echo ========================================
echo.

echo [1/4] Finding Python installation...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found in PATH. Trying common locations...
    
    if exist "C:\Python39\python.exe" (
        set PYTHON_PATH=C:\Python39\python.exe
        echo Found Python at: C:\Python39\python.exe
    ) else if exist "C:\Python310\python.exe" (
        set PYTHON_PATH=C:\Python310\python.exe
        echo Found Python at: C:\Python310\python.exe
    ) else if exist "C:\Python311\python.exe" (
        set PYTHON_PATH=C:\Python311\python.exe
        echo Found Python at: C:\Python311\python.exe
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python39\python.exe" (
        set PYTHON_PATH=%LOCALAPPDATA%\Programs\Python\Python39\python.exe
        echo Found Python at: %LOCALAPPDATA%\Programs\Python\Python39\python.exe
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
        set PYTHON_PATH=%LOCALAPPDATA%\Programs\Python\Python310\python.exe
        echo Found Python at: %LOCALAPPDATA%\Programs\Python\Python310\python.exe
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
        set PYTHON_PATH=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
        echo Found Python at: %LOCALAPPDATA%\Programs\Python\Python311\python.exe
    ) else (
        echo ERROR: Python not found! Please install Python first.
        pause
        exit /b 1
    )
) else (
    set PYTHON_PATH=python
    echo Found Python in PATH
)

echo.
echo [2/4] Installing python-dotenv...
"%PYTHON_PATH%" -m pip install python-dotenv
if %errorlevel% neq 0 (
    echo ERROR: Failed to install python-dotenv
    pause
    exit /b 1
)
echo python-dotenv installed successfully!

echo.
echo [3/4] Installing other dependencies...
"%PYTHON_PATH%" -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo WARNING: Some dependencies might not have installed correctly
)

echo.
echo [4/4] Testing the application...
echo Starting MX Fantasy League...
echo.
echo If the app starts successfully, you should see:
echo "Running on http://127.0.0.1:5000"
echo.
echo Press Ctrl+C to stop the app when you're done testing.
echo.

"%PYTHON_PATH%" app.py

echo.
echo ========================================
echo Setup complete! Your app should be running.
echo ========================================
pause

