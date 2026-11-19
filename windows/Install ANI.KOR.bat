@echo off
title ANI.KOR installer
chcp 65001 >nul
echo.
echo   ANI.KOR installer
echo   ------------------
echo   This downloads and sets up everything ANI.KOR needs.
echo   The first time takes about 5 minutes. Leave this window open.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { irm 'https://raw.githubusercontent.com/anikor-dev/anikor/main/windows/install.ps1' | iex } catch { Write-Host ('  ' + $_) -ForegroundColor Red; exit 1 }"
if errorlevel 1 (
  echo.
  echo   Something went wrong. Take a screenshot of this window and send it over.
  echo.
  pause
  exit /b 1
)
echo.
pause
