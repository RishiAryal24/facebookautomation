@echo off
echo ========================================================
echo   PyLoom AI-Powered Facebook Automation System
echo ========================================================
echo.

echo [1/2] Starting FastAPI Backend on http://localhost:8000 ...
start "PyLoom Backend" cmd /k "cd /d %~dp0 && .venv\Scripts\python.exe backend\run.py"

echo [2/2] Starting Vite React Frontend on http://localhost:5173 ...
start "PyLoom Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Both services are launching:
echo  - Frontend Dashboard: http://localhost:5173
echo  - Backend API Docs:   http://localhost:8000/docs
echo.
pause
