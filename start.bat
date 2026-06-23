@echo off
echo ========================================
echo VIKMO Dealer Assistant - Start Script
echo ========================================
echo.
echo Starting backend server...
start cmd /k python server.py
echo.
echo Waiting 3 seconds for backend to start...
timeout /t 3
echo.
echo Starting frontend...
start cmd /k cd frontend && npm run dev
echo.
echo ========================================
echo Services starting:
echo Backend: http://localhost:5000
echo Frontend: http://localhost:3000
echo ========================================
echo.
echo Opening frontend in browser...
timeout /t 2
start http://localhost:3000
