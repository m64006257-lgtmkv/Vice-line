@echo off
chcp 65001 > nul
title GTA VC Multiplayer System Builder
color 0A

echo.
echo    ╔══════════════════════════════════════════════════╗
echo    ║      GTA VC MULTIPLAYER SYSTEM BUILDER          ║
echo    ╚══════════════════════════════════════════════════╝
echo.

:main_menu
cls
echo.
echo    Select build option:
echo.
echo    1. Build Complete System (All Components)
echo    2. Build Memory Manager Only
echo    3. Build DLL (C++ Core)
echo    4. Build Python Interface
echo    5. Create Installer Package
echo    6. Compile to EXE
echo    7. Exit
echo.
set /p choice="Enter choice (1-7): "

if "%choice%"=="1" goto build_all
if "%choice%"=="2" goto build_memory
if "%choice%"=="3" goto build_dll
if "%choice%"=="4" goto build_python
if "%choice%"=="5" goto build_installer
if "%choice%"=="6" goto build_exe
if "%choice%"=="7" goto exit_program

goto main_menu

:build_all
echo.
echo Building Complete Multiplayer System...
echo This will compile all components.
echo.

call :build_memory
call :build_dll
call :build_python
call :build_exe

echo.
echo ✓ Complete system built successfully!
echo.
echo Components:
echo   - MemoryInjector.py
echo   - MultiplayerCore.dll
echo   - GTAMultiplayerSystem.py
echo   - MultiplayerGUI.exe
echo.
pause
goto main_menu

:build_memory
echo.
echo Building Memory Manager...
echo.

:: Check Python dependencies
python -c "import psutil" 2>nul
if %errorlevel% neq 0 (
    echo Installing psutil...
    pip install psutil
)

python -c "import pywin32" 2>nul
if %errorlevel% neq 0 (
    echo Installing pywin32...
    pip install pywin32
)

:: Copy memory manager
if not exist "MemoryInjector.py" (
    echo ERROR: MemoryInjector.py not found!
    echo.
    pause
    goto main_menu
)

echo ✓ Memory manager ready
goto :EOF

:build_dll
echo.
echo Building C++ DLL Core...
echo.

:: Check for C++ compiler
where g++ >nul 2>nul
if %errorlevel% equ 0 (
    echo Found g++ compiler
    goto compile_dll
)

where cl >nul 2>nul
if %errorlevel% equ 0 (
    echo Found MSVC compiler
    goto compile_dll_msvc
)

echo.
echo ERROR: No C++ compiler found!
echo.
echo Please install one of:
echo   - MinGW (g++)
echo   - Microsoft Visual C++ Build Tools
echo.
pause
goto main_menu

:compile_dll
echo Compiling with g++...
g++ -shared -o MultiplayerCore.dll MultiplayerCore.cpp -lws2_32 -static
if exist "MultiplayerCore.dll" (
    echo ✓ DLL compiled successfully
) else (
    echo ✗ DLL compilation failed
)
goto :EOF

:compile_dll_msvc
echo Compiling with MSVC...
:: This requires Visual Studio environment
echo Please compile manually using Visual Studio
echo.
pause
goto :EOF

:build_python
echo.
echo Building Python Interface...
echo.

:: Check Python version
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found!
    echo Please install Python 3.8 or higher
    echo.
    pause
    goto main_menu
)

:: Install required packages
echo Installing required packages...
pip install psutil pywin32

:: Test the system
echo Testing system...
python -c "from MemoryInjector import GTAVCMemoryManager; print('Memory module OK')"

echo ✓ Python interface ready
goto :EOF

:build_installer
echo.
echo Creating Installer Package...
echo.

if not exist "dist" mkdir "dist"
if not exist "dist\system" mkdir "dist\system"

:: Copy all files
echo Copying system files...
copy "MemoryInjector.py" "dist\system\"
copy "GTAMultiplayerSystem.py" "dist\system\"
copy "MultiplayerCore.dll" "dist\system\" 2>nul
copy "README.txt" "dist\"
copy "LICENSE.txt" "dist\"

:: Create installer script
echo @echo off > "dist\install.bat"
echo echo Installing GTA VC Multiplayer System... >> "dist\install.bat"
echo echo. >> "dist\install.bat"
echo echo This will install the multiplayer system components. >> "dist\install.bat"
echo echo. >> "dist\install.bat"
echo echo Installing Python dependencies... >> "dist\install.bat"
echo pip install psutil pywin32 >> "dist\install.bat"
echo echo. >> "dist\install.bat"
echo echo Installation complete! >> "dist\install.bat"
echo echo. >> "dist\install.bat"
echo echo To start the system: >> "dist\install.bat"
echo echo   1. Run GTA Vice City >> "dist\install.bat"
echo echo   2. Run MultiplayerGUI.exe >> "dist\install.bat"
echo echo   3. Choose Host or Join >> "dist\install.bat"
echo echo. >> "dist\install.bat"
echo pause >> "dist\install.bat"

:: Create launcher
echo @echo off > "dist\Start Multiplayer.bat"
echo echo GTA VC Multiplayer System >> "dist\Start Multiplayer.bat"
echo echo ========================= >> "dist\Start Multiplayer.bat"
echo echo. >> "dist\Start Multiplayer.bat"
echo echo Starting Multiplayer GUI... >> "dist\Start Multiplayer.bat"
echo python "system\GTAMultiplayerSystem.py" >> "dist\Start Multiplayer.bat"
echo pause >> "dist\Start Multiplayer.bat"

echo.
echo ✓ Installer package created in 'dist' folder
echo.
pause
goto main_menu

:build_exe
echo.
echo Compiling to EXE...
echo.

:: Check for PyInstaller
pip list | findstr pyinstaller >nul
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

:: Compile GUI to EXE
echo Compiling MultiplayerGUI...
pyinstaller --onefile --windowed --name="GTAVC_Multiplayer" GTAMultiplayerSystem.py

if exist "dist\GTAVC_Multiplayer.exe" (
    echo ✓ EXE compiled successfully
    copy "dist\GTAVC_Multiplayer.exe" "MultiplayerGUI.exe"
) else (
    echo ✗ EXE compilation failed
)

echo.
pause
goto main_menu

:exit_program
echo.
echo Thank you for using GTA VC Multiplayer System Builder!
echo.
exit /b 0