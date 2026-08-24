@echo off
echo ========================================
echo   NeonTerm Build Script (Nuitka)
echo ========================================
echo.

REM === Шаг 1: Проверяем Python ===
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Install Python 3.8+
    pause
    exit /b 1
)

REM === Шаг 2: Устанавливаем Nuitka ===
echo [1/4] Installing Nuitka...
pip install nuitka ordered-set zstandard --quiet --upgrade

REM === Шаг 3: Проверяем наличие C-компилятора ===
echo [2/4] Checking C compiler...
echo Nuitka will auto-download MinGW64 if MSVC is not found.
echo.

REM === Шаг 4: Компиляция ===
echo [3/4] Compiling NeonTerm to native executable...
echo This may take 2-5 minutes on first run...
echo.

python -m nuitka ^
    --onefile ^
    --windows-disable-console ^
    --windows-company-name="NeonTerm" ^
    --windows-product-name="NeonTerm" ^
    --windows-file-version=1.0.0.0 ^
    --windows-product-version=1.0.0.0 ^
    --windows-file-description="Ultra-lightweight Terminal Emulator" ^
    --enable-plugin=tk-inter ^
    --remove-output ^
    --assume-yes-for-downloads ^
    --output-dir=dist ^
    neonterm.py

echo.

REM === Шаг 5: Проверяем результат ===
if exist "dist\neonterm.exe" (
    echo [4/4] BUILD SUCCESSFUL!
    echo.
    
    REM Показываем размер файла
    for %%A in ("dist\neonterm.exe") do (
        set /a size=%%~zA / 1048576
        echo   Output:  dist\neonterm.exe
        echo   Size:    %%~zA bytes (~%size% MB^)
    )
    echo.
    echo   Run:     dist\neonterm.exe
    echo.
) else (
    echo [ERROR] Build failed! Check errors above.
)

pause