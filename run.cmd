@echo off
rem FrameLab dev server launcher (double-click or run in cmd)
rem NOTE: keep this file ASCII-only. cmd.exe parses .cmd files in GBK
rem (codepage 936) on Chinese Windows, so UTF-8 Chinese comments here
rem become garbage commands and the window closes immediately.
rem The venv was created by Anaconda Python 3.8, whose OpenSSL DLLs live
rem in Library\bin - add it to PATH or import _ssl fails.
set "PATH=%~dp0.venv\Scripts;D:\ProgramFiles\Anaconda3\Library\bin;%PATH%"

rem ONE window only: enlarge it so the full startup log / traceback stays visible.
title FrameLab dev server (port 5001)
mode con: cols=110 lines=50

rem The browser is opened by app.py itself ~2s after boot (no extra cmd window here).
"%~dp0.venv\Scripts\python.exe" -X utf8 "%~dp0app.py"

echo.
echo ================================
echo Server stopped. If there is an error above, copy it to the developer.
pause
