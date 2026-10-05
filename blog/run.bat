@echo off
chcp 65001 > nul
cd /d "%~dp0"
if not exist .venv (
  echo 처음 실행이라 필요한 프로그램을 설치합니다...
  py -3 -m venv .venv || goto :error
  .venv\Scripts\python -m pip install -q -r requirements.txt || goto :error
)
.venv\Scripts\python run.py %*
pause
exit /b

:error
echo 설치에 실패했습니다. Python 3.10 이상이 설치되어 있는지 확인해 주세요.
pause
