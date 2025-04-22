@echo off
set BASEDIR=%~dp0

rem — абсолютный путь до pythonw.exe вашей системы
set PYW="C:\Users\elozo\AppData\Local\Programs\Python\Python312\pythonw.exe"

set AGENT="%BASEDIR%agent.py"

pushd "%BASEDIR%"
start "" /min %PYW% %AGENT%
popd
