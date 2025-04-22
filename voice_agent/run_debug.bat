@echo off
set BASEDIR=%~dp0

rem — путь до обычного python.exe (с окном)
set PYW="C:\Users\elozo\AppData\Local\Programs\Python\Python312\python.exe"

rem — путь до скрипта
set AGENT="%BASEDIR%agent.py"

pushd "%BASEDIR%"

rem — запускаем без сворачивания (для отладки)
%PYW% %AGENT%

popd
pause
