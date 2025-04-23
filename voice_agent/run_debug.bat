@echo off

:: Абсолютный путь до python.exe
set "PYTHON_EXE=C:\Users\elozo\AppData\Local\Programs\Python\Python312\python.exe"

:: Путь до agent.py
set "AGENT=%~dp0agent.py"

:: Переход в папку, где лежит bat-файл
cd /d "%~dp0"

:: Запуск с кавычками вокруг пути
"%PYTHON_EXE%" "%AGENT%"

pause
