@echo off
echo ==========================================
echo Сборка Wispr Clone в один EXE-файл...
echo ==========================================

python -m PyInstaller --onefile --noconsole --name "WisprFlowClone" --collect-all sounddevice --collect-all soundfile app.py

if %ERRORLEVEL% NEQ 0 (
    echo [ОШИБКА] Сборка завершилась неудачей!
    pause
    exit /b %ERRORLEVEL%
)

echo ==========================================
echo [УСПЕХ] Сборка успешно завершена!
echo Файл находится в папке: dist\WisprFlowClone.exe
echo ==========================================
pause
