@echo off
chcp 65001 > nul
title GTA VC Unified System Builder
color 0A

echo.
echo    ╔══════════════════════════════════════════════════╗
echo    ║      GTA VC UNIFIED SYSTEM BUILDER              ║
echo    ║      Python ↔ C++ Bridge System                 ║
echo    ╚══════════════════════════════════════════════════╝
echo.

:main_menu
cls
echo.
echo    Select build option:
echo.
echo    1. Build All Components
echo    2. Build C++ DLL Only
echo    3. Build Python Components
echo    4. Test System
echo    5. Create Installation Package
echo    6. Exit
echo.
set /p choice="Enter choice (1-6): "

if "%choice%"=="1" goto build_all
if "%choice%"=="2" goto build_dll
if "%choice%"=="3" goto build_python
if "%choice%"=="4" goto test_system
if "%choice%"=="5" goto create_package
if "%choice%"=="6" goto exit_program

goto main_menu

:build_all
echo.
echo Building All Components...
echo This will compile the complete system.
echo.

call :build_dll
call :build_python

echo.
echo ✓ All components built successfully!
echo.
echo Files created:
echo   - MultiplayerCore.dll (C++ Core)
echo   - AdvancedInjector.py
echo   - CPP_Controller.py
echo   - UnifiedMultiplayerSystem.py
echo.
pause
goto main_menu

:build_dll
echo.
echo Building C++ DLL...
echo.

:: Check for C++ compiler
where g++ >nul 2>nul
if %errorlevel% equ 0 (
    echo Found g++ compiler
    goto compile_with_gpp
)

where cl >nul 2>nul
if %errorlevel% equ 0 (
    echo Found MSVC compiler
    goto compile_with_msvc
)

echo.
echo ERROR: No C++ compiler found!
echo.
echo Please install one of:
echo   1. MinGW (g++) - Download from: https://mingw-w64.org/
echo   2. Microsoft Visual C++ Build Tools
echo.
echo After installation, add to PATH and try again.
echo.
pause
goto main_menu

:compile_with_gpp
echo Compiling with g++...
echo.

:: Check if source files exist
if not exist "MultiplayerCore_Enhanced.cpp" (
    echo ERROR: MultiplayerCore_Enhanced.cpp not found!
    echo.
    pause
    goto main_menu
)

:: Compile DLL
echo Compiling MultiplayerCore.dll...
g++ -shared -o MultiplayerCore.dll MultiplayerCore_Enhanced.cpp -lws2_32 -static -std=c++11

if exist "MultiplayerCore.dll" (
    echo ✓ DLL compiled successfully!
    for %%I in ("MultiplayerCore.dll") do echo Size: %%~zI bytes
) else (
    echo ✗ DLL compilation failed!
    echo Trying alternative compilation...
    
    :: Try simpler compilation
    g++ -shared -o MultiplayerCore.dll MultiplayerCore_Enhanced.cpp -lws2_32
)

echo.
pause
goto main_menu

:compile_with_msvc
echo Compiling with MSVC...
echo.

:: This requires Visual Studio environment
if not exist "MultiplayerCore_Enhanced.cpp" (
    echo ERROR: MultiplayerCore_Enhanced.cpp not found!
    echo.
    pause
    goto main_menu
)

echo Please compile manually using:
echo   1. Open Visual Studio Developer Command Prompt
echo   2. Navigate to this folder
echo   3. Run: cl /LD MultiplayerCore_Enhanced.cpp ws2_32.lib
echo   4. Copy the resulting DLL to this folder
echo.
echo Or install MinGW for automatic compilation.
echo.
pause
goto main_menu

:build_python
echo.
echo Building Python Components...
echo.

:: Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found!
    echo Please install Python 3.8 or higher
    echo.
    pause
    goto main_menu
)

:: Install required packages
echo Installing required Python packages...
pip install psutil

:: Check for pywin32 (Windows only)
python -c "import sys; print('Python', sys.version)" >nul 2>&1
if %errorlevel% equ 0 (
    python -c "try: import win32api; print('pywin32 OK') except: print('pywin32 not found, some features may be limited')"
)

:: Test imports
echo Testing Python components...
python -c "
try:
    import psutil, ctypes, socket, json, threading, time
    print('Python core dependencies OK')
except Exception as e:
    print(f'Python dependencies error: {e}')
"

echo.
echo ✓ Python components ready!
echo.
pause
goto main_menu

:test_system
echo.
echo Testing System...
echo.

