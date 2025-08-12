@echo off
title Kodi TextureTool - Visual C++ Runtime Installer
CD /d %~dp0

REM Draw banner manually for reliability
echo.
echo -------------------------------------------------------------
echo -     Kodi TextureTool - Visual C++ Runtime Installer       -
echo -------------------------------------------------------------
echo Source: TechPowerUp -- All-In-One VC++ Redistributables
echo.

REM Detect system architecture
set IS_X64=0
if "%PROCESSOR_ARCHITECTURE%"=="AMD64" set IS_X64=1
if defined PROCESSOR_ARCHITEW6432 if "%PROCESSOR_ARCHITEW6432%"=="AMD64" set IS_X64=1

REM Begin install
if "%IS_X64%"=="1" (
    call :Install64
) else (
    call :Install86
)
goto END

:Install64
echo System architecture detected: 64-bit
echo Installing both x86 and x64 Redistributables for full compatibility.
echo.
call :RunVC vcredist2010_x86.exe "VC++ 2010 x86"
call :RunVC vcredist2010_x64.exe "VC++ 2010 x64"
call :RunVC vcredist2015_2017_2019_2022_x86.exe "VC++ 2015-2022 x86"
call :RunVC vcredist2015_2017_2019_2022_x64.exe "VC++ 2015-2022 x64"
exit /b

:Install86
echo System architecture detected: 32-bit
echo Installing x86 Redistributables only.
echo.
call :RunVC vcredist2010_x86.exe "VC++ 2010 x86"
call :RunVC vcredist2015_2017_2019_2022_x86.exe "VC++ 2015-2022 x86"
exit /b

:RunVC
if exist "%~1" (
    echo Installing %~2...
    start /wait "" "%~1" /passive /norestart
    echo Done: %~2
    echo.
) else (
    echo SKIPPED - Installer not found: %~1
    echo.
)
exit /b

:END
echo -------------------------------------------------------------
echo -    Kodi TextureTool - Runtime installation complete.      -
echo -------------------------------------------------------------
echo.
ping -n 4 127.0.0.1 >nul
exit