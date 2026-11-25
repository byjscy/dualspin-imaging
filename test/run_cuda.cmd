@echo off
setlocal
set "POLAR_PYTHON=%USERPROFILE%\miniconda3\envs\DP\python.exe"
if not exist "%POLAR_PYTHON%" (
    echo Could not find the DP interpreter at "%POLAR_PYTHON%".
    exit /b 1
)
set "PYTHONUTF8=1"
"%POLAR_PYTHON%" "%~dp0train_dual_pol.py" %*
exit /b %errorlevel%