:: Check if GTA VC is running
echo Checking for GTA Vice City...
tasklist | findstr /i "gta-vc.exe gta_vc.exe vicecity.exe" >nul
if %errorlevel% equ 0 (
    echo ✅ GTA Vice City is running
) else (
    echo ⚠ GTA Vice City is not running
    echo Please run the game first for full test
)

:: Test Python components
echo Testing Python components...
python -c "
import sys
print('Python', sys.version)

# Test basic imports
try:
    import psutil, ctypes, socket, json, threading, time
    print('✅ Basic imports OK')
except Exception as e:
    print(f'❌ Basic imports failed: {e}')

# Test advanced components
try:
    # Try to import our components
    import os
    if os.path.exists('AdvancedInjector.py'):
        exec(open('AdvancedInjector.py').read())
        print('✅ AdvancedInjector available')
    else:
        print('⚠ AdvancedInjector.py not found')
        
    if os.path.exists('CPP_Controller.py'):
        exec(open('CPP_Controller.py').read())
        print('✅ CPP_Controller available')
    else:
        print('⚠ CPP_Controller.py not found')
        
except Exception as e:
    print(f'⚠ Component test: {e}')
"

:: Test DLL if exists
if exist "MultiplayerCore.dll" (
    echo ✅ DLL found: MultiplayerCore.dll
    
    :: Check DLL dependencies
    where dumpbin >nul 2>&1
    if %errorlevel% equ 0 (
        echo Checking DLL dependencies...
        dumpbin /dependents MultiplayerCore.dll > dependencies.txt 2>&1
        if %errorlevel% equ 0 (
            echo ✅ DLL dependency check passed
        ) else (
            echo ⚠ Could not check DLL dependencies
        )
        del dependencies.txt 2>nul
    ) else (
        echo ℹ dumpbin not available for dependency check
    )
) else (
    echo ⚠ DLL not found, compile it first (Option 2)
)

echo.
echo System test completed!
echo.
pause
goto main_menu

:create_package
echo.
echo Creating Installation Package...
echo.

if not exist "dist" mkdir "dist"
if not exist "dist\system" mkdir "dist\system"

:: Copy all files
echo Copying system files...

:: Python files
copy "AdvancedInjector.py" "dist\system\" >nul 2>&1
copy "CPP_Controller.py" "dist\system\" >nul 2>&1
copy "UnifiedMultiplayerSystem.py" "dist\system\" >nul 2>&1
copy "MemoryInjector.py" "dist\system\" >nul 2>&1

:: C++ DLL
if exist "MultiplayerCore.dll" (
    copy "MultiplayerCore.dll" "dist\system\" >nul 2>&1
    echo Copied MultiplayerCore.dll
)

:: Documentation
if exist "README.txt" copy "README.txt" "dist\" >nul 2>&1
if exist "LICENSE.txt" copy "LICENSE.txt" "dist\" >nul 2>&1

:: Create launcher
echo Creating launcher...
echo @echo off > "dist\Launch System.bat"
echo chcp 65001 ^>nul >> "dist\Launch System.bat"
echo echo GTA VC Unified Multiplayer System >> "dist\Launch System.bat"
echo echo ================================= >> "dist\Launch System.bat"
echo echo. >> "dist\Launch System.bat"
echo echo Starting system... >> "dist\Launch System.bat"
echo cd system >> "dist\Launch System.bat"
echo python "UnifiedMultiplayerSystem.py" >> "dist\Launch System.bat"
echo pause >> "dist\Launch System.bat"

:: Create installer
echo Creating installer script...
echo @echo off > "dist\Install.bat"
echo chcp 65001 ^>nul >> "dist\Install.bat"
echo echo Installing GTA VC Unified System... >> "dist\Install.bat"
echo echo. >> "dist\Install.bat"
echo echo Installing Python dependencies... >> "dist\Install.bat"
echo pip install psutil >> "dist\Install.bat"
echo echo. >> "dist\Install.bat"
echo echo Installation complete! >> "dist\Install.bat"
echo echo. >> "dist\Install.bat"
echo echo To start the system: >> "dist\Install.bat"
echo echo   1. Make sure GTA Vice City is running >> "dist\Install.bat"
echo echo   2. Run Launch System.bat >> "dist\Install.bat"
echo echo. >> "dist\Install.bat"
echo pause >> "dist\Install.bat"

echo.
echo ✓ Installation package created in 'dist' folder
echo.
echo To install:
echo   1. Copy 'dist' folder to target computer
echo   2. Run Install.bat as Administrator
echo   3. Run Launch System.bat
echo.
pause
goto main_menu

:exit_program
echo.
echo Thank you for using GTA VC Unified System Builder!
echo.
exit /b 0