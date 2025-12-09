@echo off
chcp 65001 > nul
title GTA VC Unified System Builder
color 0A

echo.
echo    ╔══════════════════════════════════════════════════╗
echo    ║      GTA Vice City Unified System Builder       ║
echo    ╚══════════════════════════════════════════════════╝
echo.

:main_menu
cls
echo.
echo    Select build option:
echo.
echo    1. Build Unified System (Python files)
echo    2. Create Installer
echo    3. Create Portable Package
echo    4. Create All
echo    5. Exit
echo.
set /p choice="Enter choice (1-5): "

if "%choice%"=="1" goto build_system
if "%choice%"=="2" goto build_installer
if "%choice%"=="3" goto build_portable
if "%choice%"=="4" goto build_all
if "%choice%"=="5" goto exit_program

goto main_menu

:build_system
echo.
echo Building Unified System...
echo.

:: Check if required files exist
if not exist "GTAVC_Unified_System.py" (
    echo ERROR: Main system file not found!
    echo.
    pause
    goto main_menu
)

:: Create dist directory
if not exist "dist" mkdir "dist"

:: Copy system files
echo Copying system files...
copy "GTAVC_Unified_System.py" "dist\"
copy "README.txt" "dist\" 2>nul
copy "LICENSE.txt" "dist\" 2>nul
copy "unified_config.json" "dist\" 2>nul

:: Create launcher batch file
echo @echo off > "dist\Run System.bat"
echo echo GTA Vice City Unified System >> "dist\Run System.bat"
echo echo ============================ >> "dist\Run System.bat"
echo python "GTAVC_Unified_System.py" >> "dist\Run System.bat"
echo pause >> "dist\Run System.bat"

echo.
echo ✓ Unified System built successfully!
echo Location: dist folder
echo.
pause
goto main_menu

:build_installer
echo.
echo Building Installer...
echo.

if not exist "Unified_Installer.py" (
    echo ERROR: Installer file not found!
    echo.
    pause
    goto main_menu
)

:: Run installer builder
python Unified_Installer.py

echo.
echo ✓ Installer created!
echo.
pause
goto main_menu

:build_portable
echo.
echo Creating Portable Package...
echo.

if not exist "dist" (
    echo ERROR: System not built yet. Run option 1 first.
    echo.
    pause
    goto main_menu
)

:: Create portable directory
if not exist "Portable" mkdir "Portable"

:: Copy files
echo Copying files to portable package...
xcopy "dist\*" "Portable\" /E /I /Y

:: Create portable launcher
echo @echo off > "Portable\PORTABLE LAUNCHER.bat"
echo echo GTA Vice City Unified System - Portable >> "Portable\PORTABLE LAUNCHER.bat"
echo echo ====================================== >> "Portable\PORTABLE LAUNCHER.bat"
echo echo. >> "Portable\PORTABLE LAUNCHER.bat"
echo echo This is a portable version. No installation required. >> "Portable\PORTABLE LAUNCHER.bat"
echo echo Run on any computer from USB or folder. >> "Portable\PORTABLE LAUNCHER.bat"
echo echo. >> "Portable\PORTABLE LAUNCHER.bat"
echo python "GTAVC_Unified_System.py" >> "Portable\PORTABLE LAUNCHER.bat"
echo pause >> "Portable\PORTABLE LAUNCHER.bat"

echo.
echo ✓ Portable package created!
echo Location: Portable folder
echo.
pause
goto main_menu

:build_all
echo.
echo Building ALL packages...
echo This may take a few minutes...
echo.

call :build_system
call :build_installer
call :build_portable

echo.
echo All packages built successfully!
echo.
echo Available packages:
echo 1. dist - System files
echo 2. Portable - Portable version
echo 3. Run Unified_Installer.py for installer
echo.
pause
goto main_menu

:exit_program
echo.
echo Thank you for using GTA VC Unified System Builder!
echo.
exit /b 0